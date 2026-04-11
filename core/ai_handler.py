import os
import json
import time
import requests
from typing import Dict, Tuple, Optional, List
from dotenv import load_dotenv

# Initialize environment
load_dotenv()

# === CONFIGURATION ===
CENTRAL_AI_URL = os.environ.get("CENTRAL_AI_URL", "http://localhost:8080")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") # Exported for global use (e.g. subtitler)

def load_system_instruction():
    """Load the editorial system instruction from an external file."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base_dir, "prompts", "editorial_system.txt")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception as e:
        print(f"⚠️ Error loading system instruction: {e}")
    return "Eres el Redactor Jefe de Economika Noticias. Tu línea editorial es liberal-libertaria."

def generate_content_ai(tweet_data: Dict, media_path: str = None, feedback: str = None, quality: str = "pro") -> Tuple[str, str, str, str, str, str, str, str, str]:
    """
    Use CentralAIService to analyze tweet data and media.
    
    Returns: (headline, caption, slug, shorts_title, caption_b, source, suggested_location_query, start_time, end_time)
    """
    description = tweet_data.get('description', tweet_data.get('title', ''))
    uploader_id = tweet_data.get('uploader_id', '')
    
    # Preparamos el prompt para el Hub
    system_instruction = load_system_instruction()
    feedback_section = f"\nFeedback Usuario: {feedback}" if feedback else ""
    
    prompt = f"""
    {system_instruction}
    {feedback_section}
    
    CONTEXTO TUIT: "{description}"
    HANDLE DE TWITTER: @{uploader_id}
    
    Salida requerida (JSON):
    {{
        "headline": "[Titular directo e informativo]",
        "caption": "[Cuerpo de la noticia]",
        "slug": "slug_corto",
        "shorts_title": "[YouTube Shorts Title]",
        "caption_b": "[Versión A/B]",
        "source": "[Fuente original]",
        "best_segment_start": "[MM:SS]",
        "best_segment_end": "[MM:SS]",
        "suggested_location_query": "[Query Mapa]"
    }}
    """

    max_retries = 3
    base_delay = 2
    
    for attempt in range(max_retries):
        try:
            # Si hay video, usamos el endpoint de análisis de video del Hub
            if media_path and os.path.exists(media_path) and media_path.lower().endswith(('.mp4', '.mov', '.avi')):
                print(f"   🧠 Consultando CentralAIService (/v1/analyzer/draft) [Intento {attempt+1}/{max_retries}]...")
                payload = {
                    "video_path": os.path.abspath(media_path),
                    "global_comments": feedback or "",
                    "custom_prompt": prompt
                }
                response = requests.post(f"{CENTRAL_AI_URL}/v1/analyzer/draft", json=payload, timeout=300)
            else:
                print(f"   🧠 Consultando CentralAIService para contenido estático [Intento {attempt+1}/{max_retries}]...")
                payload = {
                    "script_data": {"description": description, "uploader": uploader_id},
                    "global_comments": f"{prompt}\n{feedback or ''}"
                }
                response = requests.post(f"{CENTRAL_AI_URL}/v1/analyzer/storyboard", json=payload, timeout=60)

            if response.status_code == 200:
                data = response.json()
                return parse_hub_response(data)
            elif response.status_code == 429:
                delay = base_delay * (2 ** attempt)
                print(f"   🛑 ERROR 429 (Rate Limit). Reintentando en {delay}s...")
                time.sleep(delay)
                continue
            else:
                print(f"   ❌ CentralAIService error ({response.status_code}): {response.text}")
                raise Exception(f"Service error {response.status_code}")

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"   ⚠️ Error en intento {attempt+1}: {e}. Reintentando...")
                time.sleep(base_delay)
                continue
            print(f"   ⚠️ Fallo final tras {max_retries} intentos: {e}")
            return "ERROR DE CONEXIÓN HUB", "Asegúrate de que CentralAIService esté corriendo.", "error", "error", "", "", "", "00:00", "END"
    
    return "ERROR DE CONEXIÓN HUB", "Máximo de reintentos alcanzado.", "error", "error", "", "", "", "00:00", "END"

def parse_hub_response(data: dict) -> Tuple:
    """Adapta la respuesta del Hub al formato de EconomikaNoticias."""
    return (
        data.get('headline', 'NOTICIA'),
        data.get('caption', ''),
        data.get('slug', 'noticia'),
        data.get('shorts_title', 'Shorts'),
        data.get('caption_b', data.get('caption', '')),
        data.get('source', ''),
        data.get('suggested_location_query', ''),
        data.get('best_segment_start', '00:00'),
        data.get('best_segment_end', 'END')
    )

if __name__ == "__main__":
    sample = {'title': 'Breaking news'}
    print(generate_content_ai(sample))
