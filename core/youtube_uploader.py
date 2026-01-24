import os
import pickle
import json
import json
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    HAS_YOUTUBE_LIBS = True
except ImportError:
    HAS_YOUTUBE_LIBS = False

try:
    import cv2  # Added for video validation
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
import math

# Scopes needed for uploading
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.force-ssl']
CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'client_secrets.json')
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'youtube_token.pickle')

def get_authenticated_service():
    """Gets an authenticated YouTube service object."""
    if not HAS_YOUTUBE_LIBS:
        raise ImportError("YouTube dependencies (google-api-python-client, google-auth-oauthlib) not installed.")
    
    credentials = None
    if os.path.exists(CREDENTIALS_FILE):
        print(f"[INFO] Loading credentials from {CREDENTIALS_FILE}")
        with open(CREDENTIALS_FILE, 'rb') as f:
            credentials = pickle.load(f)
    
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print("[INFO] Refreshing access token...")
            credentials.refresh(Request())
        else:
            print("[INFO] Fetching new tokens...")
            if not os.path.exists(CLIENT_SECRETS_FILE):
                raise FileNotFoundError(f"Client secrets file not found at {CLIENT_SECRETS_FILE}")
                
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)
        
        with open(CREDENTIALS_FILE, 'wb') as f:
            print(f"[INFO] Saving credentials to {CREDENTIALS_FILE}")
            pickle.dump(credentials, f)
    
    return build('youtube', 'v3', credentials=credentials)

def upload_short(video_path: str, title: str = "Economika Noticias", description: str = "", publish_at: str = None) -> str:
    """
    Uploads a video to YouTube as a Short.
    
    Args:
        video_path: Path to the video file.
        title: Title of the video (max 100 chars).
        description: Video description.
        publish_at: Optional ISO 8601 string (e.g. 2026-01-22T15:44:00Z) for scheduling.
        
    Returns:
        The ID of the uploaded video, or None if failed.
    """
    try:
        print(f"[INFO] Starting upload for: {video_path}")
        if publish_at:
            print(f"[INFO] Scheduling for: {publish_at}")
            
        youtube = get_authenticated_service()
        
        # Ensure title is within limits
        safe_title = title[:100]
        
        body = {
            'snippet': {
                'title': safe_title,
                'description': description,
                'tags': ['shorts', 'news', 'economika', 'libertad', 'economia'],
                'categoryId': '25'  # News & Politics
            },
            'status': {
                'privacyStatus': 'private' if publish_at else 'public',
                'selfDeclaredMadeForKids': False
            }
        }
        
        if publish_at:
            # YouTube requires 'private' status to use 'publishAt'
            body['status']['publishAt'] = publish_at
            
        # --- VALIDATION FOR SHORTS ---
        if HAS_CV2:
            try:
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    duration = frame_count / fps if fps > 0 else 0
                    cap.release()
                    
                    print(f"[INFO] Video Stats: {int(width)}x{int(height)}, {duration:.2f}s")
                    
                    # Check 1: Vertical or Square (Aspect Ratio <= 1.0)
                    if width > height:
                        print(f"[WARNING] ⚠️ Video is horizontal ({int(width)}x{int(height)}). YouTube might NOT classify it as a Short.")
                        # We continue but warn.
                    
                    # Check 2: Duration < 60s
                    if duration >= 60:
                        print(f"[WARNING] ⚠️ Video is too long for Shorts ({duration:.2f}s). Trimming slightly suggested.")
                        # Ideally we would reject or trim, but for now we warn.
                else:
                    print(f"[WARNING] Could not validate video properties (CV2 failed open).")
            except Exception as e:
                print(f"[WARNING] Video validation failed: {e}")
        else:
            print("[INFO] Skipping video validation (cv2 not available)")

        # Ensure #Shorts tag is present in description or title for older clients
        if "#shorts" not in description.lower() and "#shorts" not in safe_title.lower():
            description += "\n\n#Shorts"

        # Resumable upload for better reliability
        media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
        
        request = youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"[INFO] Uploaded {int(status.progress() * 100)}%")
        
        video_id = response.get('id')
        print(f"[SUCCESS] YouTube Short uploaded: https://youtube.com/shorts/{video_id}")
        return video_id
        
    except Exception as e:
        error_msg = str(e)
        if "uploadLimitExceeded" in error_msg:
            print(f"\n[!] LÍMITE DE SUBIDA ALCANZADO: YouTube ha bloqueado nuevas subidas en este canal por hoy.")
            print(f"[!] Esto suele ocurrir tras subir 10-15 vídeos en canales nuevos o no verificados.")
            print(f"[!] SOLUCIÓN: Verifica tu cuenta de YouTube con un teléfono o espera 24 horas para continuar.\n")
        else:
            print(f"[ERROR] YouTube upload failed: {error_msg}")
        return None

if __name__ == "__main__":
    # Test script to authorize and upload a dummy file if needed
    try:
        service = get_authenticated_service()
        print("Authentication successful!")
    except Exception as e:
        print(f"Authentication failed: {e}")
