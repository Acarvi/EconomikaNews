import requests
import logging

logger = logging.getLogger(__name__)

def check_centralai_health(url: str) -> bool:
    """
    Check the health of the CentralAIService.
    
    Args:
        url: The base URL of the CentralAIService (e.g., http://localhost:8080)
        
    Returns:
        bool: True if the service is healthy (200 OK), False otherwise.
    """
    health_url = f"{url.rstrip('/')}/health"
    try:
        response = requests.get(health_url, timeout=3)
        if response.status_code == 200:
            return True
        else:
            logger.error(f"CentralAIService health check failed with status code: {response.status_code}")
            return False
    except (requests.ConnectionError, requests.Timeout) as e:
        logger.error(f"CentralAIService health check failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during CentralAIService health check: {e}")
        return False
