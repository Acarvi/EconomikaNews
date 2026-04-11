import pytest
import os
import sys
from unittest.mock import MagicMock, patch, ANY
import requests

"""
TESTS FUNCIONALES - ECONOMIKA NOTICIAS
Implementación completa con Mocks para validación de lógica de negocio.
"""

# -----------------------------------------------------------------------------
# 1. TEST: TRADUCCIÓN FORZADA A ESPAÑOL
# -----------------------------------------------------------------------------
@patch('core.subtitler.whisper.load_model')
@patch('google.genai.Client')
def test_subtitler_force_spanish_translation(mock_genai, mock_whisper_load):
    """
    OBJETIVO: Garantizar la consistencia de marca y línea editorial en español.
    """
    from core.subtitler import get_subtitles
    
    # Mock Whisper (Simulamos audio detectado como Inglés)
    mock_model = MagicMock()
    mock_whisper_load.return_value = mock_model
    mock_model.transcribe.return_value = {
        'language': 'en',
        'segments': [{'start': 0.0, 'end': 2.0, 'text': 'Hello world'}]
    }
    
    # Mock Gemini (Simulamos traducción a español)
    mock_genai_instance = mock_genai.return_value
    mock_response = MagicMock()
    mock_response.text = "<seg id=0>Hola mundo</seg>"
    mock_genai_instance.models.generate_content.return_value = mock_response
    
    # Ejecución
    with patch('core.subtitler.os.path.exists', return_value=True):
        subtitles = get_subtitles("fake_video.mp4")
    
    # Verificación
    # El primer segmento debería estar traducido (o al menos contener 'Hola')
    # Nota: split_segments puede dividirlo, así que buscamos la intención.
    texts = [s['text'].lower() for s in subtitles]
    assert any("hola" in t for t in texts), f"Esperaba traducción a español, recibí: {texts}"
    assert mock_genai_instance.models.generate_content.called

# -----------------------------------------------------------------------------
# 2. TEST: AUTO-ARRANQUE DE SERVICIOS (PRE-FLIGHT)
# -----------------------------------------------------------------------------
@patch('utils.network.requests.get')
@patch('utils.network.subprocess.Popen')
@patch('utils.network.time.sleep') 
def test_pre_flight_check_auto_start(mock_sleep, mock_popen, mock_get):
    """
    OBJETIVO: Resiliencia y auto-gestión de servicios locales.
    """
    from utils.network import check_centralai_health
    
    # Simulamos: 1º fallo de conexión, luego éxito tras auto-start
    # El auto-start hace varios checks, así que necesitamos una secuencia
    # 1. Check inicial (falla)
    # 2. Check en el loop de auto-start (falla)
    # 3. Check en el loop de auto-start (éxito)
    mock_response_ok = MagicMock()
    mock_response_ok.status_code = 200
    
    mock_get.side_effect = [
        requests.ConnectionError("Offline"), # Check inicial
        requests.ConnectionError("Still Offline"), # 1er reintento
        mock_response_ok # 2º reintento
    ]
    
    with patch('utils.network.os.path.exists', return_value=True):
        result = check_centralai_health("http://localhost:8080", auto_start=True)
    
    assert result is True
    assert mock_popen.called 
    # Verificamos que se usó sys.executable y el comando uicorn
    args, kwargs = mock_popen.call_args
    assert "uvicorn" in args[0]
    assert sys.executable in args[0]

# -----------------------------------------------------------------------------
# 3. TEST: FALLBACK Y RETRY DE CUOTA (429)
# -----------------------------------------------------------------------------
@patch('core.ai_handler.requests.post')
@patch('core.ai_handler.time.sleep')
def test_ai_handler_quota_fallback(mock_sleep, mock_post):
    """
    OBJETIVO: Gestión robusta de límites de la API de Gemini (Rate Limits).
    """
    from core.ai_handler import generate_content_ai
    
    # Simulamos: 429 (Rate Limit) -> 429 -> 200 (Success)
    mock_429 = MagicMock()
    mock_429.status_code = 429
    
    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.json.return_value = {'headline': 'Éxito tras retry'}
    
    mock_post.side_effect = [mock_429, mock_429, mock_200]
    
    tweet_data = {'description': 'Test data'}
    headline, _, _, _, _, _, _, _, _ = generate_content_ai(tweet_data)
    
    assert headline == 'Éxito tras retry'
    assert mock_post.call_count == 3
    assert mock_sleep.called

# -----------------------------------------------------------------------------
# 4. TEST: CONFORMACIÓN DE VIDEO A 30FPS
# -----------------------------------------------------------------------------
@patch('subprocess.run')
def test_video_conforming_30fps(mock_run):
    """
    OBJETIVO: Sincronización perfecta audio-subtítulos vía CFR.
    """
    from core.generator import conform_video_to_cfr
    
    # Simulamos ejecución exitosa de ffmpeg
    mock_run.return_value = MagicMock(returncode=0)
    
    input_path = "video_vfr.mp4"
    output_path = conform_video_to_cfr(input_path)
    
    # Verificamos que se llamó a ffmpeg con el filtro de fps
    assert mock_run.called
    cmd_args = mock_run.call_args[0][0]
    assert 'ffmpeg' in cmd_args
    assert 'fps=fps=30' in cmd_args
    assert output_path.endswith("_cfr.mp4")

# -----------------------------------------------------------------------------
# 5. TEST: INTEGRIDAD DEL SCRAPER DE X
# -----------------------------------------------------------------------------
@patch('core.viral_scout.Client')
def test_viral_scout_scraping_integrity(mock_twikit_client):
    """
    OBJETIVO: Detección temprana de obsolescencia del scraper de X.com.
    """
    from core.viral_scout import ViralScout
    import asyncio
    
    scout = ViralScout()
    
    # Mock del cliente Twikit para simular un error 404 (Estructura cambiada o recurso no encontrado)
    mock_instance = mock_twikit_client.return_value
    
    # get_user_by_screen_name es una corutina
    async def mock_fail(*args, **kwargs):
        raise Exception("404 Not Found - X API structure changed")
    
    mock_instance.get_user_by_screen_name.side_effect = mock_fail
    
    # Ejecutamos el scan (que es síncrono vía el wrapper)
    # Debería capturar el error y loguearlo, devolviendo lista vacía por ahora pero 
    # la intención es verificar que el error FLOTA o se LOGUEA adecuadamente.
    # Para este test, verificamos que el log o progreso recibe la alerta.
    
    logs = []
    def mock_progress(msg):
        logs.append(msg)
        
    hits = scout.scan(progress_callback=mock_progress)
    
    # Verificación: El error 404 debe aparecer en los logs de progreso
    assert len(hits) == 0
    assert any("404" in l or "Error inesperado" in l for l in logs)
    print("LOGS CAPTURADOS:", logs)
