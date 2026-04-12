import asyncio
from twikit import Client
import os
import sys

# Load cookies
COOKIES_FILE = "config/x.com_cookies.json"

async def raw_debug():
    print("Starting Raw Twikit Debug for @wallstwolverine...")
    client = Client('en-US')
    
    if not os.path.exists(COOKIES_FILE):
        print(f"Error: {COOKIES_FILE} not found.")
        return

    client.load_cookies(COOKIES_FILE)
    
    try:
        user = await client.get_user_by_screen_name("wallstwolverine")
        print(f"User Found: {user.id} | Followers: {user.followers_count}")
        
        tweets = await client.get_user_tweets(user.id, 'Tweets', count=5)
        print(f"Successfully retrieved {len(tweets) if tweets else 0} tweets.")
    except Exception as e:
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        if hasattr(e, 'response'):
            print(f"Response Status: {e.response.status_code}")
            # Save raw response text to a file
            with open("debug_raw_response.html", "w", encoding="utf-8") as f:
                f.write(e.response.text)
            print("Raw response saved to debug_raw_response.html")

if __name__ == "__main__":
    asyncio.run(raw_debug())
