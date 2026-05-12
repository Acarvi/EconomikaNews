import json
import os
import time
import asyncio
import re
import random
import hashlib
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from services.discovery.models import XAccount
from services.discovery.x_sources import (
    BrowserXSource,
    TwikitXSource,
    get_stat as _get_stat,
    is_recoverable_twikit_error as _source_is_recoverable_twikit_error,
    is_schema_failure as _source_is_schema_failure,
)


def _is_recoverable_twikit_error(exc: Exception) -> bool:
    return _source_is_recoverable_twikit_error(exc)
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
import feedparser
import httpx

# Configuration Files - in config/ and data/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNTS_FILE = os.path.join(BASE_DIR, "config", "accounts.json")
HISTORY_FILE = os.path.join(BASE_DIR, "data", "processed_history.json")
REJECTED_FILE = os.path.join(BASE_DIR, "data", "rejected_history.json")
COOKIES_FILE = os.path.join(BASE_DIR, "config", "x.com_cookies.txt")
NEWS_SOURCES_FILE = os.path.join(BASE_DIR, "config", "news_sources.json")
DISCOVERY_MODES = {"manual", "rss", "x", "mixed"}
X_SCHEMA_FAILURE_LIMIT = 3

DEFAULT_NEWS_SOURCES = [
    {
        "name": "Libre Mercado",
        "url": "https://www.libertaddigital.com/libremercado/rss.xml"
    },
    {
        "name": "El Economista",
        "url": "https://www.eleconomista.es/rss/rss-economia.php"
    },
    {
        "name": "Expansión",
        "url": "https://e00-expansion.uecdn.es/rss/economia.xml"
    },
    {
        "name": "Investing España",
        "url": "https://es.investing.com/rss/news_14.rss"
    },
    {
        "name": "Libertad Digital Economía",
        "url": "https://www.libertaddigital.com/empresas/rss.xml"
    }
]

