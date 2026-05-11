import requests
import time
import os
import json
from typing import List, Dict, Optional
from utils.network import check_publishing_hub_health

# Configuration for Hub - Standardize on CENTRAL_PUBLISHING_HUB_URL
# Robust initialization: ensure /api/v1 is not duplicated
raw_url = os.environ.get("CENTRAL_PUBLISHING_HUB_URL", "http://localhost:8000").rstrip("/")
if "/api/v1" in raw_url:
    CENTRAL_HUB_BASE = raw_url.split("/api/v1")[0].rstrip("/")
else:
    CENTRAL_HUB_BASE = raw_url

# Endpoint definitions
HUB_API_V1 = f"{CENTRAL_HUB_BASE}/api/v1"

FAILED_POSTS_FILE = os.path.join("data", "failed_posts.json")
GRAPH_API_VERSION = os.environ.get("GRAPH_API_VERSION", "v22.0")
IG_MEDIA_PROCESSING_TIMEOUT_SECONDS = int(os.environ.get("IG_MEDIA_PROCESSING_TIMEOUT_SECONDS", "300"))
IG_MEDIA_PROCESSING_POLL_SECONDS = max(1, int(os.environ.get("IG_MEDIA_PROCESSING_POLL_SECONDS", "5")))

def _admin_headers() -> Dict[str, str]:
    api_key = os.environ.get("ECONOMIKA_ADMIN_API_KEY")
    return {"X-API-Key": api_key} if api_key else {}

def _normalize_platform(platform: str) -> str:
    return {
        "instagram": "instagram_reel",
        "facebook": "facebook_reel",
        "youtube": "youtube_shorts",
    }.get(platform, platform)

def _wait_for_ig_media_finished(creation_id: str, access_token: str):
    status_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{creation_id}"
    deadline = time.monotonic() + IG_MEDIA_PROCESSING_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        response = requests.get(
            status_url,
            params={"fields": "status_code", "access_token": access_token},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        status_code = payload.get("status_code")

        if status_code == "FINISHED":
            return payload
        if status_code == "ERROR":
            raise RuntimeError(f"Instagram media processing failed: {payload}")

        time.sleep(IG_MEDIA_PROCESSING_POLL_SECONDS)

    raise RuntimeError(f"Instagram media processing timed out for creation_id={creation_id}")

def _upload_to_ig(
    video_url: str,
    caption: str,
    access_token: str,
    ig_user_id: str,
    media_type: str = "REELS",
    location_id: Optional[str] = None,
):
    """Upload a public video URL to Instagram Graph API and publish it."""
    create_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_user_id}/media"
    payload = {
        "media_type": media_type,
        "video_url": video_url,
        "access_token": access_token,
    }
    if caption:
        payload["caption"] = caption
    if location_id:
        payload["location_id"] = location_id

    response = requests.post(create_url, data=payload, timeout=60)
    response.raise_for_status()
    creation = response.json()
    creation_id = creation.get("id")
    if not creation_id:
        raise RuntimeError(f"Instagram media creation failed: {creation}")

    _wait_for_ig_media_finished(creation_id, access_token)

    publish_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_user_id}/media_publish"
    publish_payload = {
        "creation_id": creation_id,
        "access_token": access_token,
    }
    publish_response = requests.post(publish_url, data=publish_payload, timeout=60)
    publish_response.raise_for_status()
    return publish_response.json()

def upload_reel(video_url: str, caption: str, access_token: str, ig_user_id: str, location_id: Optional[str] = None):
    return _upload_to_ig(video_url, caption, access_token, ig_user_id, media_type="REELS", location_id=location_id)

def upload_story(video_url: str, access_token: str, ig_user_id: str, location_id: Optional[str] = None):
    return _upload_to_ig(video_url, "", access_token, ig_user_id, media_type="STORIES", location_id=location_id)

def upload_facebook_reel(video_url: str, caption: str, access_token: str, fb_page_id: str):
    raise NotImplementedError("Facebook Reels direct publishing is not implemented in this module yet.")

