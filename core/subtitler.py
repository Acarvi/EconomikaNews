import os
import whisper
import time
from typing import List, Dict

# Load model globally to avoid repeated loading
# 'base' is a good balance between speed and accuracy
_model = None

def get_whisper_model():
    global _model
    if _model is None:
        print("[INFO] Loading Whisper model (base)...")
        _model = whisper.load_model("base")
    return _model

def transcribe_audio(video_path: str) -> Dict:
    """Transcribes audio from video using Whisper."""
    # Safety check: skip transcription for images
    if video_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
        return {'language': 'es', 'segments': []}

    model = get_whisper_model()
    print(f"[INFO] Transcribing {video_path}...")
    # Allow auto-detection of original language, we will translate if needed
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
    
    # Direct Gemini usage
    from google import genai
    from google.genai import types
    from .ai_handler import GEMINI_API_KEY
    
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

def split_segments(segments: List[Dict], max_words: int = 3) -> List[Dict]:
    """Split long segments into smaller, punchier chunks for professional reels."""
    new_segments = []
    for seg in segments:
        words = seg['text'].split()
        if not words: continue
        
        # If segment is already short, keep it
        if len(words) <= max_words:
            new_segments.append(seg)
            continue
            
        # Split into chunks
        duration = seg['end'] - seg['start']
        word_duration = duration / len(words)
        
        for i in range(0, len(words), max_words):
            chunk = words[i:i + max_words]
            chunk_text = " ".join(chunk)
            chunk_start = seg['start'] + (i * word_duration)
            chunk_end = seg['start'] + ((i + len(chunk)) * word_duration)
            
            new_segments.append({
                'start': chunk_start,
                'end': chunk_end,
                'text': chunk_text
            })
    return new_segments

def get_subtitles(video_path: str) -> List[Dict]:
    """Main entry point to get time-stamped Spanish subtitles."""
    result = transcribe_audio(video_path)
    language = result.get('language', 'en')
    segments = result.get('segments', [])
    
    # Force translation if not Spanish, ensuring "always Spanish" goal
    if language != 'es':
        print(f"[INFO] Language '{language}' detected. Translating to Spanish with Gemini...")
        segments = translate_subtitles_to_spanish(segments)
    else:
        print(f"[INFO] Language already Spanish. No translation needed.")
    
    # Optimization: Split into short pieces for professional look
    segments = split_segments(segments, max_words=3)
        
    return segments
