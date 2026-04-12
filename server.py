import os
import sys

# --- SENTINEL API BOOTSTRAP ---
SENTINEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "SentinelAPI"))
if SENTINEL_PATH not in sys.path:
    sys.path.insert(0, SENTINEL_PATH)
try:
    from bootstrap import activate_security
    activate_security()
except ImportError:
    print("⚠️ Warning: SentinelAPI module not found. Proceeding with caution.")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from pydantic import BaseModel
import json
import os
import requests
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import asynccontextmanager

# --- LIFESPAN ---

scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern lifecycle management for FastAPI."""
    # STARTUP
    load_pending()
    load_queue()
    
    # Run scan every hour
    scheduler.add_job(
        run_viral_scan,
        trigger=IntervalTrigger(hours=1),
        id="viral_scout_hourly",
        replace_existing=True
    )
    
    # Process publishing queue every minute
    scheduler.add_job(
        process_publishing_queue,
        trigger=IntervalTrigger(minutes=1),
        id="publishing_queue_processor",
        replace_existing=True
    )
    
    # Keep-alive ping every 10 minutes
    scheduler.add_job(
        self_ping,
        trigger=IntervalTrigger(minutes=10),
        id="keep_alive_ping",
        replace_existing=True
    )

    # Run initial scan after 10 seconds of startup
    from datetime import timedelta
    scheduler.add_job(
        run_viral_scan,
        trigger='date',
        run_date=datetime.now() + timedelta(seconds=10),
        id="initial_scan",
        misfire_grace_time=3600
    )

    scheduler.start()
    print("🚀 [STARTUP] Scheduler started - Viral Scout (hourly) + Publishing Queue (every minute)", flush=True)
    
    yield
    
    # SHUTDOWN
    print("🛑 [SHUTDOWN] Shutting down scheduler...")
    scheduler.shutdown()

# Initialize FastAPI
app = FastAPI(
    title="Economika Viral Scout API",
    description="Backend for automated Twitter viral content scanning and scheduled publishing",
    version="2.0.0",
    lifespan=lifespan
)

# CORS for local client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data storage - moved to data/
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "pending_tweets.json")
QUEUE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "publishing_queue.json")
pending_tweets: List[Dict] = []
publishing_queue: List[Dict] = []
last_scan: Optional[datetime] = None

def load_pending():
    global pending_tweets
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            pending_tweets = json.load(f)

def save_pending():
    with open(DATA_FILE, 'w') as f:
        json.dump(pending_tweets, f, indent=2, default=str)

def load_queue():
    global publishing_queue
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, 'r') as f:
            publishing_queue = json.load(f)
            print(f"[STARTUP] Loaded {len(publishing_queue)} posts from queue file", flush=True)
    else:
        print(f"[STARTUP] No queue file found, starting fresh", flush=True)

def save_queue():
    with open(QUEUE_FILE, 'w') as f:
        json.dump(publishing_queue, f, indent=2, default=str)

def prune_old_tweets():
    """Remove tweets older than 24h from pending list."""
    global pending_tweets
    from datetime import timedelta
    initial_count = len(pending_tweets)
    threshold = (datetime.now() - timedelta(hours=24)).isoformat()
    
    # Ensure added_at exists
    for t in pending_tweets:
        if 'added_at' not in t: t['added_at'] = datetime.now().isoformat()
        
    pending_tweets = [t for t in pending_tweets if t.get('added_at', datetime.now().isoformat()) > threshold]
    if len(pending_tweets) < initial_count:
        print(f"  [TTL] Pruned {initial_count - len(pending_tweets)} old tweets.", flush=True)
        save_pending()

# --- ENDPOINTS ---

@app.get("/")
def root():
    """Root endpoint with API info."""
    now = datetime.now().isoformat()
    print(f"[{now}] 📥 Root access from client")
    return {
        "name": "Economika Viral Scout API",
        "status": "running",
        "pending_count": len(pending_tweets),
        "last_scan": last_scan.isoformat() if last_scan else None,
        "time": now
    }

@app.get("/health")
def health_check():
    """Health check endpoint for keep-alive pings."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/models")
def list_available_models():
    """Debug endpoint to list all available models for this API key."""
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not set"}
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        # Fix: New SDK uses .list() with an iterator
        models_iter = client.models.list()
        models_list = [m.name for m in models_iter]
        return {"available_models": models_list}
    except Exception as e:
        print(f"DEBUG ERROR: {e}")
        return {"error": str(e)}

