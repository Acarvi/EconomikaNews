from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.ingestion.models import (
    EngagementMetrics,
    IngestionResult,
    SourceAccount,
    SourceMedia,
    SourcePost,
)


class FakeIngestionProvider:
    provider_name = "fake"

    def fetch_recent_posts(
        self,
        account: SourceAccount,
        lookback_hours: int,
    ) -> IngestionResult:
        captured_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        handle = account.handle.lstrip("@")

        posts = [
            SourcePost(
                source="x",
                post_id=f"fake-{handle}-image-001",
                url=f"https://x.com/{handle}/status/fake-image-001",
                author_handle=handle,
                text="Sample image post for ingestion provider development.",
                created_at=captured_at - timedelta(hours=1),
                captured_at=captured_at,
                media=[
                    SourceMedia(
                        media_type="image",
                        url=f"https://example.test/{handle}/image-001.jpg",
                        preview_url=f"https://example.test/{handle}/image-001-preview.jpg",
                    )
                ],
                metrics=EngagementMetrics(
                    likes=120,
                    reposts=18,
                    replies=7,
                    views=9400,
                ),
                raw={
                    "provider": self.provider_name,
                    "lookback_hours": lookback_hours,
                    "fixture": "image",
                },
            ),
            SourcePost(
                source="x",
                post_id=f"fake-{handle}-video-001",
                url=f"https://x.com/{handle}/status/fake-video-001",
                author_handle=handle,
                text="Sample video post for ingestion provider development.",
                created_at=captured_at - timedelta(hours=2),
                captured_at=captured_at,
                media=[
                    SourceMedia(
                        media_type="video",
                        url=f"https://example.test/{handle}/video-001.mp4",
                        preview_url=f"https://example.test/{handle}/video-001-preview.jpg",
                    )
                ],
                metrics=EngagementMetrics(
                    likes=310,
                    reposts=44,
                    replies=21,
                    views=28100,
                ),
                raw={
                    "provider": self.provider_name,
                    "lookback_hours": lookback_hours,
                    "fixture": "video",
                },
            ),
        ]

        return IngestionResult(
            account=account,
            posts=posts,
            errors=[],
            provider_name=self.provider_name,
            captured_at=captured_at,
        )
