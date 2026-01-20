import os
import shutil
import time
from datetime import datetime, timedelta

def cleanup_old_files(directory, max_age_hours=24, dry_run=False, quiet=False):
    """
    Deletes files/folders in the directory that are older than max_age_hours.
    """
    if not os.path.exists(directory):
        if not quiet: print(f"[CLEANUP] Directory {directory} does not exist.")
        return

    now = time.time()
    cutoff = now - (max_age_hours * 3600)
    
    if not quiet: print(f"[CLEANUP] Starting cleanup in {directory} (Older than {max_age_hours}h)...")
    
    removed_count = 0
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        try:
            st = os.stat(item_path)
            if st.st_mtime < cutoff:
                if dry_run:
                    print(f"[CLEANUP][DRY-RUN] Would remove: {item}")
                else:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                    if not quiet: print(f"[CLEANUP] Removed: {item}")
                    removed_count += 1
        except Exception as e:
            if not quiet: print(f"[CLEANUP] Error removing {item}: {e}")
    
    if not quiet: print(f"[CLEANUP] Finished. Removed {removed_count} items.")

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
                # print(f"[CLEANUP] Removed temporary file: {file}") # Silenced
                removed_count += 1
            except Exception as e:
                # print(f"[CLEANUP] Error removing temp file {file}: {e}") # Silenced
                pass
                
    return removed_count

if __name__ == "__main__":
    # Test execution
    base_dir = os.path.dirname(os.path.dirname(__file__))
    output_path = os.path.join(base_dir, "output")
    cleanup_old_files(output_path, days_to_keep=7)
    cleanup_temp_files(base_dir)
