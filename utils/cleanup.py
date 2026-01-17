import os
import shutil
import time
from datetime import datetime, timedelta

def cleanup_old_files(output_dir, days_to_keep=7, dry_run=False):
    """
    Deletes folders in the output directory that are older than days_to_keep.
    """
    if not os.path.exists(output_dir):
        print(f"[CLEANUP] Output directory {output_dir} does not exist.")
        return

    now = time.time()
    cutoff = now - (days_to_keep * 86400)
    
    print(f"[CLEANUP] Starting cleanup in {output_dir} (Keeping last {days_to_keep} days)...")
    
    folders_removed = 0
    for item in os.listdir(output_dir):
        item_path = os.path.join(output_dir, item)
        
        # We only care about directories in output (which are formatted as YYYYMMDD_slug)
        if os.path.isdir(item_path):
            st = os.stat(item_path)
            mtime = st.st_mtime
            
            if mtime < cutoff:
                if dry_run:
                    print(f"[CLEANUP][DRY-RUN] Would remove: {item}")
                else:
                    try:
                        shutil.rmtree(item_path)
                        print(f"[CLEANUP] Removed old folder: {item}")
                        folders_removed += 1
                    except Exception as e:
                        print(f"[CLEANUP] Error removing {item}: {e}")
    
    print(f"[CLEANUP] Finished. Removed {folders_removed} folders.")

def cleanup_temp_files(root_dir):
    """
    Removes temporary moviepy files (ending in .mp4 or .mp3 with moviepy patterns) 
    found in the root directory.
    """
    temp_patterns = ["TEMP_MPY_", "wvf_snd"]
    removed_count = 0
    
    for file in os.listdir(root_dir):
        if any(p in file for p in temp_patterns) and file.endswith((".mp4", ".mp3")):
            file_path = os.path.join(root_dir, file)
            try:
                os.remove(file_path)
                print(f"[CLEANUP] Removed temporary file: {file}")
                removed_count += 1
            except Exception as e:
                print(f"[CLEANUP] Error removing temp file {file}: {e}")
                
    return removed_count

if __name__ == "__main__":
    # Test execution
    base_dir = os.path.dirname(os.path.dirname(__file__))
    output_path = os.path.join(base_dir, "output")
    cleanup_old_files(output_path, days_to_keep=7)
    cleanup_temp_files(base_dir)
