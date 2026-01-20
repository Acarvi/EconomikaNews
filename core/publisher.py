import requests
import time
import os
import json
import re

# Configuration for API - in config/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "config", "config_api.json")

def upload_to_temporary_host(file_path):
    """Uploads a file to catbox.moe to get a PERMANENT (or long-term) public URL."""
    print(f"[INFO] Uploading {os.path.basename(file_path)} to catbox.moe...")
    try:
        # Catbox API: https://catbox.moe/faq.php
        # No login required for guest uploads
        url = "https://catbox.moe/user/api.php"
        with open(file_path, 'rb') as f:
            files = {
                'fileToUpload': f
            }
            data = {
                'reqtype': 'fileupload'
            }
            response = requests.post(url, files=files, data=data, timeout=60)
            
            if response.status_code == 200:
                direct_url = response.text.strip()
                if direct_url.startswith("http"):
                    print(f"[SUCCESS] Direct Catbox URL: {direct_url}")
                    return direct_url
                else:
                    print(f"[ERROR] Catbox returned unexpected response: {direct_url}")
            else:
                print(f"[ERROR] Catbox upload failed with status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[ERROR] Catbox upload failed: {e}")
    return None

def save_config(app_id=None, app_secret=None, access_token=None, ig_user_id=None, **kwargs):
    config = load_config() or {}
    if app_id: config["app_id"] = app_id
    if app_secret: config["app_secret"] = app_secret
    if access_token: config["access_token"] = access_token
    if ig_user_id: config["ig_user_id"] = ig_user_id
    
    # Merge additional kwargs (like fb_page_id, username)
    for k, v in kwargs.items():
        if v: config[k] = v

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return None

def get_instagram_user_id(access_token):
    """Retrieves the Instagram User ID associated with the access token."""
    if access_token and access_token.startswith("IGAA"):
        print("[ERROR] 🛑 TOKEN DE TIPO INCORRECTO DETECTADO.")
        print("[ERROR] Estás usando un token de 'Basic Display' (empieza por IGAA).")
        print("[ERROR] Necesitas un token de 'Instagram Graph API' (empieza por EAA).")
        print("[ERROR] Consulta el archivo GUIA_API_INSTAGRAM.md para obtener el correcto.")
        return None

    # Using graph.facebook.com is more reliable for Business/Graph tokens
    url = f"https://graph.facebook.com/v22.0/me?fields=id,username&access_token={access_token}"
    response = requests.get(url)
    data = response.json()
    if "id" in data:
        return data["id"]
    else:
        print(f"[ERROR] Could not get IG User ID: {data}")
        return None

def get_facebook_page_id(access_token):
    """Retrieves the Facebook Page ID associated with the access token."""
    url = f"https://graph.facebook.com/v22.0/me/accounts?access_token={access_token}"
    response = requests.get(url)
    data = response.json()
    if "data" in data and len(data["data"]) > 0:
        # Returns the first page found
        return data["data"][0]["id"]
    else:
        print(f"[ERROR] Could not get FB Page ID: {data}")
        return None

def upload_reel(video_url, caption, access_token, ig_user_id, scheduled_publish_time=None):
    """Uploads a Reel to Instagram."""
    return _upload_to_ig(video_url, caption, access_token, ig_user_id, "REELS", scheduled_publish_time)

def upload_story(video_url, access_token, ig_user_id):
    """Uploads a Story to Instagram (Note: Story scheduling is limited via API)."""
    # Stories don't have captions in the same way Reels do via API
    return _upload_to_ig(video_url, None, access_token, ig_user_id, "STORIES")

