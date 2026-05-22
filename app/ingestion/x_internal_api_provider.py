from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from app.ingestion.models import (
    EngagementMetrics,
    IngestionResult,
    SourceAccount,
    SourceMedia,
    SourcePost,
)
from app.ingestion.x_internal_errors import (
    XInternalErrorKind,
    classify_http_error,
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
SECRET_ENV_VARS = (
    "X_AUTH_TOKEN",
    "X_CT0",
    "X_BEARER_TOKEN",
    "X_COOKIE_STRING",
)
SENSITIVE_HEADER_KEYS = {
    "authorization",
    "cookie",
    "x-csrf-token",
}


@dataclass(frozen=True)
class XInternalConfig:
    auth_token: str | None
    ct0: str | None
    bearer_token: str | None
    cookie_string: str | None
    user_agent: str | None
    timeline_url: str | None
    timeline_variables: str | None
    timeline_features: str | None
    headers_file: str | None


class XInternalApiProvider:
    provider_name = "x_internal_api"

    def __init__(
        self,
        env: Mapping[str, str] | None = None,
        opener: Callable[[Request, float], bytes] | None = None,
    ) -> None:
        self._env = env if env is not None else os.environ
        self._opener = opener or _default_opener

    def fetch_recent_posts(
        self,
        account: SourceAccount,
        lookback_hours: int,
    ) -> IngestionResult:
        captured_at = datetime.now(UTC)
        config = self._config_from_env()
        errors = self._missing_config_errors(config)
        if errors:
            return _error_result(account, errors, self.provider_name, captured_at)

        base_headers = None
        if config.headers_file:
            base_headers, header_errors = _load_headers_file(config.headers_file)
            if header_errors:
                return _error_result(account, header_errors, self.provider_name, captured_at)

        url = _build_timeline_url(config, account, lookback_hours)
        headers = _build_headers(config, base_headers)

        try:
            body = self._opener(Request(url, headers=headers, method="GET"), 30.0)
        except HTTPError as exc:
            response_body = _safe_decode(exc.read(4096))
            kind = classify_http_error(exc.code, response_body)
            error = (
                f"{kind}: X returned HTTP {exc.code}: "
                f"{redact_secrets(response_body, self._env, headers)[:240]}"
            )
            return _error_result(account, [error], self.provider_name, captured_at)
        except URLError as exc:
            return _error_result(
                account,
                [
                    f"{XInternalErrorKind.NETWORK}: "
                    f"{redact_secrets(str(exc.reason), self._env, headers)}"
                ],
                self.provider_name,
                captured_at,
            )

        text = _safe_decode(body)
        if _looks_challenge_like(text):
            return _error_result(
                account,
                [f"{XInternalErrorKind.CHALLENGE}: challenge-like response returned by X"],
                self.provider_name,
                captured_at,
            )

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            return _error_result(
                account,
                [f"{XInternalErrorKind.INVALID_JSON}: response was not JSON: {exc}"],
                self.provider_name,
                captured_at,
            )

        posts = normalize_x_internal_json(payload, account, captured_at)
        errors = []
        if not posts:
            shape = summarize_json_shape(payload)
            errors.append(
                f"{XInternalErrorKind.UNKNOWN_SCHEMA}: no tweet-like structures found; "
                f"redacted shape={redact_secrets(json.dumps(shape, sort_keys=True), self._env, headers)}"
            )

        return IngestionResult(
            account=account,
            posts=posts,
            errors=errors,
            provider_name=self.provider_name,
            captured_at=captured_at,
        )

    def _config_from_env(self) -> XInternalConfig:
        return XInternalConfig(
            auth_token=_clean_env(self._env.get("X_AUTH_TOKEN")),
            ct0=_clean_env(self._env.get("X_CT0")),
            bearer_token=_clean_env(self._env.get("X_BEARER_TOKEN")),
            cookie_string=_clean_env(self._env.get("X_COOKIE_STRING")),
            user_agent=_clean_env(self._env.get("X_USER_AGENT")),
            timeline_url=_clean_env(self._env.get("X_INTERNAL_TIMELINE_URL")),
            timeline_variables=_clean_env(self._env.get("X_INTERNAL_TIMELINE_VARIABLES")),
            timeline_features=_clean_env(self._env.get("X_INTERNAL_TIMELINE_FEATURES")),
            headers_file=_clean_env(self._env.get("X_INTERNAL_HEADERS_FILE")),
        )

    @staticmethod
    def _missing_config_errors(config: XInternalConfig) -> list[str]:
        missing: list[str] = []
        if config.headers_file:
            if not config.timeline_url:
                missing.append("X_INTERNAL_TIMELINE_URL")
        else:
            if not config.auth_token:
                missing.append("X_AUTH_TOKEN")
            if not config.ct0:
                missing.append("X_CT0")
            if not config.timeline_url:
                missing.append("X_INTERNAL_TIMELINE_URL")
        if not missing:
            return []
        return [
            f"{XInternalErrorKind.MISSING_CONFIG}: missing env var(s): {', '.join(missing)}"
        ]


def redact_secrets(
    text: str,
    env: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
) -> str:
    redacted = text
    source = env if env is not None else os.environ
    for name in SECRET_ENV_VARS:
        value = _clean_env(source.get(name))
        if value:
            redacted = redacted.replace(value, "[REDACTED]")
    for key, value in (headers or {}).items():
        if key.lower() in SENSITIVE_HEADER_KEYS and value:
            redacted = redacted.replace(value, "[REDACTED]")

    patterns = (
        r"(auth_token=)[^;\s]+",
        r"(ct0=)[^;\s]+",
        r"(Bearer\s+)[A-Za-z0-9._~+/=-]+",
        r"((?:x-csrf-token|x-csrf-token:)\s*[=:]\s*)[^;,\s]+",
        r"((?:cookie|cookie:)\s*[=:]\s*)[^,\r\n]+",
        r"((?:authorization|authorization:)\s*[=:]\s*Bearer\s+)[^;,\s]+",
    )
    for pattern in patterns:
        redacted = re.sub(pattern, r"\1[REDACTED]", redacted, flags=re.IGNORECASE)
    return redacted


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    redacted = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADER_KEYS:
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = redact_secrets(value, headers=headers)
    return redacted


def normalize_x_internal_json(
    payload: Any,
    account: SourceAccount,
    captured_at: datetime,
) -> list[SourcePost]:
    posts: list[SourcePost] = []
    seen_ids: set[str] = set()
    for node in _walk_dicts(payload):
        post = _post_from_node(node, account, captured_at)
        if post is None or post.post_id in seen_ids:
            continue
        seen_ids.add(post.post_id)
        posts.append(post)
    return posts


def summarize_json_shape(value: Any, max_depth: int = 5, max_items: int = 8) -> Any:
    if max_depth <= 0:
        return type(value).__name__
    if isinstance(value, dict):
        return {
            str(key): summarize_json_shape(child, max_depth - 1, max_items)
            for key, child in list(value.items())[:max_items]
        }
    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "items": [
                summarize_json_shape(child, max_depth - 1, max_items)
                for child in value[:max_items]
            ],
        }
    return type(value).__name__


