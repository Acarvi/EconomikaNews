from __future__ import annotations

from enum import StrEnum


class XInternalErrorKind(StrEnum):
    MISSING_CONFIG = "missing_config"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    RATE_LIMITED = "rate_limited"
    CHALLENGE = "challenge"
    NETWORK = "network"
    INVALID_JSON = "invalid_json"
    UNKNOWN_SCHEMA = "unknown_schema"


def classify_http_error(status_code: int, body: str = "") -> XInternalErrorKind:
    if _looks_challenge_like(body):
        return XInternalErrorKind.CHALLENGE
    if status_code == 401:
        return XInternalErrorKind.UNAUTHORIZED
    if status_code == 403:
        return XInternalErrorKind.FORBIDDEN
    if status_code == 429:
        return XInternalErrorKind.RATE_LIMITED
    return XInternalErrorKind.NETWORK


def _looks_challenge_like(body: str) -> bool:
    lowered = body.lower()
    markers = (
        "captcha",
        "challenge",
        "account locked",
        "login verification",
        "suspicious activity",
        "verify your identity",
    )
    return any(marker in lowered for marker in markers)
