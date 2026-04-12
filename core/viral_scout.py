import json
import os
import time
import asyncio
import re
import random
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

from twikit import Client
from config.cookie_utils import netscape_to_dict
from datetime import datetime, timedelta
import feedparser
import httpx

# Configuration Files - in config/ and data/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNTS_FILE = os.path.join(BASE_DIR, "config", "accounts.json")
HISTORY_FILE = os.path.join(BASE_DIR, "data", "processed_history.json")
REJECTED_FILE = os.path.join(BASE_DIR, "data", "rejected_history.json")
COOKIES_FILE = os.path.join(BASE_DIR, "config", "x.com_cookies.txt")

class ViralScout:
    def __init__(self):
        self.accounts = self.load_accounts()
        self.history = self.load_history(HISTORY_FILE)
        self.rejected = self.load_history(REJECTED_FILE)
        self.client = Client('en-US')

    def load_accounts(self):
        if not os.path.exists(ACCOUNTS_FILE):
            default = {
                "wallstwolverine": 800000,
                "juanrallo": 1000000,
                "dlacalle": 950000,
                "elblogsalmon": 200000,
                "Santander_es": 300000
            }
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump(default, f, indent=4)
            return default
        with open(ACCOUNTS_FILE, 'r') as f:
            return json.load(f)

    def load_history(self, filepath):
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except:
            return []

    def save_list(self, filepath, data_list):
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(list(set(data_list)), f, indent=4) # Dedup on save
        except Exception as e:
            print(f"Error saving history to {filepath}: {e}")

    def is_processed(self, tweet_id):
        return str(tweet_id) in [str(x) for x in self.history] or str(tweet_id) in [str(x) for x in self.rejected]

    def mark_as_processed(self, tweet_id):
        if tweet_id not in self.history:
            self.history.append(tweet_id)
            self.save_list(HISTORY_FILE, self.history)

    def mark_as_rejected(self, tweet_id):
        if tweet_id not in self.rejected:
            self.rejected.append(tweet_id)
            self.save_list(REJECTED_FILE, self.rejected)

    async def _scan_async(self, hours_back=24, min_ratio=2.0, max_items=20, progress_callback=print, ignore_history=False, must_have_media=True):
        """
        Internal async scan using Twikit.
        Formula: (RTs * 4 + Likes) / (sqrt(Followers) * 2)
        Viral Threshold: > 2.0 (Endurecido de 1.0 a 2.0)
        """
        # CRITICAL: Reload history to ensure we have the latest processed items
        if not ignore_history:
            self.history = self.load_history(HISTORY_FILE)
            self.rejected = self.load_history(REJECTED_FILE)

        viral_urls = []
        
        # Use get_cookies which handles both env var (cloud) and file (local)
        from config.cookie_utils import get_cookies
        cookies = get_cookies()
        
        if not cookies:
            progress_callback("❌ Error: No se encontraron cookies (ni en archivo ni en env).")
            return []
            
        try:
            # Final Resolution for Domain Conflict: Inject cookies with explicit .x.com domain
            self.client = Client('en-US')
            
            from config.cookie_utils import netscape_to_json
            import json
            json_cookies_path = COOKIES_FILE.replace('.txt', '.json')
            netscape_to_json(COOKIES_FILE, json_cookies_path)
            
            if hasattr(self.client, '_session') and hasattr(self.client._session, 'cookies'):
                self.client._session.cookies.clear()
                cookie_dict = json.load(open(json_cookies_path, encoding='utf-8'))
                for k, v in cookie_dict.items():
                    # explicitly set domain to avoid `httpx` CookieConflictError 
                    # when Twitter's API replies with 'Domain=.x.com'
                    self.client._session.cookies.set(k, v, domain=".x.com")
                print(f"✅ Twikit cookies injected manually with explicitly set domain.")
            else:
                self.client.load_cookies(json_cookies_path)
                
        except Exception as e:
            progress_callback(f"❌ Error de cookies: {e}")
            # Do NOT return empty yet, we might fallback per account
            pass

        total_accounts = len(self.accounts)
        limit_date = datetime.now() - timedelta(hours=hours_back)
        progress_callback(f"📊 [SCOUT] Accounts to scan: {list(self.accounts.keys())}")
        
        for idx, (user_screen_name, _) in enumerate(self.accounts.items()):
            progress_callback(f"🔎 Scanning @{user_screen_name} ({idx+1}/{total_accounts})...")
            
            try:
                # 1. Get User Data (Fresh followers)
                # Small initial pause to avoid burst detection
                await asyncio.sleep(random.uniform(2, 4))
                
                user_data = None
                for attempt in range(2): # Retry mechanism (initial + 1 retry)
                    try:
                        user_data = await self.client.get_user_by_screen_name(user_screen_name)
                        user_id = user_data.id
                        followers = user_data.followers_count
                        break # Success
                    except Exception as e:
                        err_msg = str(e)
                        if "429" in err_msg:
                            progress_callback(f"   🛑 RATE LIMIT (429) en lookup! Enfriando 15 minutos...")
                            for i in range(15, 0, -1):
                                progress_callback(f"   ⏳ Quedan {i} minutos...")
                                await asyncio.sleep(60)
                            continue # Try next account or retry? User said continue if 429? Actually 429 needs cooling.
                        
                        if attempt == 0:
                            progress_callback(f"   ⚠️ Fallo lookup @{user_screen_name}, reintentando en 5s... ({err_msg})")
                            await asyncio.sleep(5)
                        else:
                            # Final failure for this account
                            if any(msg in err_msg for msg in ["404", "indices", "KEY_BYTE"]) or isinstance(e, KeyError):
                                progress_callback(f"   [WARN] Fallo scrapeando @{user_screen_name}: {err_msg}")
                                user_data = None # Mark as failed
                                break
                            else:
                                raise e # Unexpected error

                if not user_data:
                    # Try fallback to search if direct lookup fails definitely
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
                        else:
                            progress_callback(f"   ⚠️ No se encontró al usuario @{user_screen_name} ni vía búsqueda.")
                    except Exception as e2:
                        progress_callback(f"   ⚠️ Fallo total buscando a @{user_screen_name}: {e} | {e2}")
                    
                    # --- FALLBACK TO NITTER RSS ---
                    progress_callback(f"   🔄 Activando FALLBACK (Nitter RSS) para @{user_screen_name}...")
                    nitter_hits = await self._scan_nitter_rss(user_screen_name, limit_date, min_ratio, progress_callback)
                    if nitter_hits:
                        viral_urls.extend(nitter_hits)
                        continue
                    else:
                        continue

                # 2. Get Recent Tweets
                all_tweets = []
                try:
                    tweets = None
                    for attempt in range(2):
                        try:
                            tweets = await self.client.get_user_tweets(user_id, 'Tweets', count=40)
                            break
                        except Exception as e:
                            err_msg = str(e)
                            if attempt == 0:
                                progress_callback(f"   ⚠️ Fallo obteniendo tuits de @{user_screen_name}, reintentando en 5s... ({err_msg})")
                                await asyncio.sleep(5)
                            else:
                                if any(msg in err_msg for msg in ["404", "indices", "KEY_BYTE"]) or isinstance(e, KeyError):
                                    progress_callback(f"   [WARN] Fallo scrapeando @{user_screen_name} (Tweets): {err_msg}")
                                    break
                                else:
                                    raise e

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
                                # pylint: disable=bare-except
                                except: pass
                            
                            # Stop if we hit the date limit or a safety cap (e.g. 80 tweets)
                            if (isinstance(created_at, datetime) and created_at < limit_date) or len(all_tweets) > 80:
                                break
                            
                            try:
                                next_tweets = await tweets.next()
                                if not next_tweets:
                                    break
                                all_tweets.extend(next_tweets)
                                tweets = next_tweets
                                await asyncio.sleep(random.uniform(2, 5)) 
                            except Exception as e:
                                progress_callback(f"   ⚠️ Error en paginación para @{user_screen_name}: {e}")
                                break
                except Exception as e:
                    if "429" in str(e):
                        progress_callback(f"   🛑 RATE LIMIT (429)! Enfriando 15 minutos...")
                        for i in range(15, 0, -1):
                            progress_callback(f"   ⏳ Quedan {i} minutos...")
                            await asyncio.sleep(60)
                        continue
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
            except Exception as e:
                if "404" in str(e) or "lookup" in str(e).lower():
                    progress_callback(f"   🔄 Fallo Twikit (404/Lookup). Intentando Fallback Nitter RSS...")
                    nitter_hits = await self._scan_nitter_rss(user_screen_name, limit_date, min_ratio, progress_callback)
                    if nitter_hits:
                        viral_urls.extend(nitter_hits)
                else:
                    progress_callback(f"   ❌ Error inesperado con @{user_screen_name}: {e}")
                continue
            except BaseException as b_e:
                progress_callback(f"   🛑 ERROR CRÍTICO DE HILO (@{user_screen_name}): {b_e}")
                continue # Prevent thread from dying and crashing main process
            
            # Inter-account jittered delay to avoid detection
            if idx < total_accounts - 1:
                await asyncio.sleep(random.uniform(5, 12))
                
        # Sort by score descending
        viral_urls.sort(key=lambda x: x['score'], reverse=True)
        return viral_urls

    async def _scan_nitter_rss(self, user_screen_name, limit_date, min_ratio=2.0, progress_callback=print):
        """
        Fallback strategy using Nitter RSS feeds.
        Nitter provides RSS at https://nitter.net/[user]/rss
        """
        instances = ["nitter.net", "nitter.it", "nitter.cz", "nitter.default.ovh"]
        hits = []
        
        for instance in instances:
            rss_url = f"https://{instance}/{user_screen_name}/rss"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(rss_url)
                    if resp.status_code != 200: continue
                    
                    feed = feedparser.parse(resp.text)
                    if not feed.entries: continue
                    
                    progress_callback(f"      ✅ Éxito con {instance}. Parsing {len(feed.entries)} entradas...")
                    
                    for entry in feed.entries:
                        # Date check
                        published = entry.get('published_parsed')
                        if published:
                            pub_dt = datetime(*published[:6])
                            if pub_dt < limit_date: continue
                        
                        tweet_id = entry.link.split('/')[-1].split('#')[0]
                        if self.is_processed(tweet_id): continue
                        
                        # Nitter RSS often doesn't give raw stats easily.
                        # We extract them from the description if possible or set defaults.
                        # Description contains HTML.
                        desc = entry.get('description', '')
                        
                        # Extract metrics from Nitter description footer if present
                        # Usually: "r: 10, l: 20" or similar in some instances
                        reposts = 0
                        likes = 0
                        stats_match = re.search(r'(\d+)\s+reposts?,\s+(\d+)\s+favorites?', desc)
                        if stats_match:
                            reposts = int(stats_match.group(1))
                            likes = int(stats_match.group(2))
                        
                        # Since we don't have followers count here, we use a conservative score
                        # Or we assume a "medium" account size if unknown.
                        # For fallback, we lower the threshold slightly to ensure we get data.
                        score = (reposts * 2 + likes) / 100.0 # Normalized heuristic for RSS
                        
                        # Media check
                        has_video = "video" in desc or ".mp4" in desc
                        has_image = "img src" in desc
                        
                        if not (has_video or has_image): continue
                        
                        # Extract media URL
                        media_url = None
                        if has_video:
                            v_match = re.search(r'source src="([^"]+)"', desc)
                            if v_match: media_url = v_match.group(1)
                        elif has_image:
                            i_match = re.search(r'img src="([^"]+)"', desc)
                            if i_match: media_url = i_match.group(1)
                        
                        type_str = "VÍDEO 🎥" if has_video else "IMAGEN 🖼️"
                        
                        hits.append({
                            'url': entry.link.replace(instance, 'x.com'),
                            'score': score,
                            'reposts': reposts,
                            'likes': likes,
                            'user': user_screen_name,
                            'id': tweet_id,
                            'type': type_str,
                            'is_video': has_video,
                            'media_url': media_url,
                            'thumbnail': media_url if not has_video else None,
                            'description': entry.title
                        })
                    
                    if hits: break # Success with one instance is enough
            except Exception as e:
                continue
                
        return hits

    def scan(self, hours_back=24, min_ratio=2.0, max_items=20, progress_callback=print, ignore_history=False, must_have_media=True):
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