def _upload_to_ig(video_url, caption, access_token, ig_user_id, media_type, scheduled_publish_time=None):
    """Internal helper for IG uploads (Reels/Stories)."""
    # Validation
    if access_token and access_token.startswith("IGAA"):
        return {"error": {"message": "Invalid Token Type", "type": "TokenMismatch"}}

    # Step 0: Propagation wait
    time.sleep(5)

    # Step 1: Initialize container
    url = f"https://graph.facebook.com/v22.0/{ig_user_id}/media"
    payload = {
        "media_type": media_type,
        "video_url": video_url,
        "access_token": access_token
    }
    if caption:
        payload["caption"] = caption
    
    is_scheduled = scheduled_publish_time and media_type == "REELS"
    if is_scheduled:
        payload["scheduled_publish_time"] = int(scheduled_publish_time)
        print(f"[INFO] Scheduling IG {media_type} for timestamp {scheduled_publish_time}...")
    
    response = requests.post(url, data=payload)
    result = response.json()
    
    if "id" in result:
        creation_id = result["id"]
        print(f"[INFO] Container created: {creation_id}. Checking status...")
        status_url = f"https://graph.facebook.com/v22.0/{creation_id}?fields=status_code&access_token={access_token}"
        
        for i in range(30):
            time.sleep(10)
            try:
                status_res = requests.get(status_url).json()
                status = status_res.get("status_code")
                print(f"[INFO] IG {media_type} status: {status}")
                
                if status == "FINISHED":
                    # For SCHEDULED posts, Instagram will publish automatically at the scheduled time.
                    if is_scheduled:
                        print(f"[SUCCESS] IG {media_type} scheduled successfully! ID: {creation_id}")
                        return {"id": creation_id, "scheduled": True}
                    else:
                        # For immediate posts, call media_publish
                        publish_url = f"https://graph.facebook.com/v22.0/{ig_user_id}/media_publish"
                        publish_payload = {"creation_id": creation_id, "access_token": access_token}
                        publish_res = requests.post(publish_url, data=publish_payload).json()
                        if "id" in publish_res:
                            print(f"[SUCCESS] IG {media_type} published successfully!")
                        return publish_res
                elif status == "ERROR":
                    print(f"[ERROR] IG {media_type} container failed: {status_res}")
                    return None
            except Exception as e:
                print(f"[WARNING] Error checking status (retrying): {e}")
                continue
    else:
        print(f"[ERROR] Failed to create IG container: {json.dumps(result)}")
        if result.get("error", {}).get("code") == 3:
            print("[HINT] 💡 Error code 3: User must be on whitelist.")
            print("[HINT]    Como tu App ya está en 'Live Mode', Meta requiere 'Advanced Access'.")
            print("[HINT]    Ve a 'App Review' -> 'Permissions and Features'.")
            print("[HINT]    Busca 'instagram_content_publish' y pulsa 'Get Advanced Access'.")
            print("[HINT]    Haz lo mismo para 'pages_show_list' y 'pages_read_engagement'.")
    return None

def upload_facebook_reel(video_url, caption, access_token, page_id):
    """Uploads a Reel to a Facebook Page."""
    print(f"[INFO] Initializing Facebook Reel upload for Page {page_id}...")
    # Step 1: Initialize upload
    url = f"https://graph.facebook.com/v22.0/{page_id}/video_reels"
    payload = {
        "upload_phase": "start",
        "access_token": access_token
    }
    res = requests.post(url, data=payload).json()
    
    if "video_id" in res:
        video_id = res["video_id"]
        upload_url = res["upload_url"] # Usually not used this way for URL-based, but let's stick to simplest version
        
        # Facebook Page Video API for URL upload is simpler:
        fb_url = f"https://graph.facebook.com/v22.0/{page_id}/videos"
        fb_payload = {
            "file_url": video_url,
            "description": caption,
            "access_token": access_token
        }
        final_res = requests.post(fb_url, data=fb_payload).json()
        if "id" in final_res:
            print(f"[SUCCESS] Published to Facebook! ID: {final_res.get('id')}")
            return final_res
    return None

# --- SCHEDULING LOGIC FOR SPAIN AUDIENCE ---
SCHEDULED_POSTS_FILE = os.path.join(BASE_DIR, "data", "scheduled_posts.json")

# Spain Active Hours (local time, assuming CET/CEST)
ACTIVE_START_HOUR = 9   # 09:00
ACTIVE_END_HOUR = 23    # 23:30 max
ACTIVE_END_MINUTE = 30
DEFAULT_SPACING_MINUTES = 30  # Default 30 min between posts
MIN_SPACING_MINUTES = 5  # Absolute minimum to avoid rate limits