def _post_from_node(
    node: dict[str, Any],
    account: SourceAccount,
    captured_at: datetime,
) -> SourcePost | None:
    legacy = _as_dict(node.get("legacy"))
    tweet = legacy if _looks_like_tweet_legacy(legacy) else node
    if not _looks_like_tweet_legacy(tweet):
        return None

    post_id = _first_str(
        node.get("rest_id"),
        tweet.get("id_str"),
        tweet.get("conversation_id_str"),
        node.get("id_str"),
    )
    text = _extract_text(tweet, node)
    if not post_id or not text:
        return None

    author_handle = _extract_author_handle(node) or account.handle.lstrip("@")
    created_at = _parse_datetime(_first_str(tweet.get("created_at")))
    metrics = EngagementMetrics(
        likes=_first_int(tweet.get("favorite_count"), tweet.get("likes")),
        reposts=_first_int(tweet.get("retweet_count"), tweet.get("reposts")),
        replies=_first_int(tweet.get("reply_count"), tweet.get("replies")),
        views=_extract_views(node),
    )
    media = _extract_media(tweet)
    url = f"https://x.com/{author_handle}/status/{post_id}"

    return SourcePost(
        source="x",
        post_id=post_id,
        url=url,
        author_handle=author_handle,
        text=text,
        created_at=created_at,
        captured_at=captured_at,
        media=media,
        metrics=metrics,
        raw={"shape": summarize_json_shape(node, max_depth=3)},
    )


def _build_headers(
    config: XInternalConfig,
    base_headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    if base_headers is not None:
        headers = dict(base_headers)
    else:
        headers = {
            "accept": "application/json, text/plain, */*",
            "user-agent": config.user_agent or DEFAULT_USER_AGENT,
            "x-twitter-active-user": "yes",
            "x-twitter-client-language": "en",
        }
    if config.bearer_token:
        _set_header(headers, "authorization", f"Bearer {config.bearer_token}")
    if config.ct0:
        _set_header(headers, "x-csrf-token", config.ct0)
    if config.user_agent:
        _set_header(headers, "user-agent", config.user_agent)

    cookie = config.cookie_string or _get_header(headers, "cookie")
    if not cookie and base_headers is None:
        cookie_parts = []
        if config.auth_token:
            cookie_parts.append(f"auth_token={config.auth_token}")
        if config.ct0:
            cookie_parts.append(f"ct0={config.ct0}")
        cookie = "; ".join(cookie_parts)
    if cookie:
        _set_header(headers, "cookie", cookie)
    return headers


def _load_headers_file(headers_file: str | None) -> tuple[dict[str, str] | None, list[str]]:
    if not headers_file:
        return None, []

    path = Path(headers_file)
    if not path.exists():
        return None, [
            f"{XInternalErrorKind.INVALID_CONFIG}: X_INTERNAL_HEADERS_FILE does not exist: {path}"
        ]
    if not path.is_file():
        return None, [
            f"{XInternalErrorKind.INVALID_CONFIG}: X_INTERNAL_HEADERS_FILE is not a file: {path}"
        ]

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, [
            f"{XInternalErrorKind.INVALID_CONFIG}: could not read X_INTERNAL_HEADERS_FILE: {exc}"
        ]
    except json.JSONDecodeError as exc:
        return None, [
            f"{XInternalErrorKind.INVALID_CONFIG}: X_INTERNAL_HEADERS_FILE is not valid JSON: {exc}"
        ]

    if not isinstance(payload, dict):
        return None, [
            f"{XInternalErrorKind.INVALID_CONFIG}: X_INTERNAL_HEADERS_FILE must contain a JSON object"
        ]

    headers: dict[str, str] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, str):
            return None, [
                f"{XInternalErrorKind.INVALID_CONFIG}: X_INTERNAL_HEADERS_FILE must map strings to strings"
            ]
        headers[key] = value
    return headers, []


