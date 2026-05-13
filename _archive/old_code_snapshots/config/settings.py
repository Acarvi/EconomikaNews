import os
from dataclasses import dataclass
from typing import Optional


DEFAULT_CENTRAL_AI_SERVICE_URL = "http://localhost:8080"
DEFAULT_CENTRAL_PUBLISHING_HUB_URL = "http://localhost:8000"
DEFAULT_ECONOMIKA_ACCOUNT_ID = "economika"


@dataclass(frozen=True)
class Settings:
    central_ai_service_url: str
    central_publishing_hub_url: str
    economika_admin_api_key: Optional[str]
    economika_account_id: str


def _read_optional_env(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value is None:
        return None

    value = value.strip()
    return value or None


def _read_env(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    return value or default


def get_settings() -> Settings:
    return Settings(
        central_ai_service_url=_read_env(
            "CENTRAL_AI_SERVICE_URL",
            DEFAULT_CENTRAL_AI_SERVICE_URL,
        ),
        central_publishing_hub_url=_read_env(
            "CENTRAL_PUBLISHING_HUB_URL",
            DEFAULT_CENTRAL_PUBLISHING_HUB_URL,
        ),
        economika_admin_api_key=_read_optional_env("ECONOMIKA_ADMIN_API_KEY"),
        economika_account_id=_read_env(
            "ECONOMIKA_ACCOUNT_ID",
            DEFAULT_ECONOMIKA_ACCOUNT_ID,
        ),
    )
