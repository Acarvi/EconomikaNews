import pytest
from unittest.mock import patch, MagicMock
import requests
import os

# -----------------------------------------------------------------------------
# 1. TEST: FALLBACK WHISPER (SYSTEM ERROR / SOX MISSING)
# -----------------------------------------------------------------------------
@patch('core.subtitler.whisper.load_model')
def test_subtitler_whisper_system_error_robust(mock_whisper_load):
    """
    OBJETIVO: Evitar crash violento cuando faltan dependencias del sistema (SoX, FFmpeg).
    CRITERIO: Debe capturar Exception, loguear el WARN específico y devolver segments vacíos.
    """
    from core.subtitler import transcribe_audio
    import core.subtitler
    
    # Reset model state to ensure test isolation
    core.subtitler._model = None
    
    # Simulamos error de carga de Whisper (e.g. SoX no encontrado)
    mock_whisper_load.side_effect = Exception("No such file or directory: 'sox'")
    
    # Ejecución
    with patch('core.subtitler.os.path.exists', return_value=True):
        result = transcribe_audio("fake_video.mp4")
    
    # Verificación
    assert result == {'language': 'es', 'segments': []}
    # No debería haber lanzado excepción al llamador

# -----------------------------------------------------------------------------
# 2. TEST: PUBLISHER DELEGATION TO HUB (API SYNC)
# -----------------------------------------------------------------------------
@patch('core.publisher.requests.post')
@patch('core.publisher.upload_to_temporary_host')
def test_publisher_hub_delegation(mock_upload, mock_post):
    """
    OBJETIVO: Verificar que el publicador delega correctamente al Hub vía HTTP.
    CRITERIO: Debe enviar un POST al endpoint correcto con el payload esperado.
    """
    from core.publisher import publish_video
    
    # Mock Catbox upload
    mock_upload.return_value = "https://catbox.moe/test.mp4"
    
    # Mock Hub Response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success", "job_id": "123"}
    mock_post.return_value = mock_response
    
    # Ejecución
    result = publish_video("test.mp4", "Caption Test", platform="instagram", title="Shorts Title")
    
    # Verificación
    assert result['status'] == 'success'
    assert mock_post.called
    
    # Verificar URL y Payload
    args, kwargs = mock_post.call_args
    url = args[0]
    payload = kwargs['json']
    
    assert "/api/v1/publish-now" in url
    assert payload['video_url'] == "https://catbox.moe/test.mp4"
    assert payload['platforms'] == ["instagram"]
    assert payload['shorts_title'] == "Shorts Title"

# -----------------------------------------------------------------------------
# 3. TEST: PUBLISHER SCHEDULING DELEGATION
# -----------------------------------------------------------------------------
@patch('core.publisher.requests.post')
@patch('core.publisher.upload_to_temporary_host')
def test_publisher_scheduling_hub(mock_upload, mock_post):
    """
    OBJETIVO: Verificar que la programación también se delega al Hub.
    """
    from core.publisher import schedule_publication
    
    mock_upload.return_value = "https://catbox.moe/test.mp4"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    mock_post.return_value = mock_response
    
    # Ejecución
    result = schedule_publication("test.mp4", "Caption", target_time="2026-04-11T20:00:00")
    
    # Verificación
    assert result['status'] == 'success'
    args, kwargs = mock_post.call_args
    assert "/api/v1/schedule" in args[0]
    assert "posts" in kwargs['json']
    assert kwargs['json']['posts'][0]['target_time'] == "2026-04-11T20:00:00"
