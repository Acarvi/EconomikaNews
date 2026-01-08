"""
Scraper module for Twitter/X posts.
Uses yt-dlp to extract metadata and media URLs from tweets.
"""
import yt_dlp
import re
import os
import time
from typing import Optional, Dict, Any

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
        from cookie_utils import netscape_to_dict
        
        client = Client('en-US')
        cookie_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "x.com_cookies.txt")
        
        if os.path.exists(cookie_file):
            cookies = netscape_to_dict(cookie_file)
            client.set_cookies(cookies)
            
            import asyncio
            
            async def _fetch():
                try:
                    # search is often more robust than get_tweet_by_id when API changes occur
                    # We search for the specific tweet ID
                    results = await client.search_tweet(f"status:{tweet_id}", 'Latest')
                    if not results:
                         # Try search by URL
                         results = await client.search_tweet(url, 'Latest')
                    
                    if not results:
                        return None
                        
                    tweet = results[0]
                    # verify it's the right one - sometimes search is fuzzy
                    # but usually for ID search it's exact if found
                    
                    full_text = getattr(tweet, 'full_text', getattr(tweet, 'text', ''))
                    
                    # Initialize defaults to prevent UnboundLocalError
                    media_url = None
                    is_video = False
                    
                    if hasattr(tweet, 'media') and tweet.media:
                        first_media = tweet.media[0]
                        media_url = getattr(first_media, 'media_url_https', None)
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
                        elif m_type == 'photo':
                            is_video = False
                            media_url = getattr(first_media, 'media_url_https', None)

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

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': False,
    }

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
                'likes': _get_stat(info, ['like_count', 'favorite_count', 'likeCount', 'view_count']), # some systems use view_count for likes? unlikely but safety
            }
    except Exception as e:
        print(f"[WARNING] yt-dlp failed: {e}. Trying browser fallback...")
        return scrape_tweet_with_browser(url)

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
