from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SourceAccount:
    handle: str
    category: str | None = None
    weight: float = 1.0
    followers_hint: int | None = None


@dataclass(frozen=True)
class SourceMedia:
    media_type: str
    url: str | None = None
    preview_url: str | None = None
    local_path: str | None = None


@dataclass(frozen=True)
class EngagementMetrics:
    likes: int | None = None
    reposts: int | None = None
    replies: int | None = None
    views: int | None = None


@dataclass(frozen=True)
class SourcePost:
    source: str
    post_id: str
    url: str
    author_handle: str
    text: str
    created_at: datetime | None
    captured_at: datetime
    media: list[SourceMedia] = field(default_factory=list)
    metrics: EngagementMetrics = field(default_factory=EngagementMetrics)
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class IngestionResult:
    account: SourceAccount
    posts: list[SourcePost]
    errors: list[str]
    provider_name: str
    captured_at: datetime
