from typing import Any, Dict, Optional

import requests

from config.settings import Settings, get_settings


DEFAULT_TIMEOUT = 30
GENERATE_DRAFT_TIMEOUT = 300
REFINE_TIMEOUT = 60


def normalize_base_url(url: str) -> str:
    return url.strip().rstrip("/")


class CentralAIClient:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.settings = settings or get_settings()
        self.base_url = normalize_base_url(self.settings.central_ai_service_url)
        self.timeout = timeout

    def health(self) -> Dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/health",
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def generate_draft(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/v1/analyzer/draft",
            json=payload,
            timeout=GENERATE_DRAFT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def refine(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/v1/analyzer/refine",
            json=payload,
            timeout=REFINE_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()


def health() -> Dict[str, Any]:
    return CentralAIClient().health()


def generate_draft(payload: Dict[str, Any]) -> Dict[str, Any]:
    return CentralAIClient().generate_draft(payload)


def refine(payload: Dict[str, Any]) -> Dict[str, Any]:
    return CentralAIClient().refine(payload)
