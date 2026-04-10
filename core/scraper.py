"""
Scraper module for Twitter/X posts.
Uses yt-dlp to extract metadata and media URLs from tweets.
"""
import yt_dlp
import re
import os
import time
from typing import Optional, Dict, Any
import httpx

# --- DEFINTIVE MONKEY PATCH FOR HTTPX COOKIE CONFLICT ---
# This prevents the fatal 'Multiple cookies exist with name=twid' error.
try:
    _original_get = httpx.Cookies.get
    def _patched_get(self, name, default=None, domain=None, path=None):
        try:
            return _original_get(self, name, default, domain, path)
        except Exception as e:
            if "Multiple cookies exist" in str(e):
                # If a conflict occurs, return the first matching cookie instead of crashing
                for cookie in self.jar:
                    if cookie.name == name:
                        if domain is None or cookie.domain == domain:
                            if path is None or cookie.path == path:
                                return cookie.value
            return default
    httpx.Cookies.get = _patched_get
except Exception as e:
    print(f"Warning: Failed to patch httpx cookies: {e}")

def _get_stat(obj: Any, keys: list, default: int = 0) -> int:
    """Robustly extract a stat from an object or dict."""
    for key in keys:
        if isinstance(obj, dict):
            if key in obj: return obj[key] or 0
        else:
            val = getattr(obj, key, None)
            if val is not None: return val or 0
    return default

