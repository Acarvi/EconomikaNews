"""
AI Handler for generating Instagram captions and video headlines.
Uses the modern google-genai SDK.
"""
import os
import json
import re
import time
from typing import Dict, Tuple
from google import genai
from google.genai import types
import warnings

# === CONFIGURATION ===
GEMINI_API_KEY = "AIzaSyCsBBiYNL67fSv1XMY11fLFTkfuqjjqi8o"

# Initialize Client
client = genai.Client(api_key=GEMINI_API_KEY)

def generate_content_rest(contents: list, model_name: str = "gemini-1.5-flash") -> str:
    """Fallback using direct REST API if SDK fails. Tries both v1 and v1beta."""
    import requests
    
    # Try multiple versions
    versions = ["v1", "v1beta"]
    
    text_content = ""
    for item in contents:
        if isinstance(item, str):
            text_content += item + "\n"
    
    payload = {
        "contents": [{"parts": [{"text": text_content}]}]
    }
    
    headers = {'Content-Type': 'application/json'}
    
    # Ensure model handle is clean for REST
    clean_model = model_name if model_name.startswith('models/') else f"models/{model_name}"
    
    for version in versions:
        url = f"https://generativelanguage.googleapis.com/{version}/{clean_model}:generateContent?key={GEMINI_API_KEY}"
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                try:
                    return result['candidates'][0]['content']['parts'][0]['text']
                except (KeyError, IndexError):
                    continue
            elif response.status_code == 429:
                print(f"   ⚠️ REST {version} Quota exceeded (429).")
                return "QUOTA_EXCEEDED"
            else:
                continue
        except Exception:
            continue
            
    return ""

    try:
        # Prompts is in root, go up one level from core/
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base_dir, "prompts", "editorial_system.txt")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as e:
        print(f"⚠️ Error loading system instruction: {e}")
    
    # Minimal fallback
    return "Eres el Redactor Jefe de Economika Noticias. Tu línea editorial es liberal-libertaria."

def generate_content_ai(tweet_data: Dict, media_path: str = None, feedback: str = None) -> Tuple[str, str, str, str, str, str]:
    """
    Use Google Gemini to analyze tweet data and media for professional redaction.
    Supports iterative feedback for refinement.
    
    Returns: (headline, caption, slug, shorts_title, caption_b, source)
    """
    
    system_instruction = load_system_instruction()
    description = tweet_data.get('description', tweet_data.get('title', ''))
    uploader_id = tweet_data.get('uploader_id', '')  # Hint for source detection
    
    feedback_section = ""
    if feedback:
        feedback_section = f"""
    --- INSTRUCCIONES ADICIONALES DEL USUARIO (APLICAR PRIORITARIAMENTE) ---
    "{feedback}"
    ---
    """

    prompt = f"""
    {system_instruction}
    
    {feedback_section}
    
    CONTENIDO DEL TUIT A PROCESAR:
    "{description}"
    
    HANDLE DE TWITTER (pista para detectar fuente): @{uploader_id}
    """
    
    contents = [prompt]
    
    # Process media
    if media_path and os.path.exists(media_path):
        try:
            print(f"   ⬆️ Analyzing media with Gemini...")
            # In new SDK, we can pass the path directly or upload
            # We'll use the upload method for consistency with processing wait
            sample_file = client.files.upload(file=media_path)
            while sample_file.state == "PROCESSING":
                time.sleep(2)
                sample_file = client.files.get(name=sample_file.name)
            
            if sample_file.state != "FAILED":
                contents.append(sample_file)
        except Exception as e:
            print(f"   ! Media analysis skipped: {e}")

    # Optimized model selection (2026 low-cost standard)
    model_names = [
        'gemini-flash-lite-latest',
        'gemini-2.5-flash-lite',
        'gemini-2.0-flash-lite',
        'gemini-1.5-flash-8b' # Legacy fallback
    ]
    
    for model_name in model_names:
        try:
            # print(f"   🤖 Trying {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    tools=[types.Tool(google_search=types.GoogleSearchRetrieval())]
                )
            )
            text = response.text
        except Exception as e:
            err_str = str(e).lower()
            if "quota" in err_str or "429" in err_str:
                print(f"   ⚠️ Quota exceeded for {model_name}. Waiting 15s...")
                time.sleep(15)
                continue
            
            # Fallback to REST for other issues
            text = generate_content_rest(contents, model_name)
            if not text or text == "QUOTA_EXCEEDED":
                if text == "QUOTA_EXCEEDED": 
                    print(f"   ⚠️ REST Quota exceeded. Waiting 15s...")
                    time.sleep(15)
                continue

        # Parse JSON results
        try:
            # The SDK might return the JSON inside markdown blocks
            json_text = text
            if "```json" in text:
                json_text = text.split("```json")[1].split("```")[0].strip()
            elif "{" in text:
                json_text = text[text.find("{"):text.rfind("}")+1]
                
            data = json.loads(json_text)
            print(f"   ✅ Content generated with {model_name}")
            return (
                data.get('headline', 'NOTICIA ECONÓMIKA'), 
                data.get('caption', ''), 
                data.get('slug', 'noticia'), 
                data.get('shorts_title', 'Noticia Economika'),
                data.get('caption_b', data.get('caption', '')),  # Fallback to caption if not provided
                data.get('source', '')  # Empty string if not detected
            )
        except Exception:
            continue
    
    return "ERROR DE CUOTA AI", "Se ha alcanzado el límite de la versión gratuita. Por favor, espera unos minutos o usa otra API Key.", "error", "error", "", ""

def format_caption_txt(headline: str, caption: str) -> str:
    """Format the content as a plain text file."""
    sep = "=" * 40
    return f"{sep}\nHEADLINE:\n{headline}\n\n{sep}\nCAPTION:\n{caption}\n"

if __name__ == "__main__":
    # Test with sample data
    sample = {
        'title': 'Breaking: Economic news!',
        'description': 'The market is responding to the latest news from the ECB.',
    }
    res = generate_content_ai(sample)
    print("Result:", res)