def _queue_failed_post(payload: Dict, error: str):
    """Saves a failed post payload to a local JSON file for later retry."""
    os.makedirs("data", exist_ok=True)
    try:
        posts = []
        if os.path.exists(FAILED_POSTS_FILE):
            with open(FAILED_POSTS_FILE, "r", encoding="utf-8") as f:
                posts = json.load(f)
        
        payload["error_at_failure"] = error
        payload["timestamp"] = time.time()
        posts.append(payload)
        
        with open(FAILED_POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(posts, f, indent=4, ensure_ascii=False)
        print(f"[WARN] Post guardado en cola local: {FAILED_POSTS_FILE}")
    except Exception as e:
        print(f"[CRITICAL] No se pudo guardar en cola local: {e}")

def upload_to_temporary_host(file_path):
    """Uploads a file to catbox.moe to get a public URL for the Publishing Hub."""
    print(f"[INFO] Uploading {os.path.basename(file_path)} to catbox.moe...")
    url = "https://catbox.moe/user/api.php"
    for attempt in range(1, 4):
        try:
            with open(file_path, 'rb') as f:
                files = {'fileToUpload': f}
                data = {'reqtype': 'fileupload'}
                response = requests.post(url, files=files, data=data, timeout=300)
                if response.status_code == 200:
                    direct_url = response.text.strip()
                    if direct_url.startswith("http"):
                        print(f"[SUCCESS] Direct Catbox URL: {direct_url}")
                        return direct_url
        except Exception as e:
            print(f"[WARN] Catbox upload error (Attempt {attempt}): {e}")
        if attempt < 3: time.sleep(5)
    return None

def publish_video(video_path: str, caption: str, platform: str = "instagram", title: str = "Noticia"):
    """
    Main entry point for immediate publication.
    Delegates to the CentralPublishingHub via HTTP POST.
    """
    # Pre-flight check with auto-start
    if not check_publishing_hub_health(CENTRAL_HUB_BASE):
        print("[ERROR] CentralPublishingHub inaccesible. Procediendo a encolado local.")
        # We don't have the video_url yet, but we want to store the intention
        _queue_failed_post({"video_path": video_path, "caption": caption, "platform": platform, "title": title}, "Hub down")
        return {"status": "queued", "message": "Post queued locally (Hub down)"}

    video_url = upload_to_temporary_host(video_path)
    if not video_url:
        return {"status": "error", "message": "Failed to upload to Catbox"}

    payload = {
        "video_url": video_url,
        "caption": caption,
        "platforms": [_normalize_platform(platform)],
        "shorts_title": title,
        "account_id": "economika"
    }

    try:
        hub_api = f"{HUB_API_V1}/publish-now"
        print(f"[HUB] Sending project to {hub_api}...")
        response = requests.post(hub_api, json=payload, headers=_admin_headers(), timeout=60)
        return response.json()
    except Exception as e:
        print(f"[ERROR] Hub Publication Failed: {e}")
        _queue_failed_post(payload, str(e))
        return {"status": "queued", "message": f"Hub error, post queued: {str(e)}"}

def schedule_publication(video_path: str, caption: str, platform: str = "instagram", title: str = "Noticia", target_time: str = None):
    """
    Main entry point for scheduled publication.
    """
    if not check_publishing_hub_health(CENTRAL_HUB_BASE):
        _queue_failed_post({"video_path": video_path, "caption": caption, "platform": platform, "title": title, "sched": True}, "Hub down")
        return {"status": "queued", "message": "Post queued locally (Hub down)"}

    video_url = upload_to_temporary_host(video_path)
    if not video_url:
        return {"status": "error", "message": "Failed to upload to Catbox"}

    if not target_time:
        from datetime import datetime, timedelta, timezone
        from zoneinfo import ZoneInfo
        target_time = (datetime.now(ZoneInfo("Europe/Madrid")) + timedelta(hours=1)).astimezone(timezone.utc).isoformat()

    payload = {
        "posts": [
            {
                "video_url": video_url,
                "caption": caption,
                "target_time": target_time,
                "platforms": [_normalize_platform(platform)],
                "shorts_title": title,
                "account_id": "economika"
            }
        ]
    }

    try:
        hub_api = f"{HUB_API_V1}/schedule"
        print(f"[HUB] Scheduling project at {hub_api}...")
        response = requests.post(hub_api, json=payload, headers=_admin_headers(), timeout=60)
        return response.json()
    except Exception as e:
        print(f"[ERROR] Hub Scheduling Failed: {e}")
        _queue_failed_post(payload, str(e))
        return {"status": "queued", "message": f"Hub error, post queued: {str(e)}"}

def publish_now(video_path, caption, platforms, shorts_title="Noticia"):
    results = []
    for p in platforms:
        results.append(publish_video(video_path, caption, platform=p, title=shorts_title))
    return results[0] if results else {"status": "error"}
