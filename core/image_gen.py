import requests
import os
import time

def generate_image_pollinations(prompt: str, output_path: str, width: int = 1080, height: int = 1920) -> str:
    """
    Generates an image using Pollinations.ai (Free, No API Key).
    """
    # Clean prompt for URL
    encoded_prompt = requests.utils.quote(prompt)
    
    # Pollinations URL format: https://image.pollinations.ai/prompt/{prompt}?width={w}&height={h}&seed={seed}&nologo=true
    # Enhanced for realism: model=flux-realism (if supported) or just flux with better prompt
    seed = int(time.time())
    # Adding 'photorealistic' to prompt is key, but 'model=flux-realism' is a valid param in some endpoints.
    # We'll use 'flux' but rely on strong prompt engineering in the caller, plus 'nologo'
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&seed={seed}&nologo=true&model=flux-realism"
    
    print(f"[AI-IMG] Requesting image from Pollinations.ai (Flux-Realism)...")
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            print(f"[AI-IMG] Image saved to {output_path}")
            return output_path
        else:
            print(f"[AI-IMG] Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"[AI-IMG] Exception: {e}")
        return None

if __name__ == "__main__":
    # Test
    generate_image_pollinations("futuristic news studio red and black theme, minimalist, 8k", "test_cover.jpg")
