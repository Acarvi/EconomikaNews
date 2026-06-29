import argparse
import json
import os
import sys
import datetime
import subprocess
import re
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

def normalize_handle(handle: str) -> str:
    """Strip @ and whitespace from account handle."""
    if not handle:
        return ""
    return handle.strip().lstrip("@")

def post_id_from_url(url: str) -> str:
    """Extracts the status ID from an X/Twitter URL. Returns None if not found."""
    if not url:
        return None
    match = re.search(r'status/(\d+)', url)
    if match:
        return match.group(1)
    return None

def normalize_metric(value) -> int:
    """Converts string/missing values to integers."""
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        # Remove commas if present (basic handling)
        value = value.replace(",", "")
        # Handle 'K' and 'M' basic
        multiplier = 1
        value = value.upper()
        if 'K' in value:
            multiplier = 1000
            value = value.replace('K', '')
        elif 'M' in value:
            multiplier = 1000000
            value = value.replace('M', '')
        try:
            return int(float(value) * multiplier)
        except ValueError:
            return 0
    return 0

def normalize_post(raw: dict, account_handle: str, provider: str) -> dict:
    """Normalizes raw fetched data into standard JSON shape."""
    url = raw.get("url", "")
    if url.startswith("/"):
        url = f"https://x.com{url}"
        
    post_id = raw.get("post_id") or post_id_from_url(url)
    
    # Simple metric extraction
    like_count = normalize_metric(raw.get("like_count") or raw.get("favorite_count") or 0)
    repost_count = normalize_metric(raw.get("repost_count") or raw.get("retweet_count") or 0)
    reply_count = normalize_metric(raw.get("reply_count") or 0)
    quote_count = normalize_metric(raw.get("quote_count") or 0)
    view_count = normalize_metric(raw.get("view_count") or 0)
    
    media_urls = raw.get("media_urls", [])
    if isinstance(media_urls, str):
        media_urls = [media_urls]
        
    # Support manual input passing created_at as is
    created_at = raw.get("created_at")
    
    return {
        "post_id": post_id,
        "account_handle": account_handle,
        "text": raw.get("text", raw.get("full_text", "")),
        "url": url,
        "created_at": created_at,
        "like_count": like_count,
        "repost_count": repost_count,
        "reply_count": reply_count,
        "quote_count": quote_count,
        "view_count": view_count,
        "media_urls": media_urls,
        "media": raw.get("media", []),
        "raw": raw if provider != "manual-json" else raw.get("raw", {})
    }

