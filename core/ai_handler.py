"""
AI Handler for generating Instagram captions and video headlines.
Uses the modern google-genai SDK.
"""
import os
import json
import re
import time
from typing import Dict, Tuple, Optional, List
from google import genai
from google.genai import types
import warnings
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# === CONFIGURATION ===
def load_env_file():
    """Simple .env loader to avoid extra dependencies. Robust to relative paths."""
    # Search root from multiple depths (core/ or root/)
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(curr_dir, "..", ".env"), # From core/
        os.path.join(curr_dir, ".env"),      # From root/
        os.path.join(os.getcwd(), ".env")    # Fallback to current working dir
    ]
    for env_path in possible_paths:
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        key, value = line.strip().split("=", 1)
                        os.environ[key] = value
            # print(f"   [ENV] Loaded from {env_path}")
            return True
    return False

load_env_file()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCsBBiYNL67fSv1XMY11fLFTkfuqjjqi8o")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

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

def generate_content_openrouter(prompt: str, model_name: str = "moonshotai/kimi-k2.5") -> str:
    """Use Kimi (Moonshot AI) via OpenRouter."""
    if not OpenAI or not OPENROUTER_API_KEY:
        return ""
    
    try:
        # Ensure OpenAI is imported and client_or is instantiated here,
        # in case the global OpenAI was None or needs re-initialization.
        # The global `OpenAI` is set by the initial try-except block.
        # This ensures `client_or` is always a fresh instance within this call.
        client_or = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        
        response = client_or.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            extra_headers={
                "HTTP-Referer": "https://github.com/Antigravity", # Optional
                "X-Title": "Economika Noticias", # Optional
            }
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"   ⚠️ Kimi AI Error: {e}")
        return ""

def load_system_instruction():
    """Load the editorial system instruction from an external file."""
    try:
        # Prompts is in root, go up one level from core/
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base_dir, "prompts", "editorial_system.txt")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception as e:
        print(f"⚠️ Error loading system instruction: {e}")
    
    # Minimal fallback
    return "Eres el Redactor Jefe de Economika Noticias. Tu línea editorial es liberal-libertaria."

