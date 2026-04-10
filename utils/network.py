import requests
import logging
import subprocess
import os
import time
import sys

logger = logging.getLogger(__name__)

def check_centralai_health(url: str, auto_start: bool = True) -> bool:
    """
    Check the health of the CentralAIService and optionally attempt auto-start.
    
    Args:
        url: The base URL of the CentralAIService (e.g., http://localhost:8080)
        auto_start: Whether to attempt starting the service if unreachable on localhost.
        
    Returns:
        bool: True if the service is healthy (200 OK), False otherwise.
    """
    health_url = f"{url.rstrip('/')}/health"
    
    def _do_check():
        try:
            response = requests.get(health_url, timeout=3)
            return response.status_code == 200
        except (requests.ConnectionError, requests.Timeout):
            return False
        except Exception as e:
            logger.error(f"Unexpected error during health check: {e}")
            return False

    is_healthy = _do_check()
    
    if is_healthy:
        return True
    
    # Auto-start logic if unreachable and on localhost
    is_localhost = "localhost" in url or "127.0.0.1" in url
    if auto_start and is_localhost:
        print(f"WARNING: CentralAIService no responde en {url}. Intentando auto-arranque...")
        
        # Identify CentralAIService path (sibling directory)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        central_ai_path = os.path.abspath(os.path.join(base_dir, "..", "CentralAIService"))
        
        if os.path.exists(os.path.join(central_ai_path, "main.py")):
            try:
                # Launch uvicorn in a new minimized console window on Windows
                cmd = f'start /min "CentralAIService" python -m uvicorn main:app --port 8080'
                subprocess.Popen(cmd, shell=True, cwd=central_ai_path)
                
                print("WAIT: Esperando a que CentralAIService se levante (5s)...")
                time.sleep(5)
                
                # Retry health check
                if _do_check():
                    print("SUCCESS: CentralAIService arrancado y saludable.")
                    return True
                else:
                    logger.error("ERROR: El auto-arranque se ejecutó pero el servicio sigue sin responder.")
            except Exception as e:
                logger.error(f"❌ Error al intentar auto-arranque: {e}")
        else:
            logger.error(f"❌ No se encontró CentralAIService en: {central_ai_path}")
            
    return False
