"""
Downloader module for Twitter/X media.
Uses yt-dlp to download videos and images.
"""
import yt_dlp
import os
import requests
from typing import Optional, Tuple

DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

COOKIES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "x.com_cookies.txt")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def download_media(url: str, output_name: str = None, thumbnail_url: str = None, is_video: bool = True, direct_url: str = None) -> Tuple[bool, str]:
    """
    Download media (video or image) from a Twitter URL.
    Returns (success, file_path or error_message).
    """
    from .scraper import extract_tweet_id
    tid = extract_tweet_id(url) or "media"
    
    # 0. Early Exit: If file already exists in DOWNLOADS_DIR, return it
    for ext in ['mp4', 'jpg', 'png', 'webp']:
        test_path = os.path.join(DOWNLOADS_DIR, f"{tid}.{ext}")
        if os.path.exists(test_path) and os.path.getsize(test_path) > 1024:
            return True, test_path

    # 1. Fast path: Direct Download if direct_url is provided and looks valid
    # This avoids expensive yt-dlp calls if we already have the MP4/JPG URL from the scraper
    if direct_url and direct_url.startswith('http'):
        ext = "mp4" if is_video else "jpg"
        if not is_video:
            if ".png" in direct_url.lower(): ext = "png"
            elif ".webp" in direct_url.lower(): ext = "webp"
        
        dest = os.path.join(DOWNLOADS_DIR, f"{tid}.{ext}")
        status, path = download_file(direct_url, dest)
        if status:
            return True, path

    # 2. Fallback: yt-dlp Extraction
    # Silence yt-dlp completely
    import sys
    import io
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()  # Capture and discard stderr
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'no_progress': True,
        'logger': type('QuietLogger', (), {'debug': lambda *a: None, 'warning': lambda *a: None, 'error': lambda *a: None})(),
        'outtmpl': os.path.join(DOWNLOADS_DIR, output_name or f'{tid}.%(ext)s'),
        'format': 'best[ext=mp4]/best',
        'http_headers': {'User-Agent': USER_AGENT},
    }
    
    if os.path.exists(COOKIES_FILE):
        ydl_opts['cookiefile'] = COOKIES_FILE

    try:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                filename = ydl.prepare_filename(info)
                if os.path.exists(filename) and os.path.getsize(filename) > 1024:
                    return True, filename
                
                # Fallback for images inside yt-dlp info
                for ext in ['mp4', 'jpg', 'png', 'webp']:
                    test_path = os.path.join(DOWNLOADS_DIR, f"{info.get('id', 'media')}.{ext}")
                    if os.path.exists(test_path):
                        return True, test_path
                
                # If nothing found but we have a thumbnail URL, try it
                if thumbnail_url:
                    from .scraper import extract_tweet_id
                    tid = extract_tweet_id(url) or "media"
                    ext = "jpg"
                    if thumbnail_url and ".png" in thumbnail_url.lower(): ext = "png"
                    dest = os.path.join(DOWNLOADS_DIR, f"{tid}.{ext}")
                    success, path = download_file(thumbnail_url, dest)
                    if success: return True, path
                        
        except Exception as e:
            # If yt-dlp fails (e.g. no video), try direct thumbnail download
            if thumbnail_url:
                ext = "jpg"
                if ".png" in thumbnail_url.lower(): ext = "png"
                if ".webp" in thumbnail_url.lower(): ext = "webp"
                
                # Generate a name if not provided
                if not output_name:
                    from .scraper import extract_tweet_id
                    tid = extract_tweet_id(url) or "media"
                    output_name = f"{tid}.{ext}"
                
                dest = os.path.join(DOWNLOADS_DIR, output_name)
                success, path = download_file(thumbnail_url, dest)
                if success:
                    return True, path
                    
            return False, str(e)
    finally:
        sys.stderr = old_stderr # Restore stderr NO MATTER WHAT

    return False, "Failed to download media"

def download_file(url: str, output_path: str) -> Tuple[bool, str]:
    """Download any file URL with verification and custom UA."""
    if not url or not isinstance(url, str) or not url.startswith('http'):
        return False, "Invalid URL"
        
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, timeout=30, headers=headers)
        response.raise_for_status()
        
        # Verify content type
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' in content_type and 'video' not in content_type and 'image' not in content_type:
            return False, "URL returned HTML instead of expected media"
            
        with open(output_path, 'wb') as f:
            f.write(response.content)
            
        # Verify file size
        if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
            return True, output_path
        
        if os.path.exists(output_path): os.remove(output_path)
        return False, "Downloaded file is too small or empty"
    except Exception as e:
        if os.path.exists(output_path): os.remove(output_path)
        return False, str(e)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        success, result = download_media(sys.argv[1])
        if success:
            print(f"Downloaded: {result}")
        else:
            print(f"Error: {result}")
