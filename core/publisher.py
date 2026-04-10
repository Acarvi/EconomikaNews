import requests
import time
import os
import json
from typing import List, Dict, Optional

# Configuration for Hub - in environment or default
CENTRAL_HUB_URL = os.environ.get("CENTRAL_HUB_URL", "http://localhost:8000")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "config", "config_api.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

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

def publish_now(video_path, caption, platforms: List[str], shorts_title: str = "Noticia"):
    """
    Publishes immediately using the CentralPublishingHub.
    Flow: Upload to Catbox -> Send URL to Hub.
    """
    video_url = upload_to_temporary_host(video_path)
    if not video_url:
        return {"status": "error", "message": "Failed to upload to Catbox"}

    payload = {
        "video_url": video_url,
        "caption": caption,
        "platforms": platforms,
        "shorts_title": shorts_title,
        "account_id": "economika"
    }

    try:
        response = requests.post(f"{CENTRAL_HUB_URL}/api/v1/publish-now", json=payload, timeout=60)
        return response.json()
    except Exception as e:
        print(f"[ERROR] Hub Publication Failed: {e}")
        return {"status": "error", "message": str(e)}

def schedule_batch(posts_to_schedule: List[Dict]):
    """
    Schedules multiple posts via the CentralPublishingHub.
    Each post in posts_to_schedule should have: reel_path, caption, target_time, platforms.
    """
    batch_posts = []
    for post in posts_to_schedule:
        print(f"[INFO] Preparing scheduled post: {os.path.basename(post['reel_path'])}")
        video_url = upload_to_temporary_host(post['reel_path'])
        if video_url:
            batch_posts.append({
                "video_url": video_url,
                "caption": post['caption'],
                "target_time": post['target_time'],
                "platforms": post.get('platforms', ["instagram_reel", "facebook_reel"]),
                "shorts_title": post.get('shorts_title', "Economika Noticia"),
                "account_id": "economika"
            })

    if not batch_posts:
        return {"status": "error", "message": "No posts could be prepared for scheduling"}

    try:
        response = requests.post(f"{CENTRAL_HUB_URL}/api/v1/schedule", json={"posts": batch_posts}, timeout=60)
        return response.json()
    except Exception as e:
        print(f"[ERROR] Hub Scheduling Failed: {e}")
        return {"status": "error", "message": str(e)}

def search_locations(query: str):
    """Proxies location search to the Hub."""
    try:
        response = requests.get(f"{CENTRAL_HUB_URL}/api/v1/locations", params={"q": query, "account_id": "economika"})
        return response.json().get("results", [])
    except Exception as e:
        print(f"[ERROR] Hub Location Search Failed: {e}")
        return []
