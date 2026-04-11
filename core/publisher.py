import requests
import time
import os
import json
from typing import List, Dict, Optional

# Configuration for Hub - Standardize on CENTRAL_PUBLISHING_HUB_URL
# Default to localhost:8000 for development compatibility
CENTRAL_HUB_URL = os.environ.get("CENTRAL_PUBLISHING_HUB_URL", "http://localhost:8000").rstrip("/")

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
    video_url = upload_to_temporary_host(video_path)
    if not video_url:
        return {"status": "error", "message": "Failed to upload to Catbox"}

    payload = {
        "video_url": video_url,
        "caption": caption,
        "platforms": [platform], # Wrap in list for Hub compatibility
        "shorts_title": title,
        "account_id": "economika"
    }

    try:
        # Use Hub's /api/v1/publish-now endpoint
        hub_api = f"{CENTRAL_HUB_URL}/api/v1/publish-now"
        print(f"[HUB] Sending project to {hub_api}...")
        response = requests.post(hub_api, json=payload, timeout=60)
        return response.json()
    except Exception as e:
        print(f"[ERROR] Hub Publication Failed: {e}")
        return {"status": "error", "message": f"Hub unreachable: {str(e)}"}

def schedule_publication(video_path: str, caption: str, platform: str = "instagram", title: str = "Noticia", target_time: str = None):
    """
    Main entry point for scheduled publication.
    Delegates to the CentralPublishingHub via HTTP POST to /api/v1/schedule.
    """
    video_url = upload_to_temporary_host(video_path)
    if not video_url:
        return {"status": "error", "message": "Failed to upload to Catbox"}

    # Default to 1 hour from now if not specified
    if not target_time:
        from datetime import datetime, timedelta
        target_time = (datetime.now() + timedelta(hours=1)).isoformat()

    payload = {
        "posts": [
            {
                "video_url": video_url,
                "caption": caption,
                "target_time": target_time,
                "platforms": [platform],
                "shorts_title": title,
                "account_id": "economika"
            }
        ]
    }

    try:
        hub_api = f"{CENTRAL_HUB_URL}/api/v1/schedule"
        print(f"[HUB] Scheduling project at {hub_api}...")
        response = requests.post(hub_api, json=payload, timeout=60)
        return response.json()
    except Exception as e:
        print(f"[ERROR] Hub Scheduling Failed: {e}")
        return {"status": "error", "message": f"Hub unreachable: {str(e)}"}

# Legacy aliases for backward compatibility if needed within core
def publish_now(video_path, caption, platforms, shorts_title="Noticia"):
    # Bridge to the new unified publish_video for each platform
    results = []
    for p in platforms:
        results.append(publish_video(video_path, caption, platform=p, title=shorts_title))
    return results[0] if results else {"status": "error"}
