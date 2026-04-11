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

    if _do_check():
        return True
    
    # Auto-start logic if unreachable and on localhost
    is_localhost = "localhost" in url or "127.0.0.1" in url
    if auto_start and is_localhost:
        print(f"\n⚠️  [PRE-FLIGHT] CentralAIService no responde en {url}.")
        print(f"🚀 Intentando auto-arranque en segundo plano...")
        
        # Identify CentralAIService path (sibling directory)
        # Assumes EconomikaNoticias and CentralAIService share the same parent folder
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        central_ai_path = os.path.abspath(os.path.join(base_dir, "..", "CentralAIService"))
        
        if os.path.exists(os.path.join(central_ai_path, "main.py")):
            try:
                # Launch uvicorn in a new minimized console window on Windows
                # Use sys.executable to ensure we use the same Python environment
                cmd = f'start /min "CentralAIService" {sys.executable} -m uvicorn main:app --port 8080'
                subprocess.Popen(cmd, shell=True, cwd=central_ai_path)
                
                # Retry loop: 4 attempts, every 2 seconds
                for i in range(1, 5):
                    print(f"⏳ [WAIT] Esperando respuesta del servicio... (intento {i}/4)")
                    time.sleep(2)
                    if _do_check():
                        print("✅ [SUCCESS] CentralAIService arrancado y saludable.")
                        return True
                
                logger.error("❌ [TIMEOUT] El servicio se ejecutó pero sigue sin responder.")
            except Exception as e:
                logger.error(f"💥 [ERROR] Error fatal al intentar auto-arranque: {e}")
        else:
            logger.error(f"🚫 [ERROR] Ruta no encontrada: {central_ai_path}")
            
    return False

def check_publishing_hub_health(url: str, auto_start: bool = True) -> bool:
    """
    Check the health of the CentralPublishingHub and optionally attempt auto-start.
    
    Args:
        url: The base URL of the Hub (e.g., http://localhost:8000)
        auto_start: Whether to attempt starting the service if unreachable on localhost.
    """
    # Ensure we use the base URL for health check, not the API v1 path
    base_url = url.split("/api/v1")[0].rstrip("/")
    health_url = f"{base_url}/health"
    
    def _do_check():
        try:
            response = requests.get(health_url, timeout=3)
            return response.status_code == 200
        except:
            return False

    if _do_check():
        return True
    
    # Auto-start logic if unreachable and on localhost
    is_localhost = "localhost" in url or "127.0.0.1" in url
    if auto_start and is_localhost:
        print(f"\n⚠️  [PRE-FLIGHT] CentralPublishingHub no responde en {base_url}.")
        print(f"🚀 Intentando auto-arranque en segundo plano...")
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Assumes the Hub is in a sibling directory named CentralPublishingHub
        hub_path = os.path.abspath(os.path.join(base_dir, "..", "CentralPublishingHub"))
        
        if os.path.exists(os.path.join(hub_path, "main.py")):
            try:
                # Launch uvicorn on port 8000 for the Hub
                cmd = f'start /min "CentralPublishingHub" {sys.executable} -m uvicorn main:app --port 8000'
                subprocess.Popen(cmd, shell=True, cwd=hub_path)
                
                # Retry loop
                for i in range(1, 5):
                    print(f"⏳ [WAIT] Esperando respuesta del Hub... (intento {i}/4)")
                    time.sleep(2)
                    if _do_check():
                        print("✅ [SUCCESS] CentralPublishingHub arrancado y saludable.")
                        return True
                
                logger.error("❌ [TIMEOUT] El Hub se ejecutó pero sigue sin responder.")
            except Exception as e:
                logger.error(f"💥 [ERROR] Error fatal al intentar auto-arranque del Hub: {e}")
        else:
            logger.error(f"🚫 [ERROR] Ruta del Hub no encontrada: {hub_path}")
            
    return False
