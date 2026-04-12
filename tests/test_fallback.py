import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from core.viral_scout import ViralScout
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_nitter_fallback_on_twikit_failure():
    """Verify that ViralScout falls back to Nitter RSS when Twikit fails."""
    # Mock the Client class to avoid internal Twikit logic
    with patch('core.viral_scout.Client') as MockClient:
        mock_client_instance = MockClient.return_value
        mock_client_instance.get_user_by_screen_name = AsyncMock(side_effect=Exception("Couldn't get KEY_BYTE indices"))
        mock_client_instance.search_user = AsyncMock(return_value=[])
        
        scout = ViralScout()
        scout.client = mock_client_instance
        
        limit_date = datetime.now() - timedelta(hours=24)
        
        # Mock asyncio.sleep and random.uniform to speed up test
        with patch('core.viral_scout.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            with patch('core.viral_scout.random.uniform', return_value=0.1):
                # Mock _scan_nitter_rss to return dummy data
                mock_hits = [{
                    'url': 'https://x.com/i/status/12345',
                    'id': '12345',
                    'score': 10.5,
                    'reposts': 50,
                    'likes': 100,
                    'user': 'testuser',
                    'type': 'VÍDEO 🎥',
                    'is_video': True,
                    'media_url': 'https://nitter.net/pic.mp4',
                    'thumbnail': None,
                    'description': 'Test tweet'
                }]
                
                with patch.object(ViralScout, '_scan_nitter_rss', new_callable=AsyncMock) as mock_nitter:
                    mock_nitter.return_value = mock_hits
                    
                    # Run scan for one account
                    scout.accounts = {"testuser": 1000}
                    results = await scout._scan_async(hours_back=24)
                    
                    # Verify fallback was called
                    mock_nitter.assert_called_once()
                    assert len(results) == 1
                    assert results[0]['id'] == '12345'

if __name__ == "__main__":
    pytest.main([__file__])
