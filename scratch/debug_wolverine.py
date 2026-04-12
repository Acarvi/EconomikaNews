import asyncio
import os
import sys

# Ensure we are in the project root
sys.path.insert(0, os.getcwd())

from core.viral_scout import ViralScout
from datetime import datetime, timedelta

async def debug_wolverine():
    scout = ViralScout()
    # Isolate wallstwolverine
    scout.accounts = {"wallstwolverine": 850000}
    
    print("[DEBUG] Starting Isolated Debug for @wallstwolverine...")
    
    # We use a very low ratio to ensure we don't filter out anything during debug
    try:
        hits = await scout._scan_async(hours_back=48, min_ratio=0.01)
        print(f"✨ Found {len(hits)} hits.")
    except Exception as e:
        print(f"❌ CRITICAL SCRATCH ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_wolverine())
