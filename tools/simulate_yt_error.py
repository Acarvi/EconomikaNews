import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.youtube_uploader import upload_short
from unittest.mock import patch, MagicMock

print("--- Simulating YouTube Upload Limit Error ---")

# Mock the get_authenticated_service to trigger a simulated error
with patch('core.youtube_uploader.get_authenticated_service') as mock_service:
    # Create a mock YouTube object
    mock_yt = MagicMock()
    mock_service.return_value = mock_yt
    
    # Configure the mock to raise an exception simulating the real HttpError message
    error_data = "{'message': 'The user has exceeded the number of videos they may upload.', 'domain': 'youtube.video', 'reason': 'uploadLimitExceeded'}"
    mock_yt.videos().insert.side_effect = Exception(f"<HttpError 400 when requesting None returned \"{error_data}\">")
    
    # Run the uploader
    # We use a dummy file path since it won't be read before the exception
    result = upload_short("dummy_video.mp4", "Test Title", "Test Description")
    
    if result is None:
        print("\n[VERIFICATION] Test finished. Check if the block message appeared above.")
    else:
        print("\n[FAILED] Test failed: upload_short should have returned None.")
