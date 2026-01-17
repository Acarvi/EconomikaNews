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

def download_media(url: str, output_name: str = None, thumbnail_url: str = None) -> Tuple[bool, str]:
    """
    Download media (video or image) from a Twitter URL.
    Returns (success, file_path or error_message).
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'outtmpl': os.path.join(DOWNLOADS_DIR, output_name or '%(id)s.%(ext)s'),
        'format': 'best[ext=mp4]/best',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if os.path.exists(filename):
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
                if ".png" in thumbnail_url.lower(): ext = "png"
                dest = os.path.join(DOWNLOADS_DIR, f"{tid}.{ext}")
                success, path = download_image(thumbnail_url, dest)
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
            success, path = download_image(thumbnail_url, dest)
            if success:
                return True, path
                
        return False, str(e)
    
    return False, "Failed to download media"

def download_image(url: str, output_path: str) -> Tuple[bool, str]:
    """Download a direct image URL with verification."""
    if not url or not isinstance(url, str) or not url.startswith('http'):
        return False, "Invalid image URL"
        
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Verify content type looks like an image
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' in content_type:
            return False, "URL returned HTML instead of image"
            
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