@app.post("/pending/{tweet_id}/mark-processed")
def mark_processed_cloud(tweet_id: str):
    """Mark a tweet as processed (removes from pending and adds to history)."""
    global pending_tweets
    from core.viral_scout import ViralScout
    scout = ViralScout()
    scout.mark_as_processed(tweet_id)
    
    initial_count = len(pending_tweets)
    pending_tweets = [t for t in pending_tweets if t.get('id') != tweet_id]
    save_pending()
    
    return {"success": True, "remaining": len(pending_tweets)}

@app.post("/pending/{tweet_id}/mark-rejected")
def mark_rejected_cloud(tweet_id: str):
    """Mark a tweet as rejected (removes from pending and adds to rejected list)."""
    global pending_tweets
    from core.viral_scout import ViralScout
    scout = ViralScout()
    scout.mark_as_rejected(tweet_id)
    
    pending_tweets = [t for t in pending_tweets if t.get('id') != tweet_id]
    save_pending()
    
    return {"success": True, "remaining": len(pending_tweets)}

@app.get("/pending")
def get_pending():
    prune_old_tweets()
    return {"tweets": pending_tweets}

@app.post("/pending/clear")
def clear_all_pending():
    """Emergency clear of all pending tweets."""
    global pending_tweets
    count = len(pending_tweets)
    pending_tweets = []
    save_pending()
    return {"success": True, "cleared": count}

class ScanRequest(BaseModel):
    hours_back: int = 24
    min_ratio: float = 2.0

@app.post("/scan")
def trigger_scan(request: ScanRequest = ScanRequest()):
    """Manually trigger a viral scout scan."""
    print(f"[{datetime.now()}] 🔍 Manual scan triggered via API (Hours: {request.hours_back}, Ratio: {request.min_ratio})")
    run_viral_scan(hours_back=request.hours_back, min_ratio=request.min_ratio)
    return {"success": True, "pending_count": len(pending_tweets)}

class ScheduleRequest(BaseModel):
    posts: List[Dict]

@app.post("/schedule")
def schedule_posts_batch(request: ScheduleRequest):
    """Receive a batch of posts to schedule."""
    global publishing_queue
    
    new_posts = request.posts
    if not new_posts:
        return {"queued": 0}
        
    # Validation/Cleanup
    valid_count = 0
    for post in new_posts:
        if not post.get('video_url') or not post.get('target_time'):
            continue
            
        post['status'] = 'pending'
        post['added_at'] = datetime.now().isoformat()
        
        # Avoid duplicates (by video_url)
        if not any(p['video_url'] == post['video_url'] for p in publishing_queue):
            publishing_queue.append(post)
            valid_count += 1
            
    save_queue()
    print(f"[{datetime.now()}] 📥 /schedule received {len(new_posts)} posts. Queued: {valid_count}. Total in queue: {len(publishing_queue)}")
    return {"success": True, "queued": valid_count, "total_in_queue": len(publishing_queue)}
    
# ... (omitted sections)

def run_viral_scan(hours_back: int = 24, min_ratio: float = 1.2):
    """Run the viral scout and add new tweets to pending (with AI content generation)."""
    global pending_tweets, last_scan
    
    now = datetime.now().isoformat()
    print(f"[{now}] 🔍 [SCAN] Starting scheduled Viral Scout scan (Hours: {hours_back}, Ratio: {min_ratio})...", flush=True)
    
    try:
        from core.viral_scout import ViralScout
        scout = ViralScout()
        
        hits = scout.scan(
            hours_back=hours_back,
            min_ratio=min_ratio, 
            ignore_history=False,
            must_have_media=True,
            progress_callback=lambda msg: print(f"  [SCOUT] {msg}", flush=True)
        )
        
        print(f"[{datetime.now().isoformat()}] 📥 [SCAN] Scout returned {len(hits)} viral hits", flush=True)
        
        if hits:
            # Add new tweets (avoid duplicates)
            existing_ids = {t['id'] for t in pending_tweets}
            new_added = 0
            for h in hits:
                if h['id'] not in existing_ids:
                    pending_tweets.append(h)
                    new_added += 1
            
            # CRITICAL: Generate AI content for ANY pending tweet that doesn't have it
            # This fixes tweets that were added during the previous "404 error" phase
            ai_fixed = 0
            for i, tweet in enumerate(pending_tweets):
                if not tweet.get('headline'):
                    print(f"  🤖 Retrying AI generation for tweet {tweet.get('id')} ({i+1}/{len(pending_tweets)})...", flush=True)
                    ai_content = generate_ai_content(tweet.get('description', ''))
                    if ai_content:
                        tweet.update(ai_content)
                        ai_fixed += 1
            
            save_pending()
            
            # TTL Cleanup: Remove tweets older than 24h to keep the list fresh
            from datetime import timedelta
            initial_count = len(pending_tweets)
            now_dt = datetime.fromisoformat(now)
            threshold = (now_dt - timedelta(hours=24)).isoformat()
            
            # Add timestamp if missing
            for t in pending_tweets:
                if 'added_at' not in t: t['added_at'] = now
                
            pending_tweets = [t for t in pending_tweets if t.get('added_at', now) > threshold]
            if len(pending_tweets) < initial_count:
                print(f"  [TTL] Pruned {initial_count - len(pending_tweets)} old tweets.")
                save_pending()
            
            print(f"  ✅ Scan complete. Added: {new_added}, AI Fixed: {ai_fixed}. Total pending: {len(pending_tweets)}", flush=True)
        else:
            print("  🤷 No new viral tweets found.", flush=True)
        
        last_scan = datetime.now()
        
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ❌ [SCAN ERROR]: {e}", flush=True)
        import traceback
        traceback.print_exc()

