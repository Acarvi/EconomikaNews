"""
Economika Cloud Server - FastAPI Backend
Runs on Render (free tier) with scheduled Viral Scout scanning.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import json
import os
from datetime import datetime
from typing import List, Dict, Optional

# Initialize FastAPI
app = FastAPI(
    title="Economika Viral Scout API",
    description="Backend for automated Twitter viral content scanning",
    version="1.0.0"
)

# CORS for local client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data storage (in-memory + file persistence)
DATA_FILE = "pending_tweets.json"
pending_tweets: List[Dict] = []
last_scan: Optional[datetime] = None

def load_pending():
    global pending_tweets
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            pending_tweets = json.load(f)

def save_pending():
    with open(DATA_FILE, 'w') as f:
        json.dump(pending_tweets, f, indent=2, default=str)

# Load on startup
load_pending()

# --- ENDPOINTS ---

@app.get("/")
def root():
    """Root endpoint with API info."""
    return {
        "name": "Economika Viral Scout API",
        "status": "running",
        "pending_count": len(pending_tweets),
        "last_scan": last_scan.isoformat() if last_scan else None
    }

@app.get("/health")
def health_check():
    """Health check endpoint for keep-alive pings."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/pending")
def get_pending():
    """Get all pending viral tweets."""
    return {
        "count": len(pending_tweets),
        "tweets": pending_tweets,
        "last_scan": last_scan.isoformat() if last_scan else None
    }

@app.post("/pending/{tweet_id}/mark-processed")
def mark_processed(tweet_id: str):
    """Mark a tweet as processed (removes from pending)."""
    global pending_tweets
    initial_count = len(pending_tweets)
    pending_tweets = [t for t in pending_tweets if t.get('id') != tweet_id]
    save_pending()
    
    if len(pending_tweets) < initial_count:
        return {"success": True, "remaining": len(pending_tweets)}
    raise HTTPException(status_code=404, detail="Tweet not found")

@app.post("/scan")
def trigger_scan():
    """Manually trigger a viral scout scan."""
    run_viral_scan()
    return {"success": True, "pending_count": len(pending_tweets)}

@app.delete("/pending")
def clear_pending():
    """Clear all pending tweets."""
    global pending_tweets
    pending_tweets = []
    save_pending()
    return {"success": True}

# --- SCHEDULED VIRAL SCOUT ---

def run_viral_scan():
    """Run the viral scout and add new tweets to pending."""
    global pending_tweets, last_scan
    
    print(f"[{datetime.now()}] Running scheduled Viral Scout scan...")
    
    try:
        from viral_scout import ViralScout
        scout = ViralScout()
        
        hits = scout.scan(
            hours_back=24,
            min_ratio=1.0,
            ignore_history=False,
            must_have_media=True,
            progress_callback=lambda msg: print(f"  {msg}")
        )
        
        if hits:
            # Add new tweets (avoid duplicates)
            existing_ids = {t['id'] for t in pending_tweets}
            new_tweets = [h for h in hits if h['id'] not in existing_ids]
            
            pending_tweets.extend(new_tweets)
            save_pending()
            
            # Mark as processed in local history
            for h in hits:
                scout.mark_as_processed(h['id'])
            
            print(f"  ✅ Added {len(new_tweets)} new tweets. Total pending: {len(pending_tweets)}")
        else:
            print("  🤷 No new viral tweets found.")
        
        last_scan = datetime.now()
        
    except Exception as e:
        print(f"  ❌ Scan error: {e}")

def self_ping():
    """Ping itself to prevent Render from sleeping (free tier)."""
    # RENDER_EXTERNAL_URL is automatically set by Render
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        return
    
    try:
        import requests
        health_url = f"{url.rstrip('/')}/health"
        response = requests.get(health_url, timeout=10)
        print(f"[{datetime.now()}] 💓 Self-ping: {health_url} -> {response.status_code}")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Self-ping error: {e}")

# --- SCHEDULER ---

scheduler = BackgroundScheduler()

@app.on_event("startup")
def start_scheduler():
    """Start the background scheduler on app startup."""
    # Run scan every hour
    scheduler.add_job(
        run_viral_scan,
        trigger=IntervalTrigger(hours=1),
        id="viral_scout_hourly",
        replace_existing=True
    )
    scheduler.start()
    print("🚀 Scheduler started - Viral Scout will run every hour")
    
    # Run initial scan after 30 seconds (give time for server to fully start)
    scheduler.add_job(
        run_viral_scan,
        trigger='date',
        run_date=datetime.now().replace(second=30),
        id="initial_scan"
    )

    # Keep-alive ping every 10 minutes
    scheduler.add_job(
        self_ping,
        trigger=IntervalTrigger(minutes=10),
        id="keep_alive_ping",
        replace_existing=True
    )

@app.on_event("shutdown")
def shutdown_scheduler():
    """Gracefully shutdown the scheduler."""
    scheduler.shutdown()

# --- RUN ---

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
