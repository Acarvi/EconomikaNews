from google import genai
import os

key = os.environ.get("GEMINI_API_KEY", "")
if not key:
    # Try to grab it if user pastes it or I assume it (but better to ask/use existing env if possible)
    # Since I cannot see user's env, I'll rely on user running it or me running it if my environment has access
    # But wait, Render has the key. I can't run this on Render easily without deploying.
    # I'll create the script and ask the user to run it locally IF they have the key set locally,
    # OR I'll search deeper.
    print("Please set GEMINI_API_KEY env var")
else:
    client = genai.Client(api_key=key)
    try:
        print("Listing models...")
        for m in client.models.list_models():
            print(f"- {m.name}")
    except Exception as e:
        print(f"Error: {e}")
