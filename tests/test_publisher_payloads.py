from unittest.mock import Mock

import core.publisher as publisher


def test_publish_video_normalizes_instagram_for_hub_client(monkeypatch):
    client = Mock()
    client.publish.return_value = {"status": "success"}
    monkeypatch.setattr(publisher, "PublishingHubClient", Mock(return_value=client))

    result = publisher.publish_video("video.mp4", "caption", platform="instagram", title="Title")

    assert result == {"status": "success"}
    client.publish.assert_called_once()
    payload = client.publish.call_args.args[0]
    assert payload["video_path"] == "video.mp4"
    assert payload["video_url"] is None
    assert payload["platforms"] == ["instagram_reel"]
    assert payload["targets"] == ["instagram_reel"]


def test_publish_video_normalizes_youtube_without_real_network(monkeypatch):
    client = Mock()
    client.publish.return_value = {"status": "success"}
    post_mock = Mock()
    monkeypatch.setattr(publisher, "PublishingHubClient", Mock(return_value=client))
    monkeypatch.setattr(publisher.requests, "post", post_mock)
    upload_mock = Mock()
    monkeypatch.setattr(publisher, "upload_to_temporary_host", upload_mock)

    publisher.publish_video("video.mp4", "caption", platform="youtube", title="Title")

    client.publish.assert_called_once()
    payload = client.publish.call_args.args[0]
    assert payload["platforms"] == ["youtube_shorts"]
    assert payload["targets"] == ["youtube_shorts"]
    upload_mock.assert_not_called()
    post_mock.assert_not_called()
