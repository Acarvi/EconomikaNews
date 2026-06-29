import argparse
import json
import os
import sys
import datetime
import subprocess
import shutil
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def calculate_score(post):
    likes = post.get("like_count", 0)
    reposts = post.get("repost_count", 0)
    replies = post.get("reply_count", 0)
    quotes = post.get("quote_count", 0)
    score = likes + (reposts * 4) + (replies * 2) + (quotes * 3)
    
    age_hours = 1
    created_at = post.get("created_at")
    if created_at:
        try:
            created_at = created_at.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(created_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            delta = now - dt
            age_hours = max(delta.total_seconds() / 3600, 1)
        except Exception:
            pass
            
    score_per_hour = score / max(age_hours, 1)
    return score, score_per_hour

def load_posts_from_json(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        if "posts" in data:
            return data["posts"]
        return data

def extract_titular(text):
    text = re.sub(r'https?://\S+', '', text).strip()
    sentences = re.split(r'(?<=[.!?]) +', text)
    if not sentences:
        return ""
    titular = sentences[0][:140]
    return titular.upper()

def create_card_image(post, output_path):
    width, height = 1080, 1920
    img = Image.new("RGB", (width, height), color=(20, 20, 20))
    draw = ImageDraw.Draw(img)
    
    font_large = ImageFont.load_default()
    font_medium = ImageFont.load_default()
    font_small = ImageFont.load_default()
    try:
        font_large = ImageFont.truetype("arial.ttf", 80)
        font_medium = ImageFont.truetype("arial.ttf", 50)
        font_small = ImageFont.truetype("arial.ttf", 35)
    except:
        pass

    # Header
    draw.text((100, 200), "ECONOMIKA", fill=(255, 50, 50), font=font_large)
    draw.text((100, 300), "ÚLTIMA HORA", fill=(255, 255, 255), font=font_large)

    # Titular
    titular = extract_titular(post.get("text", ""))
    words = titular.split()
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        if len(" ".join(current_line)) > 20:
            lines.append(" ".join(current_line[:-1]))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    
    y = 600
    for line in lines:
        draw.text((100, y), line, fill=(255, 255, 200), font=font_large)
        y += 100

    # Subhead and Footer
    draw.text((100, 1500), f"Fuente: @{post.get('account_handle', 'unknown')}", fill=(150, 150, 150), font=font_medium)
    draw.text((100, 1600), f"URL: {post.get('url', '')}", fill=(100, 100, 100), font=font_small)

    img.save(output_path)

def generate_mp4(image_path, output_path, duration):
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(image_path),
        "-c:v", "libx264", "-t", str(duration), "-pix_fmt", "yuv420p",
        "-vf", "scale=1080:1920",
        str(output_path)
    ]
    try:
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        print("ffmpeg not found in PATH.")
        return False
    except subprocess.CalledProcessError:
        print("ffmpeg failed.")
        return False

def main():
    parser = argparse.ArgumentParser(description="X to Reel MVP")
    parser.add_argument("--accounts", type=str)
    parser.add_argument("--config", type=str, default="config/x_accounts.json")
    parser.add_argument("--provider", type=str, default="auto", choices=["manual-json", "x-api", "gallery-dl", "browser-download", "auto"])
    parser.add_argument("--input-json", type=str)
    parser.add_argument("--max-posts-per-account", type=int, default=20)
    parser.add_argument("--top", type=int, default=3)
    parser.add_argument("--min-score", type=int, default=0)
    parser.add_argument("--days-back", type=int, default=2)
    parser.add_argument("--overwrite", action="store_true", default=False)
    parser.add_argument("--open", action="store_true", default=False)
    parser.add_argument("--open-best", action="store_true", default=False)
    parser.add_argument("--cookies-from-browser", type=str)
    parser.add_argument("--output-dir", type=str, default="runtime/x_reels")
    parser.add_argument("--duration-seconds", type=int, default=8)
    parser.add_argument("--python-executable", type=str, default=sys.executable)
    parser.add_argument("--summary-json", type=str)
    parser.add_argument("--dry-run", action="store_true", default=False)
    
    args = parser.parse_args()

    provider = args.provider
    if args.input_json:
        provider = "manual-json"
    elif provider == "auto":
        if os.environ.get("X_BEARER_TOKEN"):
            provider = "x-api"
        elif args.accounts:
            print("To fetch real accounts automatically, set X_BEARER_TOKEN or use a valid provider.")
            sys.exit(1)
        else:
            print("No --input-json or --accounts or X_BEARER_TOKEN provided.")
            sys.exit(1)

    posts = []
    if provider == "manual-json":
        if not args.input_json:
            print("--input-json required for manual-json provider.")
            sys.exit(1)
        posts = load_posts_from_json(args.input_json)
    elif provider == "x-api":
        print("X API provider is not fully implemented in MVP yet. Falling back/failing...")
        sys.exit(1)
    else:
        print(f"Provider {provider} not fully implemented in MVP. Please use --input-json for guaranteed fallback.")
        sys.exit(1)

    for p in posts:
        score, sph = calculate_score(p)
        p["score"] = score
        p["score_per_hour"] = sph

    valid_posts = [p for p in posts if p.get("score", 0) >= args.min_score]
    valid_posts.sort(key=lambda x: x.get("score_per_hour", 0), reverse=True)
    top_posts = valid_posts[:args.top]

    if args.dry_run:
        print("Dry run complete. Found posts:")
        for p in top_posts:
            print(f"- {p.get('post_id')} (score: {p.get('score')})")
        return

    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    output_dir = Path(args.output_dir)
    manifest = {
        "generated_at": datetime.datetime.now().isoformat(),
        "account_handles": args.accounts.split(",") if args.accounts else [],
        "selected_posts": [],
        "errors": []
    }

    best_reel_path = None

    for idx, post in enumerate(top_posts):
        post_id = post.get("post_id", "unknown")
        post_dir = output_dir / date_str / post_id

        if post_dir.exists() and not args.overwrite:
            print(f"Skipping {post_id}, already exists.")
            continue

        post_dir.mkdir(parents=True, exist_ok=True)
        (post_dir / "source_media").mkdir(exist_ok=True)

        card_path = post_dir / "card.png"
        reel_path = post_dir / "reel.mp4"
        caption_path = post_dir / "caption.txt"
        metadata_path = post_dir / "metadata.json"
        report_path = post_dir / "preview_report.md"

        create_card_image(post, card_path)
        
        has_mp4 = False
        if shutil.which("ffmpeg"):
            has_mp4 = generate_mp4(card_path, reel_path, args.duration_seconds)
        else:
            manifest["errors"].append("ffmpeg not found, couldn't generate MP4")

        caption_text = f"ECONOMIKA - señal detectada.\nFuente: @{post.get('account_handle', '')}\nURL: {post.get('url', '')}\n\n{extract_titular(post.get('text', ''))}"
        caption_path.write_text(caption_text, encoding="utf-8")

        meta = {
            "post_id": post_id,
            "account_handle": post.get("account_handle", ""),
            "source_url": post.get("url", ""),
            "text": post.get("text", ""),
            "created_at": post.get("created_at", ""),
            "like_count": post.get("like_count", 0),
            "repost_count": post.get("repost_count", 0),
            "reply_count": post.get("reply_count", 0),
            "quote_count": post.get("quote_count", 0),
            "score": post.get("score", 0),
            "score_per_hour": post.get("score_per_hour", 0),
            "media_downloaded": False,
            "media_paths": [],
            "reel_path": str(reel_path.absolute()) if has_mp4 else "",
            "card_path": str(card_path.absolute())
        }
        metadata_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        report_text = f"# X to Reel Preview\n\n" \
                      f"* Post ID: {post_id}\n" \
                      f"* Account: {post.get('account_handle', '')}\n" \
                      f"* Score: {post.get('score', 0)}\n" \
                      f"* Score per hour: {post.get('score_per_hour', 0):.2f}\n" \
                      f"* Source URL: {post.get('url', '')}\n" \
                      f"* Reel path: {reel_path.absolute() if has_mp4 else 'Not generated'}\n" \
                      f"* Caption path: {caption_path.absolute()}\n" \
                      f"* Media status: Not downloaded\n\n" \
                      f"## Caption\n\n" \
                      f"<caption>\n{caption_text}\n</caption>\n\n" \
                      f"## Manual Upload Checklist\n\n" \
                      f"* [ ] Watch reel.mp4\n" \
                      f"* [ ] Copy caption.txt\n" \
                      f"* [ ] Upload manually to TikTok\n" \
                      f"* [ ] Upload manually to Instagram Reels\n" \
                      f"* [ ] Upload manually to YouTube Shorts\n"
        report_path.write_text(report_text, encoding="utf-8")

        manifest["selected_posts"].append({
            "post_id": post_id,
            "score": post.get("score"),
            "reel_path": str(reel_path) if has_mp4 else ""
        })

        if idx == 0 and has_mp4:
            best_reel_path = reel_path

    manifest_path = output_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if args.summary_json:
        Path(args.summary_json).write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if args.open and output_dir.exists():
        if sys.platform == "win32":
            os.startfile(output_dir)

    if args.open_best and best_reel_path and best_reel_path.exists():
        if sys.platform == "win32":
            os.startfile(best_reel_path)

if __name__ == "__main__":
    main()