def filter_posts(posts, days_back, include_replies, include_reposts):
    """Filters posts by date and type."""
    filtered = []
    
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=days_back)
    
    for p in posts:
        # Check replies/reposts if detectable in raw text (basic heuristic for non-API providers)
        text = p.get("text", "")
        is_reply = text.startswith("@") or p.get("raw", {}).get("in_reply_to_status_id") or p.get("raw", {}).get("is_reply")
        is_repost = text.startswith("RT @") or p.get("raw", {}).get("retweeted_status")
        
        if not include_replies and is_reply:
            continue
            
        if not include_reposts and is_repost:
            continue
            
        # Check date
        created_at = p.get("created_at")
        if created_at:
            try:
                dt_str = created_at.replace("Z", "+00:00")
                dt = datetime.datetime.fromisoformat(dt_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                if dt < cutoff:
                    continue
            except Exception:
                pass # If we can't parse date, we keep it
                
        filtered.append(p)
        
    return filtered

def write_json_atomically(payload: dict, path: Path):
    """Writes JSON payload atomically to avoid partial reads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(temp_fd, 'w', encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, path)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e

def fetch_manual_json(input_path: str):
    """Fallback manual provider."""
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return [], [f"Failed to read input JSON: {e}"], []
        
    raw_posts = data.get("posts", data) if isinstance(data, dict) else data
    if not isinstance(raw_posts, list):
        return [], ["Input JSON must contain a list of posts or a 'posts' array."], []
        
    posts = []
    for raw in raw_posts:
        account_handle = raw.get("account_handle", "unknown")
        posts.append(normalize_post(raw, account_handle, "manual-json"))
        
    return posts, [], []

def fetch_gallery_dl(accounts, max_posts, cookies_browser):
    """gallery-dl provider implementation."""
    if not shutil_which("gallery-dl"):
        return [], ["gallery-dl not found. Install with: py -m pip install gallery-dl"], []
        
    posts = []
    errors = []
    warnings = []
    
    for account in accounts:
        cmd = ["gallery-dl", "--dump-json", f"https://x.com/{account}"]
        if cookies_browser:
            cmd.extend(["--cookies-from-browser", cookies_browser])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                errors.append(f"gallery-dl error for {account}: {result.stderr.strip()}")
                continue
                
            # gallery-dl outputs multiple JSON objects or a list
            lines = result.stdout.strip().split('\n')
            count = 0
            for line in lines:
                if not line.strip():
                    continue
                if count >= max_posts:
                    break
                    
                try:
                    raw = json.loads(line)
                    # gallery-dl structure can vary, typical: [category, {data}]
                    if isinstance(raw, list) and len(raw) > 1 and isinstance(raw[1], dict):
                        data = raw[1]
                    else:
                        data = raw
                        
                    post = normalize_post({
                        "text": data.get("content", data.get("text", "")),
                        "url": data.get("tweet_url", data.get("url", "")),
                        "created_at": data.get("date", ""),
                        "like_count": data.get("favorite_count", 0),
                        "repost_count": data.get("retweet_count", 0),
                        "reply_count": data.get("reply_count", 0),
                        "quote_count": data.get("quote_count", 0),
                        "raw": data
                    }, account, "gallery-dl")
                    posts.append(post)
                    count += 1
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            errors.append(f"Failed to run gallery-dl for {account}: {e}")
            
    return posts, errors, warnings

def shutil_which(cmd):
    import shutil
    return shutil.which(cmd)

def fetch_x_api(accounts, max_posts, token):
    """X API v2 provider implementation."""
    posts = []
    errors = []
    warnings = []
    
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "EconomikaNews/1.0"
    }
    
    for account in accounts:
        # 1. Get User ID
        url = f"https://api.twitter.com/2/users/by/username/{account}"
        req = urllib.request.Request(url, headers=headers)
        
        try:
            with urllib.request.urlopen(req) as response:
                user_data = json.loads(response.read())
                if "data" not in user_data:
                    errors.append(f"Could not find user {account} via X API")
                    continue
                user_id = user_data["data"]["id"]
        except urllib.error.URLError as e:
            errors.append(f"X API error resolving {account}: {e}")
            continue

        # 2. Get Tweets
        tweets_url = f"https://api.twitter.com/2/users/{user_id}/tweets?max_results={min(max_posts, 100)}&tweet.fields=created_at,public_metrics,in_reply_to_user_id&expansions=attachments.media_keys&media.fields=url,type"
        req = urllib.request.Request(tweets_url, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                tweets_data = json.loads(response.read())
                
                includes_media = {m["media_key"]: m for m in tweets_data.get("includes", {}).get("media", [])}
                
                for t in tweets_data.get("data", []):
                    metrics = t.get("public_metrics", {})
                    
                    media_urls = []
                    media_objs = []
                    
                    if "attachments" in t and "media_keys" in t["attachments"]:
                        for mk in t["attachments"]["media_keys"]:
                            m = includes_media.get(mk)
                            if m and "url" in m:
                                media_urls.append(m["url"])
                                media_objs.append({
                                    "url": m["url"],
                                    "type": m.get("type", "unknown"),
                                    "width": m.get("width"),
                                    "height": m.get("height")
                                })
                                
                    is_reply = bool(t.get("in_reply_to_user_id"))
                                
                    post = normalize_post({
                        "post_id": t["id"],
                        "text": t.get("text", ""),
                        "url": f"https://x.com/{account}/status/{t['id']}",
                        "created_at": t.get("created_at"),
                        "like_count": metrics.get("like_count", 0),
                        "repost_count": metrics.get("retweet_count", 0),
                        "reply_count": metrics.get("reply_count", 0),
                        "quote_count": metrics.get("quote_count", 0),
                        "media_urls": media_urls,
                        "media": media_objs,
                        "raw": t
                    }, account, "x-api")
                    
                    if is_reply:
                        post["raw"]["is_reply"] = True
                    
                    posts.append(post)
        except urllib.error.URLError as e:
            errors.append(f"X API error fetching tweets for {account}: {e}")
            
    return posts, errors, warnings
    
def fetch_yt_dlp(accounts, max_posts, cookies_browser):
    if not shutil_which("yt-dlp"):
        return [], ["yt-dlp not found. Install with: py -m pip install yt-dlp"], []
    return [], ["yt-dlp provider is not fully implemented for timelines yet."], []

def main():
    parser = argparse.ArgumentParser(description="Real X Ingestion Adapter")
    parser.add_argument("--accounts", type=str, help="Comma-separated handles")
    parser.add_argument("--config", type=str, default="config/x_accounts.json")
    parser.add_argument("--provider", type=str, default="auto", choices=["auto", "gallery-dl", "yt-dlp", "x-api", "manual-json"])
    parser.add_argument("--input-json", type=str)
    parser.add_argument("--output-json", type=str, default="runtime/x_posts/latest_posts.json")
    parser.add_argument("--max-posts-per-account", type=int, default=20)
    parser.add_argument("--days-back", type=int, default=2)
    parser.add_argument("--cookies-from-browser", type=str, choices=["firefox", "chrome", "edge"])
    parser.add_argument("--include-replies", action="store_true", default=False)
    parser.add_argument("--include-reposts", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--strict", action="store_true", default=False)
    parser.add_argument("--summary-json", type=str)
    parser.add_argument("--timeout-seconds", type=int, default=60)

    args = parser.parse_args()

    # Determine provider
    provider = args.provider
    if provider == "auto":
        if os.environ.get("X_BEARER_TOKEN"):
            provider = "x-api"
        elif shutil_which("gallery-dl"):
            provider = "gallery-dl"
        else:
            print("No valid provider found for auto. Set X_BEARER_TOKEN or install gallery-dl.", file=sys.stderr)
            sys.exit(1)

    accounts = [normalize_handle(a) for a in args.accounts.split(",")] if args.accounts else []

    posts = []
    errors = []
    warnings = []

    if provider == "manual-json":
        if not args.input_json:
            print("--input-json required for manual-json provider.", file=sys.stderr)
            sys.exit(1)
        posts, errors, warnings = fetch_manual_json(args.input_json)
    elif provider == "gallery-dl":
        if not accounts:
            print("--accounts required for gallery-dl provider.", file=sys.stderr)
            sys.exit(1)
        posts, errors, warnings = fetch_gallery_dl(accounts, args.max_posts_per_account, args.cookies_from_browser)
    elif provider == "x-api":
        if not accounts:
            print("--accounts required for x-api provider.", file=sys.stderr)
            sys.exit(1)
        token = os.environ.get("X_BEARER_TOKEN")
        if not token:
            print("X_BEARER_TOKEN environment variable required for x-api provider.", file=sys.stderr)
            sys.exit(1)
        posts, errors, warnings = fetch_x_api(accounts, args.max_posts_per_account, token)
    elif provider == "yt-dlp":
        posts, errors, warnings = fetch_yt_dlp(accounts, args.max_posts_per_account, args.cookies_from_browser)

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        if args.strict:
            sys.exit(1)

    posts = filter_posts(posts, args.days_back, args.include_replies, args.include_reposts)

    output_payload = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "provider": provider,
        "accounts": accounts,
        "posts": posts,
        "errors": errors,
        "warnings": warnings
    }

    if args.dry_run:
        print(f"Dry run. Found {len(posts)} posts.")
        for p in posts:
            print(f"- {p['post_id']} by {p['account_handle']}: {p['text'][:50]}...")
    else:
        out_path = Path(args.output_json)
        write_json_atomically(output_payload, out_path)
        print(f"Wrote {len(posts)} posts to {out_path}")
        
    if args.summary_json:
        sum_path = Path(args.summary_json)
        write_json_atomically({
            "generated_at": output_payload["generated_at"],
            "provider": provider,
            "post_count": len(posts),
            "error_count": len(errors)
        }, sum_path)

if __name__ == "__main__":
    main()
