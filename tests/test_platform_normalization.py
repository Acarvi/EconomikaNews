import core.publisher
import server


def test_server_normalize_platform():
    assert server.normalize_platform("instagram") == "instagram_reel"
    assert server.normalize_platform("facebook") == "facebook_reel"
    assert server.normalize_platform("youtube") == "youtube_shorts"
    assert server.normalize_platform("instagram_reel") == "instagram_reel"


def test_publisher_normalize_platform():
    assert core.publisher._normalize_platform("instagram") == "instagram_reel"
    assert core.publisher._normalize_platform("facebook") == "facebook_reel"
    assert core.publisher._normalize_platform("youtube") == "youtube_shorts"
    assert core.publisher._normalize_platform("instagram_reel") == "instagram_reel"
