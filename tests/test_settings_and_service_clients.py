from unittest.mock import Mock

from config.settings import (
    DEFAULT_CENTRAL_AI_SERVICE_URL,
    DEFAULT_CENTRAL_PUBLISHING_HUB_URL,
    DEFAULT_ECONOMIKA_ACCOUNT_ID,
    Settings,
    get_settings,
)
from services.central_ai_client import CentralAIClient
from services.publishing_hub_client import PublishingHubClient


def _response(payload):
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("CENTRAL_AI_SERVICE_URL", raising=False)
    monkeypatch.delenv("CENTRAL_PUBLISHING_HUB_URL", raising=False)
    monkeypatch.delenv("ECONOMIKA_ADMIN_API_KEY", raising=False)
    monkeypatch.delenv("ECONOMIKA_ACCOUNT_ID", raising=False)

    settings = get_settings()

    assert settings.central_ai_service_url == DEFAULT_CENTRAL_AI_SERVICE_URL
    assert settings.central_publishing_hub_url == DEFAULT_CENTRAL_PUBLISHING_HUB_URL
    assert settings.economika_admin_api_key is None
    assert settings.economika_account_id == DEFAULT_ECONOMIKA_ACCOUNT_ID


def test_service_url_normalization():
    settings = Settings(
        central_ai_service_url="http://localhost:8080/",
        central_publishing_hub_url="http://localhost:8000/api/v1/",
        economika_admin_api_key=None,
        economika_account_id="economika",
    )

    ai_client = CentralAIClient(settings=settings)
    hub_client = PublishingHubClient(settings=settings)

    assert ai_client.base_url == "http://localhost:8080"
    assert hub_client.base_url == "http://localhost:8000"
    assert hub_client.api_url == "http://localhost:8000/api/v1"


def test_publishing_hub_includes_api_key_header(monkeypatch):
    monkeypatch.setenv("CENTRAL_PUBLISHING_HUB_URL", "http://hub.test/api/v1")
    monkeypatch.setenv("ECONOMIKA_ADMIN_API_KEY", "secret-test-key")

    response = _response({"job_id": "job-1", "status": "queued"})
    post_mock = Mock(return_value=response)
    monkeypatch.setattr("services.publishing_hub_client.requests.post", post_mock)

    result = PublishingHubClient().publish({"caption": "hello"})

    assert result == {"job_id": "job-1", "status": "queued"}
    post_mock.assert_called_once_with(
        "http://hub.test/api/v1/publish",
        json={"caption": "hello"},
        headers={"X-API-Key": "secret-test-key"},
        timeout=30,
    )


def test_clients_use_mocked_requests(monkeypatch):
    ai_response = _response({"headline": "Draft"})
    hub_response = _response({"jobs": []})
    ai_post_mock = Mock(return_value=ai_response)
    hub_get_mock = Mock(return_value=hub_response)
    monkeypatch.setattr("services.central_ai_client.requests.post", ai_post_mock)
    monkeypatch.setattr("services.publishing_hub_client.requests.get", hub_get_mock)

    ai_client = CentralAIClient(
        settings=Settings(
            central_ai_service_url="http://ai.test/",
            central_publishing_hub_url="http://hub.test/",
            economika_admin_api_key=None,
            economika_account_id="economika",
        )
    )
    hub_client = PublishingHubClient(
        settings=Settings(
            central_ai_service_url="http://ai.test/",
            central_publishing_hub_url="http://hub.test/",
            economika_admin_api_key=None,
            economika_account_id="economika",
        )
    )

    assert ai_client.generate_draft({"source_url": "https://example.test"}) == {
        "headline": "Draft"
    }
    assert hub_client.queue() == {"jobs": []}
    ai_post_mock.assert_called_once()
    hub_get_mock.assert_called_once()
