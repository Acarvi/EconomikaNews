from unittest.mock import Mock

import core.publisher as publisher


def test_publish_video_normalizes_instagram_and_sends_admin_key(monkeypatch):
    monkeypatch.setenv("ECONOMIKA_ADMIN_API_KEY", "test-admin-key")
    monkeypatch.setattr(publisher, "check_publishing_hub_health", Mock(return_value=True))
    monkeypatch.setattr(publisher, "upload_to_temporary_host", Mock(return_value="https://cdn.example/video.mp4"))
    post_mock = Mock(return_value=Mock(json=Mock(return_value={"status": "success"})))
    monkeypatch.setattr(publisher.requests, "post", post_mock)

    result = publisher.publish_video("video.mp4", "caption", platform="instagram", title="Title")

    assert result == {"status": "success"}
    publisher.upload_to_temporary_host.assert_called_once_with("video.mp4")
    post_mock.assert_called_once()
    _, kwargs = post_mock.call_args
    assert kwargs["json"]["platforms"] == ["instagram_reel"]
    assert kwargs["headers"] == {"X-API-Key": "test-admin-key"}


def test_publish_video_normalizes_youtube_without_real_network(monkeypatch):
    monkeypatch.delenv("ECONOMIKA_ADMIN_API_KEY", raising=False)
    monkeypatch.setattr(publisher, "check_publishing_hub_health", Mock(return_value=True))
    monkeypatch.setattr(publisher, "upload_to_temporary_host", Mock(return_value="https://cdn.example/video.mp4"))
    post_mock = Mock(return_value=Mock(json=Mock(return_value={"status": "success"})))
    monkeypatch.setattr(publisher.requests, "post", post_mock)

    publisher.publish_video("video.mp4", "caption", platform="youtube", title="Title")

    publisher.upload_to_temporary_host.assert_called_once_with("video.mp4")
    post_mock.assert_called_once()
    _, kwargs = post_mock.call_args
    assert kwargs["json"]["platforms"] == ["youtube_shorts"]
    assert kwargs["headers"] == {}
