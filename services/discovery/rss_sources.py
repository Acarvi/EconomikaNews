"""RSS discovery placeholder adapter.

RSS/news remains an explicit secondary mode. The production RSS scanner still
uses ViralScout._scan_news_rss while X adapters are extracted first.
"""

from typing import Callable, List

from .models import DiscoveryCandidate


class NewsRSSSource:
    def __init__(self, scanner: Callable[..., list]):
        self.scanner = scanner

    async def scan(self, **kwargs) -> List[DiscoveryCandidate]:
        rows = await self.scanner(**kwargs)
        return [
            DiscoveryCandidate(
                url=row["url"],
                score=row["score"],
                reposts=row.get("reposts", 0),
                likes=row.get("likes", 0),
                user=row.get("user") or row.get("source", "rss"),
                source=row.get("source", "rss"),
                id=row["id"],
                type=row.get("type", "NEWS"),
                is_video=row.get("is_video", False),
                media_url=row.get("media_url"),
                thumbnail=row.get("thumbnail"),
                description=row.get("description", ""),
            )
            for row in rows
        ]
