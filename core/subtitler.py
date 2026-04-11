import os
import whisper
import time
from typing import List, Dict

# Load model globally to avoid repeated loading
# 'medium' chosen for better accuracy as requested by user ("sube el whisper")
_model = None

def get_whisper_model():
    global _model
    if _model is None:
        print("[INFO] Loading Whisper model (large-v3)...")
        try:
            _model = whisper.load_model("large-v3")
        except Exception as e:
            print(f"[WARN] Failed to load large-v3 model, falling back to medium: {e}")
            try:
                _model = whisper.load_model("medium")
            except Exception as e2:
                print(f"[ERROR] Whisper local fallback failed completely: {e2}")
                _model = "FAILED" # Marker to skip transcription
    return _model

def transcribe_audio(video_path: str) -> Dict:
    """Transcribes audio from video using Whisper."""
    # Safety check: skip transcription for images
    if video_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
        return {'language': 'es', 'segments': []}

    model = get_whisper_model()
    if model == "FAILED":
        print("[WARN] Fallback a Whisper falló por dependencias del sistema. Renderizando vídeo SIN subtítulos.")
        return {'language': 'es', 'segments': []}

    print(f"[INFO] Transcribing {video_path}...")
    
    try:
        # Enable word_timestamps for maximum precision in sync
        result = model.transcribe(video_path, word_timestamps=True)
        return result
    except Exception as e:
        print(f"[WARN] Transcription failed or system dependency error: {e}")
        if "size" in str(e) and isinstance(e, RuntimeError):
            print(f"[WARN] Whisper shape error detected. Retrying with fp16=False...")
            try:
                result = model.transcribe(video_path, word_timestamps=True, fp16=False)
                return result
            except Exception as e2:
                 print(f"[ERROR] Whisper retry failed: {e2}")
        
        print("[WARN] Fallback a Whisper falló por dependencias del sistema. Renderizando vídeo SIN subtítulos.")
        return {'language': 'es', 'segments': []} # Return empty on failure to prevent crash

def translate_subtitles_to_spanish(segments: List[Dict]) -> List[Dict]:
    """
    Translates segments to Spanish using Gemini AI while preserving structure.
    """
    if not segments: return []
    
    # Extract all text blocks to translate
    original_texts = [s['text'].strip() for s in segments]
    
    # Use XML-style tags for safer parsing than " --- "
    combined_text = ""
    for i, t in enumerate(original_texts):
        combined_text += f"<seg id={i}>{t}</seg>\n"
    
    prompt = f"""Traduce los subtítulos dentro de las etiquetas a ESPAÑOL.
MANTÉN EL TONO de 'Economika Noticias' (profesional, serio, premium, liberal).
NO respondas con nada más que el XML traducido.
Respeta los IDs.

ENTRADA:
{combined_text}

SALIDA (Formato esperado):
<seg id=0>Traducción 0</seg>
...
"""
    
    # Direct Gemini usage
    from google import genai
    from google.genai import types
    from core.ai_handler import GEMINI_API_KEY
    import re
    
    # Robust validation for API Key
    if not GEMINI_API_KEY or len(GEMINI_API_KEY) < 10:
        print("[WARN] API Key de Gemini inválida o vacía. Omitiendo traducción de subtítulos (Fallback).")
        return segments # Devuelve los segmentos originales de Whisper sin traducir
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        translated_blob = response.text
        
        # Robust parsing with Regex
        pattern = r"<seg id=(\d+)>(.*?)</seg>"
        matches = re.findall(pattern, translated_blob, re.DOTALL)
        
        # Create a dict for lookups
        trans_map = {int(idx): text.strip() for idx, text in matches}
        
        for i, seg in enumerate(segments):
            if i in trans_map:
                seg['text'] = trans_map[i]
            # Else keep original if translation missed it
            
    except Exception as e:
        print(f"[CRITICAL] Gemini translation exception: {type(e).__name__}: {e}")
        
    return segments

def split_segments(segments: List[Dict], max_words: int = 3) -> List[Dict]:
    """Split segments into smaller chunks. Uses Whisper word-level data if available."""
    new_segments = []
    for seg in segments:
        words_data = seg.get('words')
        text_words = seg['text'].split()
        
        if not text_words: continue
        
        # Case A: We have exact word timestamps (Same language)
        if words_data and len(words_data) == len(text_words):
            for i in range(0, len(words_data), max_words):
                chunk = words_data[i:i + max_words]
                chunk_text = " ".join([w['word'].strip() for w in chunk])
                new_segments.append({
                    'start': chunk[0]['start'],
                    'end': chunk[-1]['end'],
                    'text': chunk_text
                })
        # Case B: No word data or count mismatch (e.g. after Translation)
        else:
            duration = seg['end'] - seg['start']
            word_duration = duration / len(text_words)
            for i in range(0, len(text_words), max_words):
                chunk = text_words[i:i + max_words]
                chunk_text = " ".join(chunk)
                # Improve sync: Add a small buffer to start/end to avoid "flashing"
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
    
    # 1. Force translation if not Spanish, ensuring "always Spanish" goal
    # 2. ALSO translate if language is 'ca' (Catalan) or other regional languages
    if language not in ['es', 'spa']:
        print(f"[INFO] Language '{language}' detected. Translating to Spanish with Gemini...")
        segments = translate_subtitles_to_spanish(segments)
    else:
        print(f"[INFO] Language already Spanish. No translation needed.")
    
    # Optimization: Split into short pieces (Hormozi style)
    segments = split_segments(segments, max_words=2)
        
    return segments