def load_scheduled_posts():
    if os.path.exists(SCHEDULED_POSTS_FILE):
        with open(SCHEDULED_POSTS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_scheduled_posts(posts):
    with open(SCHEDULED_POSTS_FILE, 'w') as f:
        json.dump(posts, f, indent=2, default=str)

def schedule_batch(posts_to_schedule, server_url=None):
    """
    The local script finishes immediately after sending; the server handles the wait times.
    If tweet_ids are provided, it will notify the server to mark them as processed.
    Returns list of scheduled times as strings.
    """
    from datetime import datetime, timedelta, timezone
    
    # Default server URL (can be overridden or set via env)
    if not server_url:
        server_url = os.environ.get("ECONOMIKA_SERVER_URL", "https://economikanoticias.onrender.com")
    
    config = load_config()
    if not config:
        raise Exception("No se encontró configuración de API de Instagram")
    
    # CRITICAL: Use timezone-aware datetime to avoid offset bugs
    # Server is in UTC, so we need to convert local time to UTC
    now = datetime.now(timezone.utc)
    
    # Define today's active window
    today_start = now.replace(hour=ACTIVE_START_HOUR, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=ACTIVE_END_HOUR, minute=ACTIVE_END_MINUTE, second=0, microsecond=0)
    
    # Determine starting point
    next_slot = now + timedelta(minutes=5)
    
    if now > today_end:
        next_slot = (now + timedelta(days=1)).replace(hour=ACTIVE_START_HOUR, minute=0, second=0, microsecond=0)
        window_end = next_slot.replace(hour=ACTIVE_END_HOUR, minute=ACTIVE_END_MINUTE)
    elif now < today_start:
        next_slot = today_start
        window_end = today_end
    else:
        window_end = today_end
    
    # Calculate spacing
    num_posts = len(posts_to_schedule)
    if num_posts == 0:
        return []
    
    available_minutes = (window_end - next_slot).total_seconds() / 60
    required_minutes = (num_posts - 1) * DEFAULT_SPACING_MINUTES
    
    if required_minutes <= available_minutes:
        actual_spacing = DEFAULT_SPACING_MINUTES
    else:
        if num_posts > 1:
            actual_spacing = max(MIN_SPACING_MINUTES, available_minutes / (num_posts - 1))
        else:
            actual_spacing = 0
        print(f"[INFO] Compressing spacing to {actual_spacing:.1f} min")
    
    scheduled_times = []
    batch_payload = []
    
    for i, post in enumerate(posts_to_schedule):
        print(f"[INFO] Uploading post {i+1}/{num_posts} to temp host...")
        
        try:
            # Upload video to temp host
            temp_url = upload_to_temporary_host(post['reel_path'])
            if not temp_url:
                print(f"[ERROR] Failed to upload {post['reel_path']}")
                continue
            
            target_time = next_slot.isoformat()
            scheduled_times.append(next_slot.strftime("%Y-%m-%d %H:%M"))
            
            batch_payload.append({
                "video_url": temp_url,
                "caption": post['caption'],
                "target_time": target_time,
                "platforms": ["instagram_reel", "instagram_story", "facebook_reel"]
            })
            
            print(f"[INFO] Post {i+1} queued for {next_slot.strftime('%H:%M')}")
            
        except Exception as e:
            print(f"[ERROR] Failed to prepare post: {e}")
        
        next_slot = next_slot + timedelta(minutes=actual_spacing)
    
    # Send batch to server
    if batch_payload:
        try:
            print(f"[INFO] Sending batch of {len(batch_payload)} posts to server...")
            response = requests.post(
                f"{server_url.rstrip('/')}/schedule",
                json={"posts": batch_payload},
                timeout=60 # Increased timeout for larger batches
            )
            if response.status_code == 200:
                result = response.json()
                print(f"[SUCCESS] Server queued {result.get('queued', 0)} posts. Total in queue: {result.get('total_in_queue', 0)}")
                
                # NEW: Notify server to remove these from pending
                for post in posts_to_schedule:
                    tweet_id = post.get('tweet_data', {}).get('id')
                    if tweet_id:
                        try:
                            requests.post(f"{server_url.rstrip('/')}/pending/{tweet_id}/mark-processed", timeout=10)
                            print(f"[INFO] Marked tweet {tweet_id} as processed in cloud.")
                        except:
                            print(f"[WARNING] Failed to mark tweet {tweet_id} as processed.")
            else:
                print(f"[ERROR] Server returned {response.status_code}: {response.text}")
        except Exception as e:
            print(f"[ERROR] Failed to send batch to server: {e}")
            print(f"[HINT] Make sure the server is running at {server_url}")
    
    print(f"[INFO] Successfully queued {len(scheduled_times)} posts for server-side publishing.")
    return scheduled_times

def run_scheduled_publisher():
    """
    Background worker that publishes scheduled posts when their time comes.
    Should be called periodically (e.g., via cron or a separate thread).
    """
    from datetime import datetime
    
    posts = load_scheduled_posts()
    now = datetime.now()
    config = load_config()
    
    if not config:
        print("[ERROR] No API config found for scheduled publishing.")
        return
    
    published = []
    
    for post in posts:
        if post['status'] != 'pending':
            continue
            
        scheduled_time = datetime.fromisoformat(post['scheduled_time'])
        
        if now >= scheduled_time:
            print(f"[INFO] Publishing scheduled post: {post['reel_path']}")
            try:
                temp_url = upload_to_temporary_host(post['reel_path'])
                if temp_url:
                    result = upload_reel(temp_url, post['caption'], config['access_token'], config['ig_user_id'])
                    if result and 'id' in result:
                        post['status'] = 'published'
                        post['ig_id'] = result['id']
                        published.append(post['reel_path'])
                    else:
                        post['status'] = 'failed'
                else:
                    post['status'] = 'failed'
            except Exception as e:
                print(f"[ERROR] Failed to publish: {e}")
                post['status'] = 'failed'
    
    save_scheduled_posts(posts)
    return published
