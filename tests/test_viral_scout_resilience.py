import pytest
import asyncio
import inspect
from unittest.mock import MagicMock, patch, AsyncMock
import core.viral_scout as viral_scout
from core.viral_scout import ViralScout, _is_recoverable_twikit_error


SAMPLE_NEWS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Economia</title>
    <item>
      <title>El mercado laboral sorprende al alza</title>
      <link>https://example.com/economia/mercado-laboral</link>
      <description><![CDATA[<p>Datos economicos relevantes.</p><img src="https://example.com/image.jpg" />]]></description>
    </item>
  </channel>
</rss>
"""


class FakeRSSResponse:
    status_code = 200
    text = SAMPLE_NEWS_RSS


class FakeRSSClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url):
        return FakeRSSResponse()


def test_recoverable_twikit_error_helper_detects_schema_errors():
    assert _is_recoverable_twikit_error(KeyError("urls")) is True
    assert _is_recoverable_twikit_error(Exception("Couldn't get KEY_BYTE indices")) is True


def test_fallback_logging_does_not_reference_undefined_e():
    source = inspect.getsource(viral_scout.ViralScout._scan_async)
    assert "{e} | {e2}" not in source
    assert "{last_lookup_error} | {e2}" in source


@pytest.mark.asyncio
async def test_news_rss_fallback_parses_entries():
    scout = ViralScout()
    scout.load_news_sources = lambda: [{"name": "Test Economia", "url": "https://example.com/rss.xml"}]

    with patch('core.viral_scout.httpx.AsyncClient', FakeRSSClient):
        hits = await scout._scan_news_rss(progress_callback=lambda _m: None, ignore_history=True)

    assert len(hits) == 1
    assert hits[0]["url"] == "https://example.com/economia/mercado-laboral"
    assert hits[0]["user"] == "Test Economia"


@pytest.mark.asyncio
async def test_news_rss_candidate_has_required_fields():
    scout = ViralScout()
    scout.load_news_sources = lambda: [{"name": "Test Economia", "url": "https://example.com/rss.xml"}]

    with patch('core.viral_scout.httpx.AsyncClient', FakeRSSClient):
        hits = await scout._scan_news_rss(progress_callback=lambda _m: None, ignore_history=True)

    required = {"url", "score", "user", "source", "id", "type", "is_video", "media_url", "thumbnail", "description"}
    assert required.issubset(hits[0])
    assert hits[0]["id"].startswith("news-")


@pytest.mark.asyncio
async def test_scan_returns_news_fallback_when_x_paths_fail():
    with patch('core.viral_scout.Client') as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.get_user_by_screen_name = AsyncMock(side_effect=Exception("Couldn't get KEY_BYTE indices"))
        mock_client.search_user = AsyncMock(return_value=[])

        scout = ViralScout()
        scout.accounts = {"fail_user": 1000}
        scout.load_news_sources = lambda: [{"name": "Test Economia", "url": "https://example.com/rss.xml"}]

        with patch('config.cookie_utils.get_cookies', return_value={'ct0': 'dummy'}):
            with patch('config.cookie_utils.netscape_to_json'):
                with patch('core.viral_scout.json.load', return_value={'ct0': 'dummy'}):
                    with patch.object(ViralScout, '_scan_nitter_rss', new_callable=AsyncMock) as mock_nitter:
                        mock_nitter.return_value = []
                        with patch('core.viral_scout.httpx.AsyncClient', FakeRSSClient):
                            with patch('asyncio.sleep', return_value=None):
                                hits = await scout._scan_async(progress_callback=lambda _m: None, ignore_history=True)

        assert len(hits) == 1
        assert hits[0]["id"].startswith("news-")
        assert hits[0]["source"] == "Test Economia"

@pytest.mark.asyncio
async def test_viral_scout_retry_lookup_success():
    """Test that account lookup retries once on failure and then succeeds."""
    scout = ViralScout()
    scout.accounts = {"test_user": 1000}
    
    # Mocking the internal imports and Client class
    with patch('config.cookie_utils.get_cookies', return_value={'ct0': 'dummy'}):
        with patch('config.cookie_utils.netscape_to_json'):
            with patch('json.load', return_value={'ct0': 'dummy'}):
                with patch('core.viral_scout.Client') as mock_client_class:
                    mock_instance = mock_client_class.return_value
                    
                    mock_user = MagicMock()
                    mock_user.id = 123
                    mock_user.followers_count = 1000
                    
                    # Mocking get_user_by_screen_name to fail once then succeed
                    # It must be a coroutine
                    async def mock_lookup_side_effect(*args, **kwargs):
                        if mock_lookup_side_effect.call_count == 0:
                            mock_lookup_side_effect.call_count += 1
                            raise Exception("Couldn't get KEY_BYTE indices | status: 404")
                        return mock_user
                    mock_lookup_side_effect.call_count = 0
                    
                    mock_instance.get_user_by_screen_name = mock_lookup_side_effect
                    mock_instance.get_user_tweets = AsyncMock(return_value=[])
                    
                    logs = []
                    # Avoid sleep in tests
                    with patch('asyncio.sleep', return_value=None):
                        with patch.object(scout, '_scan_news_rss', AsyncMock(return_value=[])):
                            hits = await scout._scan_async(progress_callback=lambda m: logs.append(m))
                        
                        assert mock_lookup_side_effect.call_count == 1 # One failure, then success
                        assert any("reintentando en 5s" in l for l in logs)
                        assert len(hits) == 0

@pytest.mark.asyncio
async def test_viral_scout_skip_on_total_failure():
    """Test that an account is skipped with a warning after total lookup failure."""
    scout = ViralScout()
    scout.accounts = {"fail_user": 1000, "success_user": 1000}
    
    with patch('config.cookie_utils.get_cookies', return_value={'ct0': 'dummy'}):
        with patch('config.cookie_utils.netscape_to_json'):
            with patch('json.load', return_value={'ct0': 'dummy'}):
                with patch('core.viral_scout.Client') as mock_client_class:
                    mock_instance = mock_client_class.return_value
                    
                    mock_success_user = MagicMock()
                    mock_success_user.id = 456
                    mock_success_user.followers_count = 1000
                    
                    async def mock_lookup_side_effect(user_name, *args, **kwargs):
                        if user_name == "fail_user":
                            raise Exception("404 KEY_BYTE indices")
                        return mock_success_user
                    
                    mock_instance.get_user_by_screen_name = mock_lookup_side_effect
                    mock_instance.get_user_tweets = AsyncMock(return_value=[])
                    mock_instance.search_user = AsyncMock(return_value=[])
                    
                    logs = []
                    with patch.object(ViralScout, '_scan_nitter_rss', new_callable=AsyncMock) as mock_nitter:
                        mock_nitter.return_value = []
                        with patch('asyncio.sleep', return_value=None):
                            with patch.object(scout, '_scan_news_rss', AsyncMock(return_value=[])):
                                await scout._scan_async(progress_callback=lambda m: logs.append(m))
                            
                            # Verify User 1 was skipped with WARN
                            assert any("[WARN] Fallo scrapeando @fail_user" in l for l in logs)
                            # Verify it moved to success_user
                            assert any("Scanning @success_user" in l for l in logs)

@pytest.mark.asyncio
async def test_viral_scout_retry_tweets_success():
    """Test that tweet fetching retries once on failure and then succeeds."""
    scout = ViralScout()
    scout.accounts = {"test_user": 1000}
    
    with patch('config.cookie_utils.get_cookies', return_value={'ct0': 'dummy'}):
        with patch('config.cookie_utils.netscape_to_json'):
            with patch('json.load', return_value={'ct0': 'dummy'}):
                with patch('core.viral_scout.Client') as mock_client_class:
                    mock_instance = mock_client_class.return_value
                    
                    mock_user = MagicMock()
                    mock_user.id = 123
                    mock_user.followers_count = 1000
                    
                    mock_instance.get_user_by_screen_name = AsyncMock(return_value=mock_user)
                    
                    async def mock_tweets_side_effect(*args, **kwargs):
                        if mock_tweets_side_effect.call_count == 0:
                            mock_tweets_side_effect.call_count += 1
                            raise Exception("KEY_BYTE indices failure")
                        return []
                    mock_tweets_side_effect.call_count = 0
                    
                    mock_instance.get_user_tweets = mock_tweets_side_effect
                    
                    logs = []
                    with patch('asyncio.sleep', return_value=None):
                        with patch.object(scout, '_scan_news_rss', AsyncMock(return_value=[])):
                            await scout._scan_async(progress_callback=lambda m: logs.append(m))
                        
                        assert mock_tweets_side_effect.call_count == 1
                        assert any("reintentando en 5s" in l for l in logs)

@pytest.mark.asyncio
async def test_viral_scout_skip_on_total_tweet_failure():
    """Test that an account is skipped with a warning after total tweet fetch failure."""
    scout = ViralScout()
    scout.accounts = {"fail_user": 1000, "success_user": 1000}
    
    with patch('config.cookie_utils.get_cookies', return_value={'ct0': 'dummy'}):
        with patch('config.cookie_utils.netscape_to_json'):
            with patch('json.load', return_value={'ct0': 'dummy'}):
                with patch('core.viral_scout.Client') as mock_client_class:
                    mock_instance = mock_client_class.return_value
                    
                    mock_user1 = MagicMock()
                    mock_user1.id = 1
                    mock_user2 = MagicMock()
                    mock_user2.id = 2
                    
                    mock_instance.get_user_by_screen_name = AsyncMock(side_effect=[mock_user1, mock_user2])
                    
                    async def mock_tweets_side_effect(*args, **kwargs):
                        # Use a simpler way to track which user it is if possible, 
                        # but here id=1 is the one that fails.
                        # Wait, the way it's called is get_user_tweets(user_id, ...)
                        user_id = args[0]
                        if user_id == 1:
                            raise Exception("KEY_BYTE indices info")
                        return []
                    
                    mock_instance.get_user_tweets = mock_tweets_side_effect
                    
                    logs = []
                    with patch.object(ViralScout, '_scan_nitter_rss', new_callable=AsyncMock) as mock_nitter:
                        mock_nitter.return_value = []
                        with patch('asyncio.sleep', return_value=None):
                            with patch.object(scout, '_scan_news_rss', AsyncMock(return_value=[])):
                                await scout._scan_async(progress_callback=lambda m: logs.append(m))
                            
                            # Verify User 1 was skipped with WARN
                            assert any("[WARN] Fallo scrapeando @fail_user (Tweets)" in l for l in logs)
                            # Verify success for user 2
                            assert any("Scanning @success_user" in l for l in logs)
