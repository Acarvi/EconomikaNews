import importlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from app.ingestion import XInternalApiProvider as ExportedXInternalApiProvider
from app.ingestion.models import IngestionResult, SourceAccount
from app.ingestion.x_internal_api_provider import (
    XInternalApiProvider,
    normalize_x_internal_json,
    redact_headers,
    redact_secrets,
)
from app.ingestion.x_internal_errors import XInternalErrorKind
from app.ingestion.x_internal_timeline import (
    build_timeline_url,
    extract_user_id_from_timeline_url,
    parse_timeline_url,
)
from app.ingestion.x_internal_user_lookup import (
    build_user_lookup_url,
    extract_user_id_from_user_lookup_json,
    parse_user_lookup_url,
)


def _sample_timeline_url() -> str:
    query = urlencode(
        {
            "variables": json.dumps(
                {"userId": "111", "count": 20, "includePromotedContent": True}
            ),
            "features": json.dumps({"responsive_web_graphql_exclude_directive_enabled": True}),
            "fieldToggles": json.dumps({"withArticlePlainText": False}),
            "ignored": "kept-out-of-template",
        }
    )
    return f"https://x.com/i/api/graphql/abc123/UserTweets?{query}"


def _sample_user_lookup_url(variable_name: str = "screen_name") -> str:
    query = urlencode(
        {
            "variables": json.dumps(
                {variable_name: "wallstwolverine", "withGrokTranslatedBio": True}
            ),
            "features": json.dumps({"responsive_web_profile_redirect_enabled": False}),
            "fieldToggles": json.dumps({"withPayments": False}),
        }
    )
    return f"https://x.com/i/api/graphql/lookup123/UserByScreenName?{query}"


def _decoded_query_json(url: str, name: str) -> dict:
    raw = parse_qs(urlsplit(url).query)[name][-1]
    return json.loads(raw)


def test_parse_timeline_url_decodes_graphql_query_params() -> None:
    template = parse_timeline_url(_sample_timeline_url())

    assert template.base_url == "https://x.com/i/api/graphql/abc123/UserTweets"
    assert template.query_id == "abc123"
    assert template.operation_name == "UserTweets"
    assert template.variables["userId"] == "111"
    assert template.variables["count"] == 20
    assert template.features == {"responsive_web_graphql_exclude_directive_enabled": True}
    assert template.field_toggles == {"withArticlePlainText": False}


def test_build_timeline_url_replaces_user_id() -> None:
    template = parse_timeline_url(_sample_timeline_url())

    url = build_timeline_url(template, user_id="222")

    assert _decoded_query_json(url, "variables")["userId"] == "222"
    assert _decoded_query_json(url, "variables")["count"] == 20
    assert _decoded_query_json(url, "features") == template.features
    assert _decoded_query_json(url, "fieldToggles") == template.field_toggles
    assert "ignored" not in parse_qs(urlsplit(url).query)


def test_build_timeline_url_overrides_count() -> None:
    template = parse_timeline_url(_sample_timeline_url())

    url = build_timeline_url(template, user_id="222", count=50)

    assert _decoded_query_json(url, "variables")["count"] == 50


def test_extract_user_id_from_timeline_url() -> None:
    assert extract_user_id_from_timeline_url(_sample_timeline_url()) == "111"


def test_invalid_timeline_variables_json_raises_clear_error() -> None:
    url = "https://x.com/i/api/graphql/abc123/UserTweets?variables=%7B"

    try:
        parse_timeline_url(url)
    except ValueError as exc:
        assert "invalid variables JSON" in str(exc)
    else:
        raise AssertionError("expected invalid variables JSON error")


def test_parse_user_lookup_url_decodes_screen_name_template() -> None:
    template = parse_user_lookup_url(_sample_user_lookup_url())

    assert template.base_url == "https://x.com/i/api/graphql/lookup123/UserByScreenName"
    assert template.query_id == "lookup123"
    assert template.operation_name == "UserByScreenName"
    assert template.variables["screen_name"] == "wallstwolverine"
    assert template.features == {"responsive_web_profile_redirect_enabled": False}
    assert template.field_toggles == {"withPayments": False}


