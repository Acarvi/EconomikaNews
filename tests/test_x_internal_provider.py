import importlib

from app.ingestion import XInternalApiProvider as ExportedXInternalApiProvider
from app.ingestion.models import IngestionResult, SourceAccount
from app.ingestion.x_internal_api_provider import (
    XInternalApiProvider,
    normalize_x_internal_json,
    redact_secrets,
)


def test_provider_imports_and_name() -> None:
    provider = XInternalApiProvider(env={})

    assert provider.provider_name == "x_internal_api"
    assert ExportedXInternalApiProvider is XInternalApiProvider


def test_missing_env_returns_errors_not_crash() -> None:
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
    assert "X_INTERNAL_TIMELINE_URL" in result.errors[0]


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
