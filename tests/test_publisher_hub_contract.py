from unittest.mock import Mock

import pytest

import core.publisher as publisher


def test_normalize_targets_default():
    assert publisher.normalize_targets(None) == ["instagram_reel"]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("instagram", "instagram_reel"),
        ("reel", "instagram_reel"),
        ("story", "instagram_story"),
        ("feed", "instagram_feed"),
        ("post", "instagram_feed"),
        ("instagram_post", "instagram_feed"),
        ("youtube", "youtube_shorts"),
        ("shorts", "youtube_shorts"),
    ],
)
def test_normalize_targets_aliases(source, expected):
    assert publisher.normalize_targets([source]) == [expected]


def test_build_publish_payload_with_video_path(monkeypatch):
    monkeypatch.setenv("ECONOMIKA_ACCOUNT_ID", "economika-test")

    payload = publisher.build_publish_payload(
        video_path="C:/videos/reel.mp4",
        caption="Caption",
        title="Title",
        targets=["instagram", "story", "youtube"],
    )

    assert payload == {
        "account_id": "economika-test",
        "video_path": "C:/videos/reel.mp4",
        "video_url": None,
        "caption": "Caption",
        "title": "Title",
        "targets": ["instagram_reel", "instagram_story", "youtube_shorts"],
        "publish_mode": "now",
        "scheduled_at": None,
        "platforms": ["instagram_reel", "instagram_story", "youtube_shorts"],
        "shorts_title": "Title",
        "target_time": None,
    }


def test_build_publish_payload_with_video_url():
    payload = publisher.build_publish_payload(
        video_url="https://cdn.example/video.mp4",
        caption="Caption",
        title="Title",
        targets=["shorts"],
        account_id="custom-account",
        publish_mode="scheduled",
        scheduled_at="2026-05-11T12:00:00Z",
    )

    assert payload["account_id"] == "custom-account"
    assert payload["video_path"] is None
    assert payload["video_url"] == "https://cdn.example/video.mp4"
    assert payload["targets"] == ["youtube_shorts"]
    assert payload["platforms"] == ["youtube_shorts"]
    assert payload["title"] == "Title"
    assert payload["shorts_title"] == "Title"
    assert payload["scheduled_at"] == "2026-05-11T12:00:00Z"


def test_publish_video_calls_publishing_hub_client_publish(monkeypatch):
    client = Mock()
    client.publish.return_value = {"status": "success"}
    client_cls = Mock(return_value=client)
    upload_mock = Mock(return_value="https://legacy.example/video.mp4")
    requests_post = Mock()
    monkeypatch.setattr(publisher, "PublishingHubClient", client_cls)
    monkeypatch.setattr(publisher, "upload_to_temporary_host", upload_mock)
    monkeypatch.setattr(publisher.requests, "post", requests_post)

    result = publisher.publish_video(
        "C:/videos/reel.mp4",
        "Caption",
        platform="instagram",
        title="Title",
    )

    assert result == {"status": "success"}
    client.publish.assert_called_once()
    payload = client.publish.call_args.args[0]
    assert payload["video_path"] == "C:/videos/reel.mp4"
    assert payload["video_url"] is None
    assert payload["targets"] == ["instagram_reel"]
    upload_mock.assert_not_called()
    requests_post.assert_not_called()


def test_schedule_publication_calls_publishing_hub_client_schedule(monkeypatch):
    client = Mock()
    client.schedule.return_value = {"status": "scheduled"}
    monkeypatch.setattr(publisher, "PublishingHubClient", Mock(return_value=client))
    monkeypatch.setattr(publisher, "upload_to_temporary_host", Mock())
    monkeypatch.setattr(publisher.requests, "post", Mock())

    result = publisher.schedule_publication(
        "C:/videos/reel.mp4",
        "Caption",
        platform="story",
        title="Title",
        target_time="2026-05-11T12:00:00Z",
    )

    assert result == {"status": "scheduled"}
    client.schedule.assert_called_once()
    payload = client.schedule.call_args.args[0]
    assert list(payload) == ["posts"]
    assert payload["posts"][0]["publish_mode"] == "scheduled"
    assert payload["posts"][0]["scheduled_at"] == "2026-05-11T12:00:00Z"
    assert payload["posts"][0]["targets"] == ["instagram_story"]


def test_publish_now_sends_multiple_targets_in_one_call(monkeypatch):
    client = Mock()
    client.publish.return_value = {"status": "success"}
    monkeypatch.setattr(publisher, "PublishingHubClient", Mock(return_value=client))
    monkeypatch.setattr(publisher, "upload_to_temporary_host", Mock())
    monkeypatch.setattr(publisher.requests, "post", Mock())

    result = publisher.publish_now(
        "C:/videos/reel.mp4",
        "Caption",
        ["instagram", "story", "shorts"],
        shorts_title="Shorts Title",
    )

    assert result == {"status": "success"}
    client.publish.assert_called_once()
    payload = client.publish.call_args.args[0]
    assert payload["targets"] == [
        "instagram_reel",
        "instagram_story",
        "youtube_shorts",
    ]
    assert payload["shorts_title"] == "Shorts Title"
