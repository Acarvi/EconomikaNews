from app.ingestion import (
    EngagementMetrics,
    FakeIngestionProvider,
    IngestionProvider,
    IngestionResult,
    SourceAccount,
    SourceMedia,
    SourcePost,
)


def test_imports_expose_ingestion_contracts() -> None:
    assert SourceAccount
    assert SourceMedia
    assert EngagementMetrics
    assert SourcePost
    assert IngestionResult
    assert IngestionProvider
    assert FakeIngestionProvider


def test_fake_provider_returns_deterministic_result() -> None:
    account = SourceAccount(
        handle="economika_dev",
        category="economics",
        weight=1.25,
        followers_hint=1000,
    )
    provider = FakeIngestionProvider()

    result = provider.fetch_recent_posts(account=account, lookback_hours=24)

    assert isinstance(result, IngestionResult)
    assert result.account == account
    assert result.provider_name == "fake"
    assert result.errors == []
    assert len(result.posts) == 2
    assert [post.post_id for post in result.posts] == [
        "fake-economika_dev-image-001",
        "fake-economika_dev-video-001",
    ]


def test_fake_provider_includes_image_and_video_media() -> None:
    provider = FakeIngestionProvider()
    result = provider.fetch_recent_posts(
        account=SourceAccount(handle="@economika_dev"),
        lookback_hours=24,
    )

    media_types = {
        media.media_type
        for post in result.posts
        for media in post.media
    }

    assert "image" in media_types
    assert "video" in media_types
