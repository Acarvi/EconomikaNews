from typing import Any, Dict, Optional

import requests

from config.settings import Settings, get_settings


DEFAULT_TIMEOUT = 30
API_PREFIX = "/api/v1"


def normalize_base_url(url: str) -> str:
    base_url = url.strip().rstrip("/")
    if base_url.endswith(API_PREFIX):
        return base_url[: -len(API_PREFIX)].rstrip("/")
    return base_url


class PublishingHubClient:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.settings = settings or get_settings()
        self.base_url = normalize_base_url(self.settings.central_publishing_hub_url)
        self.api_url = f"{self.base_url}{API_PREFIX}"
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        if not self.settings.economika_admin_api_key:
            return {}
        return {"X-API-Key": self.settings.economika_admin_api_key}

    def health(self) -> Dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/health",
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def publish(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            f"{self.api_url}/publish",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def schedule(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            f"{self.api_url}/schedule",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def queue(self) -> Dict[str, Any]:
        response = requests.get(
            f"{self.api_url}/queue",
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()


def health() -> Dict[str, Any]:
    return PublishingHubClient().health()


def publish(payload: Dict[str, Any]) -> Dict[str, Any]:
    return PublishingHubClient().publish(payload)


def schedule(payload: Dict[str, Any]) -> Dict[str, Any]:
    return PublishingHubClient().schedule(payload)


def queue() -> Dict[str, Any]:
    return PublishingHubClient().queue()
