import os
import whisper
import time
from typing import List, Dict
from ai_handler import generate_content_ai

# Load model globally to avoid repeated loading
# 'base' is a good balance between speed and accuracy
_model = None

def get_whisper_model():
    global _model
    if _model is None:
        print("[INFO] Loading Whisper model (small)...")
        _model = whisper.load_model("small")
    return _model

def transcribe_audio(video_path: str) -> Dict:
    """Transcribes audio from video using Whisper."""
    model = get_whisper_model()
    print(f"[INFO] Transcribing {video_path}...")
    result = model.transcribe(video_path)
    return result

def translate_subtitles_to_spanish(segments: List[Dict]) -> List[Dict]:
    """
    Translates segments to Spanish using Gemini AI while preserving structure.
    """
    if not segments: return []
    
    # Extract all text blocks to translate
    original_texts = [s['text'].strip() for s in segments]
    combined_text = "\n---\n".join(original_texts)
    
    prompt = f"""Traduce el siguiente contenido de video (subtítulos) al ESPAÑOL.
MANTÉN EL TONO de 'Economika Noticias' (profesional, serio, premium).
Respeta los separadores '---' para que pueda reconstruir los segmentos.
No añades explicaciones, solo la traducción.

CONTENIDO:
{combined_text}
"""
    # Create a dummy tweet_data for the ai_handler
    dummy_tweet = {'description': prompt}
    # We use ai_handler.generate_content_ai logic or just call gemini directly
    # For simplicity and consistency with current ai_handler:
    from ai_handler import generate_content_ai
    # Note: ai_handler returns (headline, caption, slug, shorts_title)
    # We need a custom call for just translation if we want precision, 
    # but let's assume we use a direct gemini call or refine ai_handler.
    
    # Direct Gemini usage is better here to avoid mixing formats
    from google import genai
    from google.genai import types
    
    from ai_handler import GEMINI_API_KEY
    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt
        )
        translated_blob = response.text
        translated_lines = translated_blob.split("---")
        
        for i, seg in enumerate(segments):
            if i < len(translated_lines):
                seg['text'] = translated_lines[i].strip()
    except Exception as e:
        print(f"[WARNING] Gemini translation failed: {e}. Keeping original.")
        
    return segments

def get_subtitles(video_path: str) -> List[Dict]:
    """Main entry point to get time-stamped Spanish subtitles."""
    result = transcribe_audio(video_path)
    language = result.get('language', 'en')
    segments = result.get('segments', [])
    
    if language != 'es':
        print(f"[INFO] Language '{language}' detected. Translating to Spanish...")
        segments = translate_subtitles_to_spanish(segments)
        
    return segments