class ViralScout:
    def __init__(self):
        self.accounts = self.load_accounts()
        self.history = self.load_history(HISTORY_FILE)
        self.rejected = self.load_history(REJECTED_FILE)
        self.client = None
        self.twikit_source = TwikitXSource(processed_checker=self.is_processed)

    def get_discovery_mode(self, manual_urls: Optional[List[str]] = None) -> str:
        mode = os.environ.get("ECONOMIKA_DISCOVERY_MODE", "").strip().lower()
        if not mode:
            return "manual" if manual_urls else "x"
        return mode if mode in DISCOVERY_MODES else "x"

    def is_x_scout_enabled(self) -> bool:
        enabled = os.environ.get("ECONOMIKA_ENABLE_X_SCOUT")
        if enabled is None:
            return True
        return enabled.strip().lower() in {"1", "true", "yes", "on"}

    def get_x_source_mode(self) -> str:
        mode = os.environ.get("ECONOMIKA_X_SOURCE", "twikit").strip().lower()
        return mode if mode in {"twikit", "browser", "auto"} else "twikit"

    def build_x_accounts(self) -> List[XAccount]:
        return [
            XAccount(screen_name=screen_name, followers_hint=followers_hint)
            for screen_name, followers_hint in self.accounts.items()
        ]

    def build_manual_candidates(self, urls: List[str]) -> List[Dict[str, Any]]:
        candidates = []
        seen_urls = set()
        for url in urls:
            clean_url = (url or "").strip()
            if not clean_url or clean_url in seen_urls:
                continue
            seen_urls.add(clean_url)
            candidate_id = f"manual-{hashlib.sha1(clean_url.encode('utf-8')).hexdigest()[:16]}"
            candidates.append({
                "url": clean_url,
                "score": 1.0,
                "reposts": 0,
                "likes": 0,
                "user": "manual",
                "source": "manual",
                "id": candidate_id,
                "type": "MANUAL",
                "is_video": False,
                "media_url": None,
                "thumbnail": None,
                "description": clean_url
            })
        return candidates

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

    def load_news_sources(self):
        if not os.path.exists(NEWS_SOURCES_FILE):
            os.makedirs(os.path.dirname(NEWS_SOURCES_FILE), exist_ok=True)
            with open(NEWS_SOURCES_FILE, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_NEWS_SOURCES, f, ensure_ascii=False, indent=4)
            return DEFAULT_NEWS_SOURCES

        try:
            with open(NEWS_SOURCES_FILE, 'r', encoding='utf-8') as f:
                sources = json.load(f)
            if isinstance(sources, list):
                return sources
            if isinstance(sources, dict):
                return sources.get("sources", DEFAULT_NEWS_SOURCES)
        except Exception as e:
            print(f"Warning: Failed to load news sources: {e}")
        return DEFAULT_NEWS_SOURCES

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

    async def _scan_browser_x_source(self, max_items=20, progress_callback=print):
        progress_callback("Scanning X via experimental BrowserXSource...")
        source = BrowserXSource()
        candidates = await source.scan_accounts(
            self.build_x_accounts(),
            max_items=max_items,
            progress_callback=progress_callback,
        )
        return [candidate.to_dict() for candidate in candidates]

    def _write_x_debug_dump(self, user_screen_name: str, err_msg: str, exc: Exception, progress_callback=print):
        if os.environ.get("ECONOMIKA_DEBUG_X", "").strip().lower() not in {"1", "true", "yes", "on"}:
            return
        debug_dir = os.path.join(BASE_DIR, "debug")
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_user = re.sub(r"[^A-Za-z0-9_.-]", "_", user_screen_name)
        debug_path = os.path.join(debug_dir, f"x_response_{safe_user}_{timestamp}.txt")
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(f"USER: {user_screen_name}\n")
            f.write(f"ERROR: {err_msg}\n")
            f.write(f"EXCEPTION TYPE: {type(exc).__name__}\n")
            if hasattr(exc, 'response'):
                f.write(f"RESPONSE STATUS: {exc.response.status_code}\n")
                f.write(f"RESPONSE TEXT: {exc.response.text}\n")
        progress_callback(f"   [DEBUG] Dump guardado en {debug_path}")

    async def _scan_async(self, hours_back=24, min_ratio=2.0, max_items=20, progress_callback=print, ignore_history=False, must_have_media=True):
        """
        Internal async scan using Twikit.
        Formula: (RTs * 4 + Likes) / (sqrt(Followers) * 2)
        Viral Threshold: > 2.0 (Endurecido de 1.0 a 2.0)
        """
        discovery_mode = self.get_discovery_mode()
        progress_callback(f"Discovery mode: {discovery_mode}")

        if discovery_mode == "manual":
            progress_callback("Manual discovery mode: usando solo URLs introducidas por el usuario.")
            return []

        if discovery_mode == "rss":
            progress_callback("RSS/news mode selected explicitly.")
            return await self._scan_news_rss(
                hours_back=hours_back,
                max_items=max_items,
                progress_callback=progress_callback,
                ignore_history=ignore_history
            )

        if not self.is_x_scout_enabled():
            progress_callback("X Viral Scout disabled by ECONOMIKA_ENABLE_X_SCOUT=false.")
            if discovery_mode == "mixed":
                progress_callback("Mixed mode: X disabled, scanning RSS/news fallback.")
                return await self._scan_news_rss(
                    hours_back=hours_back,
                    max_items=max_items,
                    progress_callback=progress_callback,
                    ignore_history=ignore_history
                )
            return []

        # CRITICAL: Reload history to ensure we have the latest processed items
        if not ignore_history:
            self.history = self.load_history(HISTORY_FILE)
            self.rejected = self.load_history(REJECTED_FILE)

        viral_urls = []
        schema_failures = 0
        x_source_mode = self.get_x_source_mode()

        if x_source_mode == "browser":
            return await self._scan_browser_x_source(max_items=max_items, progress_callback=progress_callback)

        progress_callback("Scanning configured X accounts...")
        progress_callback(f"X source: {x_source_mode}")
        
        # Use get_cookies which handles both env var (cloud) and file (local)
        from config.cookie_utils import get_cookies
        cookies = get_cookies()
        
        if not cookies:
            progress_callback("No se encontraron cookies X/Twitter.")
            if discovery_mode == "mixed":
                progress_callback("Mixed mode: usando RSS/news fallback.")
                return await self._scan_news_rss(hours_back=hours_back, max_items=max_items, progress_callback=progress_callback, ignore_history=ignore_history)
            progress_callback("No se encontraron tuits virales. Prueba renovar cookies o usar modo mixed/rss.")
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
            if schema_failures >= X_SCHEMA_FAILURE_LIMIT:
                progress_callback("X/Twikit degraded: KEY_BYTE / urls schema error.")
                break

            progress_callback(f"🔎 Scanning @{user_screen_name} ({idx+1}/{total_accounts})...")
            
            try:
                # 1. Get User Data (Fresh followers)
                # Small initial pause to avoid burst detection
                await asyncio.sleep(random.uniform(2, 4))
                
                user_data = None
                last_lookup_error = None
                skip_twikit_for_account = False
                for attempt in range(2): # Retry mechanism (initial + 1 retry)
                    try:
                        user_data = await self.client.get_user_by_screen_name(user_screen_name)
                        user_id = user_data.id
                        followers = user_data.followers_count
                        break # Success
                    except Exception as e:
                        last_lookup_error = e
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
                            # Final failure for this account - INVESTIGACIÓN FORENSE
                            if user_screen_name.lower() == 'wallstwolverine' and os.environ.get("ECONOMIKA_DEBUG_X", "").strip().lower() in {"1", "true", "yes", "on"}:
                                debug_dir = os.path.join(BASE_DIR, "debug")
                                os.makedirs(debug_dir, exist_ok=True)
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                debug_path = os.path.join(debug_dir, f"x_response_{user_screen_name}_{timestamp}.txt")
                                with open(debug_path, "w", encoding="utf-8") as f:
                                    f.write(f"USER: {user_screen_name}\n")
                                    f.write(f"ERROR: {err_msg}\n")
                                    f.write(f"EXCEPTION TYPE: {type(e).__name__}\n")
                                    if hasattr(e, 'response'):
                                        f.write(f"RESPONSE STATUS: {e.response.status_code}\n")
                                        f.write(f"RESPONSE TEXT: {e.response.text}\n")
                                progress_callback(f"   [DEBUG] Dump guardado en {debug_path}")

                            if _is_recoverable_twikit_error(e):
                                progress_callback(f"   [WARN] Fallo scrapeando @{user_screen_name}: {err_msg}")
                                if self._is_schema_failure(e):
                                    schema_failures += 1
                                user_data = None # Mark as failed
                                skip_twikit_for_account = True
                                break
                            else:
                                raise e # Unexpected error

                if not user_data:
                    # Try fallback to search if direct lookup fails definitely
                    if skip_twikit_for_account:
                        pass
                    else:
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
                            progress_callback(f"   ⚠️ Fallo total buscando a @{user_screen_name}: {last_lookup_error} | {e2}")
                    
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
                    tweets_failed_recoverably = False
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
                                if _is_recoverable_twikit_error(e):
                                    progress_callback(f"   [WARN] Fallo scrapeando @{user_screen_name} (Tweets): {err_msg}")
                                    if self._is_schema_failure(e):
                                        schema_failures += 1
                                    tweets_failed_recoverably = True
                                    break
                                else:
                                    raise e

                    if tweets_failed_recoverably:
                        progress_callback(f"   Fallo Twikit ({err_msg}). Intentando Fallback Nitter RSS...")
                        nitter_hits = await self._scan_nitter_rss(user_screen_name, limit_date, min_ratio, progress_callback)
                        if nitter_hits:
                            viral_urls.extend(nitter_hits)
                        continue

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
                if _is_recoverable_twikit_error(e):
                    progress_callback(f"   🔄 Fallo Twikit ({e}). Intentando Fallback Nitter RSS...")
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
        if viral_urls:
            deduped = {}
            for item in viral_urls:
                url = item.get("url")
                if url and url not in deduped:
                    deduped[url] = item
            viral_urls = list(deduped.values())
            viral_urls.sort(key=lambda x: x['score'], reverse=True)
            return viral_urls[:max_items]

        if schema_failures >= X_SCHEMA_FAILURE_LIMIT:
            progress_callback("X/Twikit degraded: KEY_BYTE / urls schema error.")
            if x_source_mode == "auto":
                browser_hits = await self._scan_browser_x_source(max_items=max_items, progress_callback=progress_callback)
                if browser_hits:
                    return browser_hits[:max_items]

        if discovery_mode == "mixed":
            progress_callback("No se encontraron candidatos X/Nitter. Mixed mode: activando RSS/news fallback.")
            rss_hits = await self._scan_news_rss(
                hours_back=hours_back,
                max_items=max_items,
                progress_callback=progress_callback,
                ignore_history=ignore_history
            )
            return rss_hits[:max_items]

        progress_callback("No se encontraron tuits virales. Prueba renovar cookies o usar modo mixed/rss.")
        return []

    def _is_schema_failure(self, exc: Exception) -> bool:
        return _source_is_schema_failure(exc)

    async def _scan_nitter_rss(self, user_screen_name, limit_date, min_ratio=2.0, progress_callback=print):
        """
        Fallback strategy using Nitter RSS feeds with instance rotation.
        """
        instances = ['nitter.net', 'nitter.cz', 'nitter.poast.org', 'nitter.privacydev.net']
        hits = []
        failures = []
        progress_callback(f"      Probando fallback Nitter RSS para @{user_screen_name}...")

        for instance in instances:
            rss_url = f"https://{instance}/{user_screen_name}/rss"
            try:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    resp = await client.get(rss_url)
                    if resp.status_code != 200:
                        failures.append(f"{instance}: HTTP {resp.status_code}")
                        continue

                    feed = feedparser.parse(resp.text)
                    if not feed.entries:
                        failures.append(f"{instance}: sin entradas")
                        continue

                    progress_callback(f"      Nitter OK con {instance}: {len(feed.entries)} entradas.")

                    for entry in feed.entries:
                        published = entry.get('published_parsed')
                        if published:
                            pub_dt = datetime(*published[:6])
                            if pub_dt < limit_date:
                                continue

                        link = entry.get('link', '')
                        tweet_id = link.split('/')[-1].split('#')[0]

                        if not tweet_id:
                            continue
                        if self.is_processed(tweet_id):
                            continue

                        desc = entry.get('description', '')
                        reposts = 0
                        likes = 0

                        stats_match = re.search(r'(\d+)\s+(?:reposts?|r),?\s+(\d+)\s+(?:favorites?|f|likes?)', desc, re.I)
                        if stats_match:
                            reposts = int(stats_match.group(1))
                            likes = int(stats_match.group(2))

                        score = (reposts * 3 + likes) / 50.0

                        has_video = "video" in desc or ".mp4" in desc
                        has_image = "img src" in desc or "dc:image" in entry or "media_content" in entry

                        if not (has_video or has_image):
                            continue

                        media_url = None
                        if has_video:
                            v_match = re.search(r'source src="([^"]+)"', desc)
                            if v_match:
                                media_url = v_match.group(1)
                        elif has_image:
                            i_match = re.search(r'img src="([^"]+)"', desc)
                            if i_match:
                                media_url = i_match.group(1)

                        if not media_url and entry.get('media_content'):
                            media_url = entry.media_content[0].get('url')

                        type_str = "VIDEO" if has_video else "IMAGEN"

                        hits.append({
                            'url': f"https://x.com/{user_screen_name}/status/{tweet_id}",
                            'score': score,
                            'reposts': reposts,
                            'likes': likes,
                            'user': user_screen_name,
                            'id': tweet_id,
                            'type': type_str,
                            'is_video': has_video,
                            'media_url': media_url,
                            'thumbnail': media_url if not has_video else None,
                            'description': entry.get('title', '')
                        })

                    if hits:
                        progress_callback(f"      Nitter rescato {len(hits)} items.")
                        break
            except Exception as e:
                failures.append(f"{instance}: {e}")
                continue

        if not hits and failures:
            progress_callback(f"      Nitter sin resultados para @{user_screen_name} ({len(failures)} instancias fallidas).")

        return hits

    async def _scan_news_rss(self, hours_back=24, max_items=20, progress_callback=print, ignore_history=False):
        """
        Last-resort fallback using configured economy/news RSS feeds.
        """
        sources = self.load_news_sources()
        limit_date = datetime.now() - timedelta(hours=hours_back)
        hits = []
        seen_urls = set()
        progress_callback(f"   RSS noticias: probando {len(sources)} fuentes configuradas...")

        headers = {
            "User-Agent": "EconomikaNoticias ViralScout/1.0"
        }

        timeout = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            for source in sources:
                if isinstance(source, str):
                    source_name = source
                    source_url = source
                else:
                    source_name = source.get("name") or source.get("source") or source.get("url")
                    source_url = source.get("url") or source.get("feed_url")

                if not source_url:
                    continue

                try:
                    resp = await client.get(source_url)
                    if resp.status_code != 200:
                        continue

                    feed = feedparser.parse(resp.text)
                    entries = getattr(feed, "entries", [])
                    if not entries:
                        continue

                    for entry in entries:
                        link = entry.get("link") or entry.get("id")
                        title = (entry.get("title") or "").strip()
                        if not link or not title:
                            continue
                        clean_link = link.split("#")[0].strip()
                        if clean_link in seen_urls:
                            continue
                        seen_urls.add(clean_link)

                        published = entry.get("published_parsed") or entry.get("updated_parsed")
                        if published:
                            pub_dt = datetime(*published[:6])
                            if pub_dt < limit_date:
                                continue

                        candidate_id = f"news-{hashlib.sha1(clean_link.encode('utf-8')).hexdigest()[:16]}"

                        if not ignore_history and self.is_processed(candidate_id):
                            continue

                        desc_html = entry.get("summary") or entry.get("description") or title
                        description = re.sub(r"<[^>]+>", " ", desc_html)
                        description = re.sub(r"\s+", " ", description).strip()

                        media_url = self._extract_entry_media_url(entry, desc_html)
                        age_hours = 0
                        if published:
                            age_hours = max(0, (datetime.now() - datetime(*published[:6])).total_seconds() / 3600)
                        recency_score = max(1.0, 24.0 - age_hours) / 4.0
                        score = round(max(2.0, recency_score), 2)

                        hits.append({
                            'url': clean_link,
                            'score': score,
                            'reposts': 0,
                            'likes': 0,
                            'user': source_name,
                            'source': source_name,
                            'id': candidate_id,
                            'type': "NEWS 📰",
                            'is_video': False,
                            'media_url': media_url,
                            'thumbnail': None,
                            'description': title if not description else f"{title} - {description}"
                        })
                except Exception:
                    continue

        hits.sort(key=lambda item: item.get("score", 0), reverse=True)
        hits = hits[:max_items]

        if hits:
            progress_callback(f"   RSS noticias rescato {len(hits)} candidatos.")
        else:
            progress_callback("   RSS noticias no devolvio candidatos.")

        return hits

    def _extract_entry_media_url(self, entry, html):
        for key in ("media_content", "media_thumbnail"):
            media_items = entry.get(key)
            if media_items:
                url = media_items[0].get("url")
                if url:
                    return url

        links = entry.get("links") or []
        for link in links:
            href = link.get("href")
            link_type = link.get("type", "")
            if href and link_type.startswith("image/"):
                return href

        match = re.search(r'<img[^>]+src=["'']([^"'']+)["'']', html or "", re.I)
        if match:
            return match.group(1)

        return None

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