def _build_timeline_url(
    config: XInternalConfig,
    account: SourceAccount,
    lookback_hours: int,
) -> str:
    assert config.timeline_url is not None
    _ = account, lookback_hours
    parts = urlsplit(config.timeline_url)
    query: dict[str, str] = {}
    if parts.query:
        query.update(
            {
                key: value[-1]
                for key, value in parse_qs(
                    parts.query,
                    keep_blank_values=True,
                ).items()
            }
        )
    if config.timeline_variables and "variables" not in query:
        query["variables"] = config.timeline_variables
    if config.timeline_features and "features" not in query:
        query["features"] = config.timeline_features
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def _default_opener(request: Request, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _get_header(headers: Mapping[str, str], key: str) -> str | None:
    lowered = key.lower()
    for header_key, value in headers.items():
        if header_key.lower() == lowered:
            return value
    return None


def _set_header(headers: dict[str, str], key: str, value: str) -> None:
    lowered = key.lower()
    for header_key in list(headers):
        if header_key.lower() == lowered:
            headers[header_key] = value
            return
    headers[key] = value


def _error_result(
    account: SourceAccount,
    errors: list[str],
    provider_name: str,
    captured_at: datetime,
) -> IngestionResult:
    return IngestionResult(
        account=account,
        posts=[],
        errors=errors,
        provider_name=provider_name,
        captured_at=captured_at,
    )


def _walk_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            found.append(current)
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return found


def _looks_like_tweet_legacy(value: dict[str, Any]) -> bool:
    return bool(
        value
        and (
            "full_text" in value
            or "text" in value
            or "id_str" in value
            or "conversation_id_str" in value
        )
    )


def _extract_text(tweet: dict[str, Any], node: dict[str, Any]) -> str | None:
    note_tweet = _as_dict(node.get("note_tweet"))
    note_results = _as_dict(note_tweet.get("note_tweet_results"))
    note_result = _as_dict(note_results.get("result"))
    return _first_str(
        _as_dict(note_result.get("text")).get("text"),
        note_result.get("text"),
        tweet.get("full_text"),
        tweet.get("text"),
    )


def _extract_author_handle(node: dict[str, Any]) -> str | None:
    core = _as_dict(node.get("core"))
    user_results = _as_dict(core.get("user_results"))
    user_result = _as_dict(user_results.get("result"))
    user_legacy = _as_dict(user_result.get("legacy"))
    return _first_str(user_legacy.get("screen_name"), node.get("screen_name"))


def _extract_views(node: dict[str, Any]) -> int | None:
    views = _as_dict(node.get("views"))
    return _first_int(views.get("count"), views.get("state"))


def _extract_media(tweet: dict[str, Any]) -> list[SourceMedia]:
    media_items: list[SourceMedia] = []
    entities = _as_dict(tweet.get("extended_entities")) or _as_dict(tweet.get("entities"))
    for item in _as_list(entities.get("media")):
        media = _as_dict(item)
        media_type = _first_str(media.get("type")) or "unknown"
        if media_type == "photo":
            media_type = "image"
        elif media_type not in {"image", "video"}:
            media_type = "unknown"

        video_info = _as_dict(media.get("video_info"))
        variants = _as_list(video_info.get("variants"))
        video_url = _first_str(
            *[
                _as_dict(variant).get("url")
                for variant in variants
                if _as_dict(variant).get("url")
            ]
        )
        media_items.append(
            SourceMedia(
                media_type=media_type,
                url=video_url or _first_str(media.get("media_url_https"), media.get("media_url")),
                preview_url=_first_str(media.get("media_url_https"), media.get("media_url")),
            )
        )
    return media_items


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _looks_challenge_like(text: str) -> bool:
    return classify_http_error(200, text) == XInternalErrorKind.CHALLENGE


def _safe_decode(value: bytes) -> str:
    return value.decode("utf-8", errors="replace")


def _clean_env(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_str(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
        if isinstance(value, int):
            return str(value)
    return None


def _first_int(*values: Any) -> int | None:
    for value in values:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None