def generate_content_ai(tweet_data: Dict, media_path: str = None, feedback: str = None, quality: str = "pro") -> Tuple[str, str, str, str, str, str, str, str, str]:
    """
    Use AI to analyze tweet data and media for professional redaction.
    quality: "cheap" (fast preview analysis) or "pro" (final high-quality redaction).
    
    Returns: (headline, caption, slug, shorts_title, caption_b, source, suggested_location_query, start_time, end_time)
    """
    
    description = tweet_data.get('description', tweet_data.get('title', ''))
    uploader_id = tweet_data.get('uploader_id', '')
    
    if quality == "cheap":
        # Simplified prompt for preview analysis - PLANNING PHASE
        prompt = f"""
        OBJETIVO: ESTO ES UNA FASE DE PLANIFICACIÓN (PREVIEW).
        Analiza la multimedia y propón un plan de contenido.
        
        TU TAREA:
        1. Describe qué ocurre visualmente de forma resumida.
        2. Define el ÁNGULO de la noticia y cómo piensas redactarla después.
        
        Salida requerida (JSON):
        {{
            "plan_explicacion": "VISUAL: [Qué se ve]\\nPLAN: [Qué vamos a contar y qué enfoque daremos]", 
            "source": "[Fuente detectada o 'Desconocida']"
        }}
        
        CONTEXTO TUIT: "{description}"
        HANDLE: @{uploader_id}
        """
        system_instruction = "Eres un analista de noticias de alto impacto. Tu prioridad es la multimedia."
    else:
        system_instruction = load_system_instruction()
        feedback_section = ""
        if feedback:
            feedback_section = f"\n--- INSTRUCCIONES DEL USUARIO (PRIORIDAD MÁXIMA) ---\n\"{feedback}\"\n---\n"

        analysis_context = ""

        prompt = f"""
        {system_instruction}
        {feedback_section}
        
        OBJETIVO: Redactar una noticia veraz, de alto impacto y NADA ROBÓTICA. Estilo "periodismo ágil".
        
        FASE 1: INVESTIGACIÓN Y FACT-CHECK (Google Search)
        1. Identifica a las personas clave en el vídeo/tuit.
        2. **DETECTA LA FUENTE ORIGINAL**:
           * El uploader (@{uploader_id}) a menudo es un "re-subidor".
           * Mira el vídeo/imagen: ¿Hay marca de agua de TikTok/IG de OTRA persona?
           * ¿El vídeo es de una cadena de TV (ej: LaSexta, CNN)?
           * SI VES MARCA DE AGUA/LOGO: Esa es la "source". (Ej: "@pepe_tiktok", "Antena 3").
           * SI NO: Usa el handle del uploader.
        3. Verifica los cargos actuales de los implicados.
        
        FASE 2: REDACCIÓN EDITORIAL (ESTILO NATURAL)
        - TITULARES: 
          * PROHIBIDO: "Polémica en...", "Lo que pasó con...", "Impactante...". Son clichés de IA.
          * OBJETIVO: Titulares informativos que cuenten la noticia DE GOLPE. Sujeto + Verbo + Predicado potente.
          * BIEN: "SpaceX prioriza la Luna antes que Marte para 2027" o "Rubio exige explicaciones sobre los misiles".
          * MAL: "La increíble decisión de SpaceX que cambia todo". (Clickbait barato/IA).
          
        - CAPTION: Redacta con fuerza liberal-libertaria. Usa datos, no adjetivos vacíos.
        
        FASE 3: REVISIÓN DE ANACRONISMOS
        - Relee tu texto. Si has llamado a alguien por un cargo que ya no ocupa, CORRÍGELO.
        
        FASE 3: SELECCIÓN DE SEGMENTO VIRAL (MP4)
        - Si el vídeo es largo, dame el TIMESTAMP (MM:SS) de inicio y fin de la parte más interesante.
        - Máximo 90 segundos. Prioriza el clímax o la declaración más fuerte.
        - Si el vídeo es corto o todo es bueno, pon "00:00" y "END".

        CONTEXTO TUIT: "{description}"
        HANDLE DE TWITTER: @{uploader_id}
        
        Salida requerida (JSON):
        {{
            "headline": "[Titular directo, informativo y natural]",
            "caption": "[Cuerpo de la noticia con fact-check aplicado]",
            "slug": "slug_corto",
            "shorts_title": "[Título para YouTube Shorts optimizado SEO]",
            "caption_b": "[Versión alternativa para A/B testing]",
            "source": "[Fuente visual detectada o uploader]",
            "best_segment_start": "[MM:SS o 0]", 
            "best_segment_end": "[MM:SS o END]",
            "suggested_location_query": "[Búsqueda para mapa si aplica]"
        }}
        """
    
    contents = [prompt]
    
    # Process media
    if media_path and os.path.exists(media_path):
        upload_path = media_path
        # OPTIMIZATION: For 'cheap' preview, upload only a thumbnail if it's a video
        if quality == "cheap" and media_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
            try:
                import cv2
                cap = cv2.VideoCapture(media_path)
                ret, frame = cap.read()
                if ret:
                    thumb_path = media_path.rsplit('.', 1)[0] + "_preview_thumb.jpg"
                    cv2.imwrite(thumb_path, frame)
                    upload_path = thumb_path
                cap.release()
            except Exception as e:
                print(f"   ! Thumbnail extraction failed: {e}")

        try:
            print(f"   ⬆️ Analyzing media with Gemini ({'thumbnail' if upload_path != media_path else 'full file'})...")
            # Wait a moment for any file locks (cv2, etc) to clear
            time.sleep(1)
            
            # Use file= instead of path= for google-genai SDK
            sample_file = client.files.upload(file=upload_path)
            while sample_file.state == "PROCESSING":
                time.sleep(2)
                sample_file = client.files.get(name=sample_file.name)
            
            if sample_file.state != "FAILED":
                contents.append(sample_file)
        except Exception as e:
            print(f"   ! Media analysis skipped: {e}")

    # Optimized model selection (2026 standard)
    if quality == "cheap":
        model_names = ['gemini-2.0-flash-lite-preview-02-05', 'gemini-1.5-flash-8b']
    else:
        # For PRO, we use 2.0 Flash as primary for integrated Vision + Search + Redaction
        model_names = [
            'gemini-2.0-flash',
            'gemini-1.5-pro-latest',
            'gemini-1.5-flash-latest'
        ]
    
    # --- UNIFIED PROVIDER: GOOGLE GEMINI (Multi-model Fallback with Retry) ---
    # We prioritize 2.0 Flash for integrated Google Search research and high rate limits
    
    MAX_RETRIES_PER_MODEL = 3
    
    for model_name in model_names:
        for attempt in range(MAX_RETRIES_PER_MODEL):
            try:
                # Enable Google Search for fact-checking / research in PRO mode
                # NOTE: Google Search Tool is NOT compatible with response_mime_type='application/json' in current API
                use_search = (quality == "pro")
                tools = [types.Tool(google_search=types.GoogleSearch())] if use_search else None
                
                # If using tools (Search), we CANNOT force JSON mime type. We rely on the prompt.
                config = types.GenerateContentConfig(
                    response_mime_type='application/json' if not use_search else 'text/plain',
                    tools=tools
                )
                
                print(f"   🤖 Asking {model_name} (Attempt {attempt+1}/{MAX_RETRIES_PER_MODEL})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config
                )
                text = response.text
                
                # If we get here, it succeeded
                result = parse_ai_json(text)
                if result:
                    print(f"   ✅ Content generated with {model_name}")
                    return result
                    
            except Exception as e:
                # Cleaner Error Logging
                err_str = str(e).lower()
                clean_err = str(e)
                if hasattr(e, 'message'): clean_err = e.message
                elif hasattr(e, 'status'): clean_err = f"{e.status}: {getattr(e, 'message', '')}"
                
                # Improve readability of error
                if "400" in clean_err: clean_err = "400 Bad Request (Check config/params)"
                if "404" in clean_err: clean_err = f"404 Model {model_name} not found"
                
                is_quota = "quota" in err_str or "429" in err_str or "exhausted" in err_str
                
                if is_quota:
                    wait_time = 20 * (attempt + 1) # 20s, 40s, 60s
                    print(f"   ⚠️ Quota exceeded for {model_name}. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    # Loop continues to next attempt
                else:
                    print(f"   ⚠️ Error with {model_name}: {clean_err}")
                    # If it's not a quota error (e.g. invalid arg), break to next model
                    break
            
        # If we exhausted retries for this model, try the next one
    
    # If all models failed
    return "ERROR DE CUOTA AI", "Se ha alcanzado el límite de la versión gratuita en todos los modelos. Por favor, espera unos minutos.", "error", "error", "", "", "", "00:00", "END"

def parse_ai_json(text: str) -> Optional[Tuple]:
    """Helper to parse JSON from AI response robustly."""
    try:
        json_text = text
        if "```json" in text:
            json_text = text.split("```json")[1].split("```")[0].strip()
        elif "{" in text:
            json_text = text[text.find("{"):text.rfind("}")+1]
            
        data = json.loads(json_text)
        
        # If it's a cheap preview, headline and caption might be missing or under different keys
        headline = data.get('headline', data.get('plan_explicacion', 'NOTICIA ECONÓMIKA'))
        caption = data.get('caption', data.get('plan_explicacion', ''))
        
        return (
            headline, 
            caption, 
            data.get('slug', 'noticia'), 
            data.get('shorts_title', 'Noticia Economika'),
            data.get('caption_b', caption),
            data.get('source', ''),
            data.get('suggested_location_query', ''),
            data.get('best_segment_start', '00:00'),
            data.get('best_segment_end', 'END')
        )
    except Exception:
        return None

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