def self_ping():
    """Ping itself to prevent Render from sleeping (free tier)."""
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        return
    
    try:
        health_url = f"{url.rstrip('/')}/health"
        response = requests.get(health_url, timeout=10)
        print(f"[{datetime.now()}] 💓 Self-ping: {health_url} -> {response.status_code}")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Self-ping error: {e}")

def process_publishing_queue():
    """Process the publishing queue - publish posts whose target time has passed."""
    global publishing_queue
    
    # CRITICAL: Use timezone-aware datetime to match client
    from datetime import timezone
    now = datetime.now(timezone.utc)
    print(f"[{now}] 🔍 Checking publishing queue... ({len(publishing_queue)} total posts)", flush=True)
    
    if not publishing_queue:
        return
    
    published_ids = []
    
    # Load config from environment variables (set in Render)
    config = {
        "access_token": os.environ.get("IG_ACCESS_TOKEN"),
        "ig_user_id": os.environ.get("IG_USER_ID"),
        "fb_page_id": os.environ.get("FB_PAGE_ID")
    }
    
    if not config["access_token"] or not config["ig_user_id"]:
        missing = []
        if not config["access_token"]: missing.append("IG_ACCESS_TOKEN")
        if not config["ig_user_id"]: missing.append("IG_USER_ID")
        print(f"[{now}] ⚠️  Publishing queue: Missing credentials in environment: {', '.join(missing)}", flush=True)
        return
    
    pending_count = sum(1 for p in publishing_queue if p.get("status") == "pending")
    print(f"[{now}] 📊 Queue status: {pending_count} pending posts", flush=True)
    
    for i, post in enumerate(publishing_queue):
        if post["status"] != "pending":
            continue
        
        try:
            target_time = datetime.fromisoformat(post["target_time"])
        except Exception as e:
            print(f"[{now}] ⚠️  Invalid target_time format for post {i}: {e}", flush=True)
            publishing_queue[i]["status"] = "error"
            continue
        
        time_until = (target_time - now).total_seconds()
        if time_until > 60:
            print(f"[{now}] ⏰ Post {i+1}: scheduled for {target_time.strftime('%H:%M')}, {int(time_until/60)} min remaining", flush=True)
        
        if now >= target_time:
            print(f"[{now}] 📤 Publishing queued post: {post['video_url'][:50]}...")
            try:
                from core.publisher import upload_reel, upload_story, upload_facebook_reel
                
                # Instagram Reel
                if "instagram_reel" in post["platforms"]:
                    result = upload_reel(
                        post["video_url"],
                        post["caption"],
                        config["access_token"],
                        config["ig_user_id"]
                    )
                    if result and "id" in result:
                        print(f"[{now}] ✅ IG Reel published! ID: {result['id']}")
                    else:
                        raise Exception(f"IG Reel failed: {result}")
                
                # Instagram Story
                if "instagram_story" in post["platforms"]:
                    upload_story(post["video_url"], config["access_token"], config["ig_user_id"])
                
                # Facebook Reel
                if "facebook_reel" in post["platforms"] and config["fb_page_id"]:
                    upload_facebook_reel(post["video_url"], post["caption"], config["access_token"], config["fb_page_id"])
                
                publishing_queue[i]["status"] = "published"
                publishing_queue[i]["published_at"] = now.isoformat()
                print(f"[{now}] ✅ Post {i+1} successfully published.")
                
            except Exception as e:
                print(f"[{now}] ❌ Publish error for post {i+1}: {e}")
                publishing_queue[i]["status"] = "error"
                publishing_queue[i]["error_details"] = str(e)
                publishing_queue[i]["last_retry"] = now.isoformat()
    
    # Clean up published posts older than 24 hours
    threshold = now.timestamp() - 86400
    publishing_queue = [
        p for p in publishing_queue 
        if p["status"] == "pending" or datetime.fromisoformat(p.get("added_at", now.isoformat())).timestamp() > threshold
    ]
    save_queue()

# --- RUN ---

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
