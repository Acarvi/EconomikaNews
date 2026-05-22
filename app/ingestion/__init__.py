"""Normalized ingestion interfaces for source providers."""

from app.ingestion.fake_provider import FakeIngestionProvider
from app.ingestion.models import (
    EngagementMetrics,
    IngestionResult,
    SourceAccount,
    SourceMedia,
    SourcePost,
)
from app.ingestion.provider import IngestionProvider

__all__ = [
    "EngagementMetrics",
    "FakeIngestionProvider",
    "IngestionProvider",
    "IngestionResult",
    "SourceAccount",
    "SourceMedia",
    "SourcePost",
]
