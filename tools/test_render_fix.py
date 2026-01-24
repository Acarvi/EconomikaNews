
import os
import sys

# Add project root to sys.path to allow imports BEFORE importing core
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import numpy as np
from moviepy import ColorClip
from core.generator import process_video_for_reel, conform_video_to_cfr

def test_rendering_fix():
    print("=== Testing Video Rendering Fix ===")
    
    # 1. Create a dummy video file if none exists
    test_video = "test_input.mp4"
    if not os.path.exists(test_video):
        print("Creating dummy test video...")
        clip = ColorClip(size=(640, 480), color=(255, 0, 0), duration=2)
        clip.write_videofile(test_video, fps=24, codec="libx264", logger=None)
        clip.close()

    # 2. Test CFR conformation
    print("\nTesting CFR conformation...")
    cfr_path = conform_video_to_cfr(test_video)
    if os.path.exists(cfr_path) and cfr_path.endswith("_cfr.mp4"):
        print(f"SUCCESS: Conformed video created at {cfr_path}")
    else:
        print(f"FAILURE: CFR conformation failed or returned original path: {cfr_path}")

    # 3. Test full rendering process
    print("\nTesting full rendering process...")
    output_name = "test_output_reel.mp4"
    try:
        result_path = process_video_for_reel(test_video, "Test Headline", handle="@test", output_name=output_name, skip_subtitles=True)
        if os.path.exists(result_path):
            print(f"SUCCESS: Resulting reel created at {result_path}")
        else:
            print(f"FAILURE: Resulting reel not found at {result_path}")
    except Exception as e:
        print(f"FAILURE: Rendering process crashed: {e}")

    # Cleanup (optional, keeping for user to see)
    # if os.path.exists(test_video): os.remove(test_video)
    # if os.path.exists(cfr_path): os.remove(cfr_path)

if __name__ == "__main__":
    # Add project root to sys.path to allow imports
    sys.path.append(os.getcwd())
    test_rendering_fix()
