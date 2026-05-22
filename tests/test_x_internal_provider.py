import importlib
import json
from pathlib import Path

from app.ingestion import XInternalApiProvider as ExportedXInternalApiProvider
from app.ingestion.models import IngestionResult, SourceAccount
from app.ingestion.x_internal_api_provider import (
    XInternalApiProvider,
    normalize_x_internal_json,
    redact_headers,
    redact_secrets,
)


def test_provider_imports_and_name() -> None:
    provider = XInternalApiProvider(env={})

    assert provider.provider_name == "x_internal_api"
    assert ExportedXInternalApiProvider is XInternalApiProvider


def test_missing_env_without_headers_file_requires_auth_ct0_and_timeline() -> None:
    provider = XInternalApiProvider(env={})

    result = provider.fetch_recent_posts(
        account=SourceAccount(handle="economika_dev"),
        lookback_hours=24,
    )

    assert isinstance(result, IngestionResult)
    assert result.provider_name == "x_internal_api"
    assert result.posts == []
    assert result.errors
    assert "missing_config" in result.errors[0]
    assert "X_AUTH_TOKEN" in result.errors[0]
    assert "X_CT0" in result.errors[0]
    assert "X_INTERNAL_TIMELINE_URL" in result.errors[0]


def test_headers_file_without_auth_env_reaches_injected_opener(tmp_path: Path) -> None:
    headers_file = tmp_path / "x_headers.json"
    headers_file.write_text(
        json.dumps(
            {
                "authorization": "Bearer file-token",
                "cookie": "auth_token=file-auth; ct0=file-ct0",
                "referer": "https://x.com/wallstwolverine",
                "x-csrf-token": "file-ct0",
                "user-agent": "file-agent",
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    def opener(request, timeout):
        captured["timeout"] = timeout
        captured["headers"] = {
            key.lower(): value
            for key, value in request.header_items()
        }
        return b'{"data":[]}'

    provider = XInternalApiProvider(
        env={
            "X_INTERNAL_HEADERS_FILE": str(headers_file),
            "X_INTERNAL_TIMELINE_URL": "https://x.com/i/api/graphql/query/UserTweets",
        },
        opener=opener,
    )

    provider.fetch_recent_posts(SourceAccount(handle="wallstwolverine"), 24)

    assert captured["timeout"] == 30.0
    assert captured["headers"]["authorization"] == "Bearer file-token"
    assert captured["headers"]["cookie"] == "auth_token=file-auth; ct0=file-ct0"
    assert captured["headers"]["referer"] == "https://x.com/wallstwolverine"
    assert captured["headers"]["x-csrf-token"] == "file-ct0"
    assert captured["headers"]["user-agent"] == "file-agent"


def test_no_headers_file_still_requires_auth_ct0_and_timeline() -> None:
    provider = XInternalApiProvider(
        env={
            "X_INTERNAL_TIMELINE_URL": "https://x.com/i/api/graphql/query/UserTweets",
        }
    )

    result = provider.fetch_recent_posts(SourceAccount(handle="wallstwolverine"), 24)

    assert result.posts == []
    assert "missing_config" in result.errors[0]
    assert "X_AUTH_TOKEN" in result.errors[0]
    assert "X_CT0" in result.errors[0]


def test_headers_file_still_requires_timeline_url(tmp_path: Path) -> None:
    headers_file = tmp_path / "x_headers.json"
    headers_file.write_text(json.dumps({"accept": "application/json"}), encoding="utf-8")
    provider = XInternalApiProvider(
        env={
            "X_INTERNAL_HEADERS_FILE": str(headers_file),
        }
    )

    result = provider.fetch_recent_posts(SourceAccount(handle="wallstwolverine"), 24)

    assert result.posts == []
    assert "missing_config" in result.errors[0]
    assert "X_INTERNAL_TIMELINE_URL" in result.errors[0]
    assert "X_AUTH_TOKEN" not in result.errors[0]
    assert "X_CT0" not in result.errors[0]


def test_missing_headers_file_returns_config_error_not_crash(tmp_path: Path) -> None:
    provider = XInternalApiProvider(
        env={
            "X_INTERNAL_HEADERS_FILE": str(tmp_path / "missing.json"),
            "X_INTERNAL_TIMELINE_URL": "https://x.com/i/api/graphql/query/UserTweets",
        }
    )

    result = provider.fetch_recent_posts(SourceAccount(handle="wallstwolverine"), 24)

    assert result.posts == []
    assert "invalid_config" in result.errors[0]
    assert "does not exist" in result.errors[0]


def test_invalid_headers_file_returns_invalid_config(tmp_path: Path) -> None:
    headers_file = tmp_path / "x_headers.json"
    headers_file.write_text("{", encoding="utf-8")
    provider = XInternalApiProvider(
        env={
            "X_INTERNAL_HEADERS_FILE": str(headers_file),
            "X_INTERNAL_TIMELINE_URL": "https://x.com/i/api/graphql/query/UserTweets",
        }
    )

    result = provider.fetch_recent_posts(SourceAccount(handle="wallstwolverine"), 24)

    assert result.posts == []
    assert "invalid_config" in result.errors[0]
    assert "not valid JSON" in result.errors[0]


def test_non_object_headers_file_returns_config_error(tmp_path: Path) -> None:
    headers_file = tmp_path / "x_headers.json"
    headers_file.write_text("[]", encoding="utf-8")
    provider = XInternalApiProvider(
        env={
            "X_INTERNAL_HEADERS_FILE": str(headers_file),
            "X_INTERNAL_TIMELINE_URL": "https://x.com/i/api/graphql/query/UserTweets",
        }
    )

    result = provider.fetch_recent_posts(SourceAccount(handle="wallstwolverine"), 24)

    assert result.posts == []
    assert "invalid_config" in result.errors[0]
    assert "JSON object" in result.errors[0]


def test_non_string_header_value_returns_config_error(tmp_path: Path) -> None:
    headers_file = tmp_path / "x_headers.json"
    headers_file.write_text('{"accept": 123}', encoding="utf-8")
    provider = XInternalApiProvider(
        env={
            "X_INTERNAL_HEADERS_FILE": str(headers_file),
            "X_INTERNAL_TIMELINE_URL": "https://x.com/i/api/graphql/query/UserTweets",
        }
    )

    result = provider.fetch_recent_posts(SourceAccount(handle="wallstwolverine"), 24)

    assert result.posts == []
    assert "invalid_config" in result.errors[0]
    assert "strings to strings" in result.errors[0]


def test_env_overrides_headers_file_for_sensitive_headers(tmp_path: Path) -> None:
    headers_file = tmp_path / "x_headers.json"
    headers_file.write_text(
        json.dumps(
            {
                "authorization": "Bearer file-token",
                "cookie": "auth_token=file-auth; ct0=file-ct0",
                "x-csrf-token": "file-ct0",
                "user-agent": "file-agent",
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    def opener(request, timeout):
        captured["headers"] = {
            key.lower(): value
            for key, value in request.header_items()
        }
        return b'{"data":[]}'

    provider = XInternalApiProvider(
        env={
            "X_INTERNAL_HEADERS_FILE": str(headers_file),
            "X_INTERNAL_TIMELINE_URL": "https://x.com/i/api/graphql/query/UserTweets",
            "X_BEARER_TOKEN": "env-token",
            "X_CT0": "env-ct0",
            "X_USER_AGENT": "env-agent",
            "X_COOKIE_STRING": "auth_token=env-auth; ct0=env-ct0",
        },
        opener=opener,
    )

    provider.fetch_recent_posts(SourceAccount(handle="wallstwolverine"), 24)

    assert captured["headers"]["authorization"] == "Bearer env-token"
    assert captured["headers"]["cookie"] == "auth_token=env-auth; ct0=env-ct0"
    assert captured["headers"]["x-csrf-token"] == "env-ct0"
    assert captured["headers"]["user-agent"] == "env-agent"


def test_redaction_removes_cookie_and_bearer_values() -> None:
    env = {
        "X_AUTH_TOKEN": "auth-secret",
        "X_CT0": "ct0-secret",
        "X_BEARER_TOKEN": "bearer-secret",
        "X_COOKIE_STRING": "auth_token=auth-secret; ct0=ct0-secret",
    }
    text = (
        "authorization: Bearer bearer-secret; "
        "cookie: auth_token=auth-secret; ct0=ct0-secret"
    )

    redacted = redact_secrets(text, env)

    assert "auth-secret" not in redacted
    assert "ct0-secret" not in redacted
    assert "bearer-secret" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_headers_redacts_sensitive_header_values() -> None:
    headers = {
        "authorization": "Bearer file-token",
        "cookie": "auth_token=file-auth; ct0=file-ct0",
        "x-csrf-token": "file-ct0",
        "accept": "*/*",
    }

    redacted = redact_headers(headers)

    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["cookie"] == "[REDACTED]"
    assert redacted["x-csrf-token"] == "[REDACTED]"
    assert redacted["accept"] == "*/*"


def test_sample_json_parser_normalizes_tweet_like_payload() -> None:
    payload = {
        "data": {
            "user": {
                "result": {
                    "timeline": {
                        "entries": [
                            {
                                "content": {
                                    "itemContent": {
                                        "tweet_results": {
                                            "result": {
                                                "rest_id": "12345",
                                                "core": {
                                                    "user_results": {
                                                        "result": {
                                                            "legacy": {
                                                                "screen_name": "economika_dev"
                                                            }
                                                        }
                                                    }
                                                },
                                                "legacy": {
                                                    "id_str": "12345",
                                                    "full_text": "A useful macro thread.",
                                                    "created_at": (
                                                        "Wed Jan 01 12:00:00 +0000 2026"
                                                    ),
                                                    "favorite_count": 10,
                                                    "retweet_count": 2,
                                                    "reply_count": 1,
                                                    "extended_entities": {
                                                        "media": [
                                                            {
                                                                "type": "photo",
                                                                "media_url_https": (
                                                                    "https://example.test/a.jpg"
                                                                ),
                                                            }
                                                        ]
                                                    },
                                                },
                                                "views": {"count": "500"},
                                            }
                                        }
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
    }

    posts = normalize_x_internal_json(
        payload,
        account=SourceAccount(handle="fallback"),
        captured_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )

    assert len(posts) == 1
    assert posts[0].post_id == "12345"
    assert posts[0].author_handle == "economika_dev"
    assert posts[0].metrics.likes == 10
    assert posts[0].metrics.views == 500
    assert posts[0].media[0].media_type == "image"


def test_probe_script_module_importable() -> None:
    module = importlib.import_module("scripts.x_internal_probe")

    assert module
