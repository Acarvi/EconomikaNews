import json
import os
import time
import asyncio
import re
from typing import List, Dict, Optional, Any

def _get_stat(obj: Any, keys: list, default: int = 0) -> int:
    """Robustly extract a stat from an object or dict."""
    for key in keys:
        if isinstance(obj, dict):
            if key in obj: return obj[key] or 0
        else:
            val = getattr(obj, key, None)
            if val is not None: return val or 0
    return default
from twikit import Client
from config.cookie_utils import netscape_to_dict
from datetime import datetime, timedelta

# Configuration Files - in config/ and data/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNTS_FILE = os.path.join(BASE_DIR, "config", "accounts.json")
HISTORY_FILE = os.path.join(BASE_DIR, "data", "processed_history.json")
COOKIES_FILE = os.path.join(BASE_DIR, "config", "x.com_cookies.txt")

class ViralScout:
    def __init__(self):
        self.accounts = self.load_accounts()
        self.history = self.load_history()
        self.client = Client('en-US')

    def load_accounts(self):
        if not os.path.exists(ACCOUNTS_FILE):
            default = {
                "wallstwolverine": 800000,
                "unusual_whales": 1500000,
                "zerohedge": 1800000
            }
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump(default, f, indent=4)
            return default
        with open(ACCOUNTS_FILE, 'r') as f:
            return json.load(f)

    def load_history(self):
        if not os.path.exists(HISTORY_FILE):
            return []
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            return []

    def save_history(self):
        with open(HISTORY_FILE, 'w') as f:
            json.dump(self.history, f, indent=4)

    def is_processed(self, tweet_id):
        return tweet_id in self.history

    def mark_as_processed(self, tweet_id):
        if tweet_id not in self.history:
            self.history.append(tweet_id)
            self.save_history()

    async def _scan_async(self, hours_back=24, min_ratio=1.0, max_items=20, progress_callback=print, ignore_history=False, must_have_media=True):
        """
        Internal async scan using Twikit.
        Formula: (RTs * 4 + Likes) / (sqrt(Followers) * 2)
        Viral Threshold: > 1.0
        """
        viral_urls = []
        
        # Use get_cookies which handles both env var (cloud) and file (local)
        from config.cookie_utils import get_cookies
        cookies = get_cookies()
        
        if not cookies:
            progress_callback("❌ Error: No se encontraron cookies (ni en archivo ni en env).")
            return []
            
        try:
            self.client.set_cookies(cookies)
        except Exception as e:
            progress_callback(f"❌ Error de cookies: {e}")
            return []

        total_accounts = len(self.accounts)
        limit_date = datetime.now() - timedelta(hours=hours_back)
        progress_callback(f"📊 [SCOUT] Accounts to scan: {list(self.accounts.keys())}")
        
        for idx, (user_screen_name, _) in enumerate(self.accounts.items()):
            progress_callback(f"🔎 Scanning @{user_screen_name} ({idx+1}/{total_accounts})...")
            
            try:
                # 1. Get User Data (Fresh followers)
                try:
                    user_data = await self.client.get_user_by_screen_name(user_screen_name)
                    user_id = user_data.id
                    followers = user_data.followers_count
                except Exception as e:
                    # Fallback to search if direct lookup fails
                    try:
                        search_results = await self.client.search_user(user_screen_name)
                        if search_results:
                            # Try to find an exact match in results
                            matching_user = None
                            for u in search_results:
                                if u.screen_name.lower() == user_screen_name.lower():
                                    matching_user = u
                                    break
                            
                            if matching_user:
                                user_data = matching_user
                                user_id = user_data.id
                                followers = user_data.followers_count
                                progress_callback(f"   ℹ️ @{user_screen_name} encontrado vía búsqueda.")
                            else:
                                progress_callback(f"   ⚠️ No se encontró coincidencia exacta para @{user_screen_name}.")
                                continue
                        else:
                            progress_callback(f"   ⚠️ No se encontró al usuario @{user_screen_name} ni vía búsqueda: {e}")
                            continue
                    except Exception as e2:
                        progress_callback(f"   ⚠️ Fallo total buscando a @{user_screen_name}: {e} | {e2}")
                        continue

                # 2. Get Recent Tweets (with pagination for deep scan)
                try:
                    all_tweets = []
                    tweets = await self.client.get_user_tweets(user_id, 'Tweets', count=40)
                    if tweets:
                        all_tweets.extend(tweets)
                        
                        # Pagination loop to cover the full timeframe
                        while True:
                            last_tweet = all_tweets[-1]
                            created_at = last_tweet.created_at
                            if isinstance(created_at, str):
                                try:
                                    created_at = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
                                    created_at = created_at.replace(tzinfo=None)
                                except: pass
                            
                            # Stop if we hit the date limit or a safety cap (e.g. 150 tweets)
                            if (isinstance(created_at, datetime) and created_at < limit_date) or len(all_tweets) > 150:
                                break
                            
                            next_tweets = await tweets.next()
                            if not next_tweets:
                                break
                            all_tweets.extend(next_tweets)
                            tweets = next_tweets
                            await asyncio.sleep(1) # Safety delay
                except Exception as e:
                    progress_callback(f"   ⚠️ Error obteniendo tuits de @{user_screen_name}: {e}")
                    continue

                if not all_tweets: continue

                for tweet in all_tweets:
                    # Note: We include Retweets now as requested.
                    tweet_id = str(tweet.id)
                    
                    # Date Filter
                    created_at = tweet.created_at
                    if isinstance(created_at, str):
                        try:
                            created_at = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
                            created_at = created_at.replace(tzinfo=None)
                        except: pass
                    
                    if isinstance(created_at, datetime) and created_at < limit_date:
                        continue

                    # History Filter
                    if not ignore_history and self.is_processed(tweet_id):
                        continue
                    
                    # Media Check and URL extraction
                    has_video = False
                    has_media = hasattr(tweet, 'media') and tweet.media and len(tweet.media) > 0
                    media_url = None
                    thumbnail_url = None
                    
                    if must_have_media and not has_media:
                        continue
                    
                    if has_media:
                        first_media = tweet.media[0]
                        m_type = getattr(first_media, 'type', '')
                        
                        # Helper to find URL in various possible attributes
                        def find_media_url(obj):
                            for attr in ['media_url_https', 'media_url', 'display_url']:
                                val = getattr(obj, attr, None)
                                if val and isinstance(val, str) and val.startswith('http'):
                                    return val
                            return None

                        if m_type == 'video':
                            has_video = True
                            # Get best video URL
                            video_info = getattr(first_media, 'video_info', {})
                            if isinstance(video_info, dict):
                                variants = video_info.get('variants', [])
                                if variants:
                                    mp4s = [v for v in variants if v.get('content_type') == 'video/mp4']
                                    if mp4s:
                                        best_v = max(mp4s, key=lambda x: x.get('bitrate', 0))
                                        media_url = best_v.get('url')
                            thumbnail_url = find_media_url(first_media)
                        else:
                            # Photo
                            media_url = find_media_url(first_media)
                            thumbnail_url = media_url

                    # Extract Stats
                    reposts = _get_stat(tweet, ['retweet_count', 'repost_count', 'retweetCount'])
                    likes = _get_stat(tweet, ['favorite_count', 'like_count', 'favoriteCount'])
                    
                    # --- MATHEMATICAL VIRALITY FORMULA ---
                    if followers < 100: followers = 100 # Safety
                    denom = (followers ** 0.5) * 2
                    score = ((reposts * 4) + likes) / denom
                    
                    if score >= min_ratio:
                        type_str = "VÍDEO 🎥" if has_video else "IMAGEN 🖼️"
                        viral_urls.append({
                            'url': f"https://x.com/i/status/{tweet_id}",
                            'score': score,
                            'reposts': reposts,
                            'likes': likes,
                            'user': user_screen_name,
                            'id': tweet_id,
                            'type': type_str,
                            'is_video': has_video,
                            'media_url': media_url,
                            'thumbnail': thumbnail_url,
                            'description': getattr(tweet, 'full_text', getattr(tweet, 'text', ''))
                        })
                        progress_callback(f"   🔥 IMPACTO: {score:.1f} ({reposts} RTs, {likes} Likes) - {type_str}")
                
                await asyncio.sleep(1) # Pequeña pausa entre cuentas
                
            except Exception as e:
                progress_callback(f"   ❌ Error inesperado con @{user_screen_name}: {e}")
                continue
                
        # Sort by score descending
        viral_urls.sort(key=lambda x: x['score'], reverse=True)
        return viral_urls

    def scan(self, hours_back=24, min_ratio=1.0, max_items=20, progress_callback=print, ignore_history=False, must_have_media=True):
        """
        Sync wrapper for scan_async.
        """
        try:
            return asyncio.run(self._scan_async(hours_back, min_ratio, max_items, progress_callback, ignore_history, must_have_media))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self._scan_async(hours_back, min_ratio, max_items, progress_callback, ignore_history, must_have_media))

if __name__ == "__main__":
    scout = ViralScout()
    print("Test Scan...")
    hits = scout.scan(min_ratio=0.01) # Lower ratio for test
    print("Hits:", hits)
