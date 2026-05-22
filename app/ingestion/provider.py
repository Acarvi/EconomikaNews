from __future__ import annotations

from typing import Protocol

from app.ingestion.models import IngestionResult, SourceAccount


class IngestionProvider(Protocol):
    provider_name: str

    def fetch_recent_posts(
        self,
        account: SourceAccount,
        lookback_hours: int,
    ) -> IngestionResult:
        ...