def extract_tweet_id(url: str) -> Optional[str]:
    """Extract the tweet ID from a Twitter/X URL."""
    patterns = [
        r'twitter\.com/\w+/status/(\d+)',
        r'x\.com/\w+/status/(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def scrape_tweet_with_browser(url: str) -> Optional[Dict[str, Any]]:
    """
    Robust fallback using Twikit search.
    """
    tweet_id = extract_tweet_id(url)
    if not tweet_id:
        return None
        
    try:
        from twikit import Client
        from config.cookie_utils import netscape_to_dict
        
        client = Client('en-US')
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cookie_file = os.path.join(base_dir, "config", "x.com_cookies.txt")
        
        if os.path.exists(cookie_file):
            from config.cookie_utils import netscape_to_json
            import json
            json_cookies = cookie_file.replace('.txt', '.json')
            netscape_to_json(cookie_file, json_cookies)
            
            if hasattr(client, '_session') and hasattr(client._session, 'cookies'):
                client._session.cookies.clear()
                cookie_dict = json.load(open(json_cookies, encoding='utf-8'))
                for k, v in cookie_dict.items():
                    client._session.cookies.set(k, v, domain=".x.com")
                print(f"✅ Scraper cookies injected manually with explicitly set domain.")
            else:
                client.load_cookies(json_cookies)
            
            import asyncio
            
            async def _fetch():
                try:
                    # search is often more robust than get_tweet_by_id when API changes occur
                    # We search for the specific tweet ID
                    # IMPORTANT: Use get_tweet_by_id for direct accuracy, search_tweet is fuzzy
                    try:
                        tweet = await client.get_tweet_by_id(tweet_id)
                    except Exception as e:
                        print(f"   [Twikit ID Lookup Error] {e}")
                        # Fallback to search if direct lookup fails
                        results = await client.search_tweet(f"status:{tweet_id}", 'Latest')
                        tweet = results[0] if results else None
                     
                    if not tweet:
                        return None
                        
                    full_text = getattr(tweet, 'full_text', getattr(tweet, 'text', ''))
                    
                    # Initialize defaults to prevent UnboundLocalError
                    media_url = None
                    is_video = False
                    
                    # Helper to find URL in various possible attributes
                    def find_media_url(obj):
                        for attr in ['media_url_https', 'media_url', 'display_url']:
                            val = getattr(obj, attr, None)
                            if val and isinstance(val, str) and val.startswith('http'):
                                return val
                        return None

                    if hasattr(tweet, 'media') and tweet.media:
                        first_media = tweet.media[0]
                        m_type = getattr(first_media, 'type', '')
                        if m_type == 'video':
                            is_video = True
                            video_info = getattr(first_media, 'video_info', {})
                            variants = video_info.get('variants', [])
                            if variants:
                                mp4s = [v for v in variants if v.get('content_type') == 'video/mp4']
                                if mp4s:
                                    best_v = max(mp4s, key=lambda x: x.get('bitrate', 0))
                                    media_url = best_v.get('url')
                            if not media_url: # fallback to thumbnail if video URL failed
                                media_url = find_media_url(first_media)
                        else:
                            # photo or other
                            is_video = False
                            media_url = find_media_url(first_media)
                    
                    # Final check: if we expected media but got none, return None to avoid corrupt flows
                    if not media_url:
                        print(f"   [Scraper] No se pudo extraer URL de media para {tweet_id}")
                        return None

                    # Robust user extraction
                    user_name = "Economika"
                    user_id = "economika"
                    if hasattr(tweet, 'user') and tweet.user:
                        user_name = getattr(tweet.user, 'name', user_name)
                        user_id = getattr(tweet.user, 'screen_name', user_id)
                                    
                    return {
                        'id': tweet_id,
                        'title': full_text[:100] + "..." if len(full_text) > 100 else full_text,
                        'description': full_text,
                        'uploader': user_name,
                        'uploader_id': user_id,
                        'thumbnail': media_url,
                        'url': media_url if is_video else None,
                        'media_url': media_url, # New field for clarity
                        'formats': [],
                        'duration': 10 if is_video else None,
                        'is_video': is_video,
                        'reposts': _get_stat(tweet, ['retweet_count', 'repost_count', 'retweetCount']),
                        'likes': _get_stat(tweet, ['favorite_count', 'like_count', 'favoriteCount']),
                    }
                except Exception as ex:
                    print(f"   [Twikit Search Fallback Error] {ex}")
                    import traceback
                    traceback.print_exc()
                    return None

            return asyncio.run(_fetch())
    except Exception as e:
        print(f"   [Scraper Fallback Error] {e}")
        
    return None

def scrape_tweet(url: str) -> Optional[Dict[str, Any]]:
    """
    Scrape tweet metadata using yt-dlp with fallback.
    """
    tweet_id = extract_tweet_id(url)
    if not tweet_id:
        print(f"[ERROR] Could not extract tweet ID from: {url}")
        return None

    # Silence yt-dlp completely
    import sys
    import io
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()  # Capture and discard stderr

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': False,
        'logger': type('QuietLogger', (), {'debug': lambda *a: None, 'warning': lambda *a: None, 'error': lambda *a: None})(),
    }

    try:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print(f"[INFO] Attempting to scrape with yt-dlp: {url}")
                info = ydl.extract_info(url, download=False)
                
                return {
                    'id': tweet_id,
                    'title': info.get('title', ''),
                    'description': info.get('description', ''),
                    'uploader': info.get('uploader', ''),
                    'uploader_id': info.get('uploader_id', ''),
                    'thumbnail': info.get('thumbnail'),
                    'url': info.get('url'),
                    'formats': info.get('formats', []),
                    'duration': info.get('duration'),
                    'is_video': info.get('duration') is not None and info.get('duration') > 0,
                    'reposts': _get_stat(info, ['retweet_count', 'repost_count', 'retweetCount']),
                    'likes': _get_stat(info, ['like_count', 'favorite_count', 'likeCount', 'view_count']),
                }
        except Exception as e:
            print(f"[WARNING] yt-dlp failed: {e}. Trying browser fallback...")
            return scrape_tweet_with_browser(url)
    finally:
        sys.stderr = old_stderr # Restore stderr

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = scrape_tweet(sys.argv[1])
        if result:
            print(f"Title: {result['title']}")
            print(f"Uploader: @{result['uploader_id']}")
            print(f"Is Video: {result['is_video']}")
            print(f"Stats: {result.get('reposts')} RTs, {result.get('likes')} Likes")
            print(f"Thumbnail: {result['thumbnail']}")
