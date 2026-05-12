from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.viral_scout as viral_scout
from core.viral_scout import ViralScout, _is_recoverable_twikit_error
from services.discovery.models import XAccount
from services.discovery.x_sources import (
    BrowserXSource,
    TwikitXSource,
    calculate_viral_score,
    is_schema_failure,
)


def test_recoverable_twikit_error_helper_detects_schema_errors():
    assert _is_recoverable_twikit_error(KeyError("urls")) is True
    assert _is_recoverable_twikit_error(Exception("Couldn't get KEY_BYTE indices")) is True
    assert is_schema_failure(Exception("indices missing")) is True


def test_score_calculation_uses_product_formula():
    score = calculate_viral_score(reposts=25, likes=900, followers=10000)
    assert score == pytest.approx(5.0)


def test_twikit_source_normalizes_fake_tweet_to_candidate():
    media = MagicMock()
    media.type = "photo"
    media.media_url_https = "https://example.com/photo.jpg"

    tweet = MagicMock()
    tweet.id = "12345"
    tweet.media = [media]
    tweet.retweet_count = 25
    tweet.favorite_count = 900
    tweet.full_text = "Texto viral"

    source = TwikitXSource()
    candidate = source.normalize_tweet(
        tweet,
        XAccount(screen_name="testuser", followers_hint=10000),
        min_ratio=1.0,
    )

    assert candidate.url == "https://x.com/i/status/12345"
    assert candidate.score == pytest.approx(5.0)
    assert candidate.source == "twikit"
    assert candidate.media_url == "https://example.com/photo.jpg"


def test_browser_source_parser_extracts_status_urls_from_html():
    html = """
    <html><body>
      <a href="/wallstwolverine/status/111">tweet uno</a>
      <a href="https://x.com/wallstwolverine/status/222">tweet dos</a>
      <a href="/other/status/333">otro usuario</a>
    </body></html>
    """

    candidates = BrowserXSource.parse_status_urls_from_html(html, "wallstwolverine")

    assert [candidate.id for candidate in candidates] == ["111", "222"]
    assert candidates[0].source == "browser"
    assert candidates[0].score == 0.1


@pytest.mark.asyncio
async def test_auto_source_attempts_browser_after_twikit_schema_degraded(monkeypatch):
    monkeypatch.setenv("ECONOMIKA_DISCOVERY_MODE", "x")
    monkeypatch.setenv("ECONOMIKA_ENABLE_X_SCOUT", "true")
    monkeypatch.setenv("ECONOMIKA_X_SOURCE", "auto")

    scout = ViralScout()
    scout.accounts = {"one": 1000, "two": 1000, "three": 1000, "four": 1000}

    browser_hit = {
        "url": "https://x.com/one/status/999",
        "score": 0.1,
        "reposts": 0,
        "likes": 0,
        "user": "one",
        "source": "browser",
        "id": "999",
        "type": "TWEET",
        "is_video": False,
        "media_url": None,
        "thumbnail": None,
        "description": "fallback",
    }

    with patch('config.cookie_utils.get_cookies', return_value={'ct0': 'dummy'}):
        with patch('config.cookie_utils.netscape_to_json'):
            with patch('core.viral_scout.json.load', return_value={'ct0': 'dummy'}):
                with patch('core.viral_scout.Client') as mock_client_class:
                    mock_client = mock_client_class.return_value
                    mock_client.get_user_by_screen_name = AsyncMock(side_effect=Exception("Couldn't get KEY_BYTE indices"))
                    with patch.object(ViralScout, '_scan_nitter_rss', new_callable=AsyncMock) as mock_nitter:
                        mock_nitter.return_value = []
                        with patch.object(scout, '_scan_browser_x_source', AsyncMock(return_value=[browser_hit])) as mock_browser:
                            with patch('asyncio.sleep', return_value=None):
                                hits = await scout._scan_async(progress_callback=lambda _m: None, ignore_history=True)

    assert mock_client.get_user_by_screen_name.call_count == 6
    mock_browser.assert_awaited_once()
    assert hits == [browser_hit]


def test_debug_dump_only_written_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(viral_scout, "BASE_DIR", str(tmp_path))
    scout = ViralScout()

    scout._write_x_debug_dump("wallstwolverine", "KEY_BYTE", Exception("KEY_BYTE"))
    assert not (tmp_path / "debug").exists()

    monkeypatch.setenv("ECONOMIKA_DEBUG_X", "true")
    scout._write_x_debug_dump("wallstwolverine", "KEY_BYTE", Exception("KEY_BYTE"))

    debug_files = list((tmp_path / "debug").glob("x_response_wallstwolverine_*.txt"))
    assert len(debug_files) == 1
    assert "KEY_BYTE" in debug_files[0].read_text(encoding="utf-8")