def test_build_user_lookup_url_replaces_screen_name() -> None:
    template = parse_user_lookup_url(_sample_user_lookup_url())

    url = build_user_lookup_url(template, "@economika_dev")

    assert _decoded_query_json(url, "variables")["screen_name"] == "economika_dev"
    assert _decoded_query_json(url, "variables")["withGrokTranslatedBio"] is True


def test_build_user_lookup_url_supports_screen_name_camel_case() -> None:
    template = parse_user_lookup_url(_sample_user_lookup_url("screenName"))

    url = build_user_lookup_url(template, "@economika_dev")

    assert _decoded_query_json(url, "variables")["screenName"] == "economika_dev"
    assert "screen_name" not in _decoded_query_json(url, "variables")


def test_extract_user_id_from_user_lookup_json_rest_id() -> None:
    payload = {"data": {"user": {"result": {"rest_id": "12345"}}}}

    assert extract_user_id_from_user_lookup_json(payload) == "12345"


def test_extract_user_id_from_user_lookup_json_legacy_fallbacks() -> None:
    assert (
        extract_user_id_from_user_lookup_json(
            {"data": {"user": {"result": {"legacy": {"id_str": "23456"}}}}}
        )
        == "23456"
    )
    assert (
        extract_user_id_from_user_lookup_json(
            {"data": {"user": {"result": {"legacy": {"user_id_str": "34567"}}}}}
        )
        == "34567"
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


def test_template_url_with_user_id_reaches_injected_opener() -> None:
    captured = {}

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return b'{"data":[]}'

    provider = XInternalApiProvider(
        env={
            "X_AUTH_TOKEN": "auth-secret",
            "X_CT0": "ct0-secret",
            "X_INTERNAL_TIMELINE_TEMPLATE_URL": _sample_timeline_url(),
            "X_INTERNAL_USER_ID": "999",
        },
        opener=opener,
    )

    provider.fetch_recent_posts(SourceAccount(handle="wallstwolverine"), 24)

    assert captured["timeout"] == 30.0
    assert captured["url"].startswith("https://x.com/i/api/graphql/abc123/UserTweets?")
    assert _decoded_query_json(captured["url"], "variables")["userId"] == "999"


def test_user_id_env_mode_still_wins_over_lookup_template() -> None:
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        return b'{"data":[]}'

    provider = XInternalApiProvider(
        env={
            "X_AUTH_TOKEN": "auth-secret",
            "X_CT0": "ct0-secret",
            "X_INTERNAL_TIMELINE_TEMPLATE_URL": _sample_timeline_url(),
            "X_INTERNAL_USER_ID": "999",
            "X_INTERNAL_USER_LOOKUP_TEMPLATE_URL": _sample_user_lookup_url(),
        },
        opener=opener,
    )

    provider.fetch_recent_posts(SourceAccount(handle="wallstwolverine"), 24)

    assert len(calls) == 1
    assert "UserTweets" in calls[0]
    assert _decoded_query_json(calls[0], "variables")["userId"] == "999"


def test_provider_resolves_user_id_then_fetches_timeline() -> None:
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        if "UserByScreenName" in request.full_url:
            return b'{"data":{"user":{"result":{"rest_id":"777"}}}}'
        return b'{"data":[]}'

    provider = XInternalApiProvider(
        env={
            "X_AUTH_TOKEN": "auth-secret",
            "X_CT0": "ct0-secret",
            "X_INTERNAL_TIMELINE_TEMPLATE_URL": _sample_timeline_url(),
            "X_INTERNAL_USER_LOOKUP_TEMPLATE_URL": _sample_user_lookup_url(),
        },
        opener=opener,
    )

    provider.fetch_recent_posts(SourceAccount(handle="@economika_dev"), 24)

    assert len(calls) == 2
    assert "UserByScreenName" in calls[0]
    assert _decoded_query_json(calls[0], "variables")["screen_name"] == "economika_dev"
    assert "UserTweets" in calls[1]
    assert _decoded_query_json(calls[1], "variables")["userId"] == "777"
    assert provider.last_resolved_user_id == "777"


def test_template_url_missing_user_id_returns_config_error() -> None:
    provider = XInternalApiProvider(
        env={
            "X_AUTH_TOKEN": "auth-secret",
            "X_CT0": "ct0-secret",
            "X_INTERNAL_TIMELINE_TEMPLATE_URL": _sample_timeline_url(),
        }
    )

    result = provider.fetch_recent_posts(SourceAccount(handle="wallstwolverine"), 24)

    assert result.posts == []
    assert "missing_config" in result.errors[0]
    assert "X_INTERNAL_USER_ID or X_INTERNAL_USER_LOOKUP_TEMPLATE_URL" in result.errors[0]
    assert "X_INTERNAL_TIMELINE_URL" not in result.errors[0]


def test_lookup_template_without_timeline_template_returns_config_error() -> None:
    provider = XInternalApiProvider(
        env={
            "X_AUTH_TOKEN": "auth-secret",
            "X_CT0": "ct0-secret",
            "X_INTERNAL_USER_LOOKUP_TEMPLATE_URL": _sample_user_lookup_url(),
        }
    )

    result = provider.fetch_recent_posts(SourceAccount(handle="wallstwolverine"), 24)

    assert result.posts == []
    assert "missing_config" in result.errors[0]
    assert "X_INTERNAL_TIMELINE_TEMPLATE_URL" in result.errors[0]


def test_invalid_template_url_returns_invalid_config_through_provider() -> None:
    provider = XInternalApiProvider(
        env={
            "X_AUTH_TOKEN": "auth-secret",
            "X_CT0": "ct0-secret",
            "X_INTERNAL_TIMELINE_TEMPLATE_URL": (
                "https://x.com/i/api/graphql/abc123/UserTweets?variables=%7B"
            ),
            "X_INTERNAL_USER_ID": "999",
        }
    )

    result = provider.fetch_recent_posts(SourceAccount(handle="wallstwolverine"), 24)

    assert result.posts == []
    assert result.errors[0].startswith(f"{XInternalErrorKind.INVALID_CONFIG}:")
    assert "invalid variables JSON" in result.errors[0]


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
    assert result.errors[0].startswith(f"{XInternalErrorKind.INVALID_CONFIG}:")
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


def test_create_x_headers_file_module_importable() -> None:
    module = importlib.import_module("scripts.create_x_headers_file")

    assert module


def test_create_x_probe_env_script_exists_without_real_secret_literals() -> None:
    script = Path("scripts/create_x_probe_env.ps1")
    text = script.read_text(encoding="utf-8")

    assert script.exists()
    assert 'X_INTERNAL_HEADERS_FILE = "runtime/secrets/x_headers.json"' in text
    assert "Read-Host" in text
    assert "python scripts\\x_internal_probe.py --handle wallstwolverine --lookback-hours 24 --print-json" in text
    assert not re.search(r"auth_token\s*=", text, flags=re.IGNORECASE)
    assert not re.search(r"ct0\s*=", text, flags=re.IGNORECASE)
    assert not re.search(r"bearer\s+[A-Za-z0-9._~+/=-]{12,}", text, flags=re.IGNORECASE)
    assert not re.search(r"cookie\s*[:=]", text, flags=re.IGNORECASE)
    assert not re.search(r"authorization\s*[:=]", text, flags=re.IGNORECASE)


def test_no_runtime_or_local_secret_files_tracked() -> None:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "runtime",
            "*/x_headers.json",
            "x_headers.json",
            ".env",
            ".env.*",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == ""
