import requests
import time
import os
import json
import re

# Configuration for API
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config_api.json")

def upload_to_temporary_host(file_path):
    """Uploads a file to a temporary hosting (tmpfiles.org) to get a DIRECT public URL."""
    print(f"[INFO] Uploading {os.path.basename(file_path)} to temporary host...")
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            # Using tmpfiles.org which is more reliable for direct links
            response = requests.post('https://tmpfiles.org/api/v1/upload', files=files)
            data = response.json()
            if 'data' in data and 'url' in data['data']:
                url = data['data']['url']
                # Transform to direct download link: tmpfiles.org/XXXX -> tmpfiles.org/dl/XXXX
                direct_url = url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                print(f"[SUCCESS] Direct Temp URL: {direct_url}")
                return direct_url
    except Exception as e:
        print(f"[ERROR] Temporary upload failed: {e}")
    return None

def save_config(app_id, app_secret, access_token, ig_user_id):
    config = {
        "app_id": app_id,
        "app_secret": app_secret,
        "access_token": access_token,
        "ig_user_id": ig_user_id
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return None

def get_instagram_user_id(access_token):
    """Retrieves the Instagram User ID associated with the access token."""
    url = f"https://graph.instagram.com/me?fields=id,username&access_token={access_token}"
    response = requests.get(url)
    data = response.json()
    if "id" in data:
        return data["id"]
    else:
        print(f"[ERROR] Could not get IG User ID: {data}")
        return None

def upload_reel(video_url, caption, access_token, ig_user_id, scheduled_publish_time=None):
    """
    Uploads a Reel to Instagram. 
    If scheduled_publish_time is provided (Unix timestamp), uses Instagram's native scheduling.
    Note: Video must be publicly accessible via URL for Instagram to download it.
    """
    # Step 1: Initialize container
    url = f"https://graph.instagram.com/v22.0/{ig_user_id}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": access_token
    }
    
    # If scheduling, add the scheduled_publish_time parameter
    if scheduled_publish_time:
        payload["scheduled_publish_time"] = int(scheduled_publish_time)
        print(f"[INFO] Scheduling Reel for timestamp {scheduled_publish_time}...")
    else:
        print(f"[INFO] Initializing Reel upload for {ig_user_id}...")
    
    response = requests.post(url, data=payload)
    result = response.json()
    
    if "id" in result:
        creation_id = result["id"]
        print(f"[INFO] Container created: {creation_id}. Waiting for processing...")
        
        # Step 2: Check status
        status_url = f"https://graph.instagram.com/v22.0/{creation_id}?fields=status_code&access_token={access_token}"
        
        max_retries = 30
        for i in range(max_retries):
            time.sleep(10)
            status_res = requests.get(status_url).json()
            status = status_res.get("status_code")
            print(f"[INFO] Processing status: {status}")
            
            if status == "FINISHED":
                # Step 3: Publish (or confirm scheduling)
                publish_url = f"https://graph.instagram.com/v22.0/{ig_user_id}/media_publish"
                publish_payload = {
                    "creation_id": creation_id,
                    "access_token": access_token
                }
                final_res = requests.post(publish_url, data=publish_payload).json()
                
                if scheduled_publish_time:
                    print(f"[SUCCESS] Reel scheduled! ID: {final_res.get('id')}")
                else:
                    print(f"[SUCCESS] Reel published! ID: {final_res.get('id')}")
                return final_res
            elif status == "ERROR":
                print(f"[ERROR] Instagram processing failed: {status_res}")
                return None
        
        print("[ERROR] Timeout waiting for processing.")
    else:
        print(f"[ERROR] Failed to start upload: {result}")
    
    return None

# --- SCHEDULING LOGIC FOR SPAIN AUDIENCE ---
SCHEDULED_POSTS_FILE = os.path.join(os.path.dirname(__file__), "scheduled_posts.json")

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

def schedule_batch(posts_to_schedule):
    """
    Schedule a batch of posts on Instagram using native scheduling.
    Uses 30 min spacing by default, compresses if needed.
    UPLOADS to Instagram immediately with scheduled_publish_time - Instagram handles publishing.
    Returns list of scheduled times as strings.
    """
    from datetime import datetime, timedelta
    
    config = load_config()
    if not config:
        raise Exception("No se encontró configuración de API de Instagram")
    
    now = datetime.now()
    
    # Define today's active window
    today_start = now.replace(hour=ACTIVE_START_HOUR, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=ACTIVE_END_HOUR, minute=ACTIVE_END_MINUTE, second=0, microsecond=0)
    
    # Determine starting point - Instagram requires at least 10 minutes in the future
    min_future = now + timedelta(minutes=15)
    
    if now > today_end:
        # Too late today, start tomorrow
        next_slot = (now + timedelta(days=1)).replace(hour=ACTIVE_START_HOUR, minute=0, second=0, microsecond=0)
        window_end = next_slot.replace(hour=ACTIVE_END_HOUR, minute=ACTIVE_END_MINUTE)
    elif now < today_start:
        next_slot = today_start
        window_end = today_end
    else:
        # During active hours, start from now + 15 min (Instagram minimum)
        next_slot = min_future
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
    
    # Load existing to merge
    existing = load_scheduled_posts()
    
    for i, post in enumerate(posts_to_schedule):
        # Convert datetime to Unix timestamp
        unix_timestamp = int(next_slot.timestamp())
        
        print(f"[INFO] Uploading post {i+1}/{num_posts} scheduled for {next_slot.strftime('%H:%M')}...")
        
        try:
            # Upload video to temp host
            temp_url = upload_to_temporary_host(post['reel_path'])
            if not temp_url:
                print(f"[ERROR] Failed to upload {post['reel_path']}")
                continue
            
            # Upload to Instagram with scheduled time
            result = upload_reel(
                temp_url, 
                post['caption'], 
                config['access_token'], 
                config['ig_user_id'],
                scheduled_publish_time=unix_timestamp
            )
            
            if result and "id" in result:
                time_str = next_slot.strftime("%Y-%m-%d %H:%M")
                scheduled_times.append(time_str)
                
                # Save locally for GUI tracking
                existing.append({
                    'id': result['id'],
                    'scheduled_time': next_slot.isoformat(),
                    'caption': post['caption'][:50] + "...",
                    'status': 'scheduled_on_ig'
                })
            
        except Exception as e:
            print(f"[ERROR] Failed to schedule post: {e}")
        
        # Move to next slot
        next_slot = next_slot + timedelta(minutes=actual_spacing)
        
        # Small delay to avoid rate limits
        if i < num_posts - 1:
            time.sleep(2)
    
    # Cleanup: remove posts scheduled more than 24 hours ago
    threshold = datetime.now() - timedelta(hours=24)
    existing = [p for p in existing if datetime.fromisoformat(p['scheduled_time']) > threshold]
    
    save_scheduled_posts(existing)
    
    print(f"[INFO] Successfully scheduled {len(scheduled_times)} posts on Instagram.")
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
