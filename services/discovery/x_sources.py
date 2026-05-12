import asyncio
import math
import os
import re
from datetime import datetime
from html import unescape
from typing import Any, Callable, Iterable, List, Optional

from .models import DiscoveryCandidate, XAccount


SCHEMA_ERROR_TOKENS = ("urls", "key_byte", "indices", "couldn't get key_byte")


def get_stat(obj: Any, keys: Iterable[str], default: int = 0) -> int:
    for key in keys:
        if isinstance(obj, dict):
            if key in obj:
                return obj[key] or 0
        else:
            val = getattr(obj, key, None)
            if val is not None:
                return val or 0
    return default


def is_schema_failure(exc: Exception) -> bool:
    msg = str(exc).lower()
    return isinstance(exc, KeyError) or any(token in msg for token in SCHEMA_ERROR_TOKENS)


def is_recoverable_twikit_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        is_schema_failure(exc)
        or "404" in msg
        or "403" in msg
        or "lookup" in msg
    )


def calculate_viral_score(reposts: int, likes: int, followers: Optional[int]) -> float:
    safe_followers = max(int(followers or 1000), 100)
    return ((reposts * 4) + likes) / (math.sqrt(safe_followers) * 2)


def candidate_to_dict(candidate: DiscoveryCandidate) -> dict:
    return candidate.to_dict()


class TwikitXSource:
    """Twikit-backed X source helpers.

    The full historical Twikit scan still lives in ViralScout for now; this
    class centralizes the replacement-safe parts first: error classification,
    score calculation, and tweet normalization.
    """

    source_name = "twikit"

    def __init__(
        self,
        client: Any = None,
        processed_checker: Optional[Callable[[str], bool]] = None,
    ):
        self.client = client
        self.processed_checker = processed_checker or (lambda _id: False)

    def normalize_tweet(
        self,
        tweet: Any,
        account: XAccount,
        followers: Optional[int] = None,
        min_ratio: float = 2.0,
        must_have_media: bool = True,
    ) -> Optional[DiscoveryCandidate]:
        tweet_id = str(getattr(tweet, "id", "") or "")
        if not tweet_id or self.processed_checker(tweet_id):
            return None

        has_video = False
        media_url = None
        thumbnail_url = None
        media_items = getattr(tweet, "media", None) or []
        has_media = len(media_items) > 0
        if must_have_media and not has_media:
            return None

        if has_media:
            first_media = media_items[0]
            media_type = getattr(first_media, "type", "")
            media_url = self._find_media_url(first_media)
            thumbnail_url = media_url
            if media_type == "video":
                has_video = True
                media_url = self._find_best_video_url(first_media) or media_url

        reposts = get_stat(tweet, ["retweet_count", "repost_count", "retweetCount"])
        likes = get_stat(tweet, ["favorite_count", "like_count", "favoriteCount"])
        follower_count = followers if followers is not None else account.followers_hint
        score = calculate_viral_score(reposts, likes, follower_count)
        if score < min_ratio:
            return None

        type_str = "VIDEO" if has_video else "IMAGEN"
        description = getattr(tweet, "full_text", getattr(tweet, "text", "")) or ""
        return DiscoveryCandidate(
            url=f"https://x.com/i/status/{tweet_id}",
            score=score,
            reposts=reposts,
            likes=likes,
            user=account.screen_name,
            source=self.source_name,
            id=tweet_id,
            type=type_str,
            is_video=has_video,
            media_url=media_url,
            thumbnail=thumbnail_url,
            description=description,
        )

    async def scan_accounts(
        self,
        accounts: List[XAccount],
        min_ratio: float = 2.0,
        max_items: int = 20,
        progress_callback: Callable[[str], None] = print,
        must_have_media: bool = True,
    ) -> List[DiscoveryCandidate]:
        if self.client is None:
            progress_callback("TwikitXSource requires a configured Twikit client.")
            return []

        hits: List[DiscoveryCandidate] = []
        for account in accounts:
            user = await self.client.get_user_by_screen_name(account.screen_name)
            followers = getattr(user, "followers_count", account.followers_hint)
            tweets = await self.client.get_user_tweets(getattr(user, "id"), "Tweets", count=40)
            for tweet in tweets or []:
                candidate = self.normalize_tweet(tweet, account, followers, min_ratio, must_have_media)
                if candidate:
                    hits.append(candidate)
                    if len(hits) >= max_items:
                        return sorted(hits, key=lambda item: item.score, reverse=True)
        return sorted(hits, key=lambda item: item.score, reverse=True)[:max_items]

    @staticmethod
    def _find_media_url(obj: Any) -> Optional[str]:
        for attr in ("media_url_https", "media_url", "display_url"):
            val = getattr(obj, attr, None)
            if val and isinstance(val, str) and val.startswith("http"):
                return val
        return None

    @staticmethod
    def _find_best_video_url(media: Any) -> Optional[str]:
        video_info = getattr(media, "video_info", {}) or {}
        variants = video_info.get("variants", []) if isinstance(video_info, dict) else []
        mp4s = [v for v in variants if v.get("content_type") == "video/mp4"]
        if not mp4s:
            return None
        return max(mp4s, key=lambda item: item.get("bitrate", 0)).get("url")


class BrowserXSource:
    """Experimental browser-backed X source.

    This adapter is disabled by default. Tests use parse_status_urls_from_html
    so no real browser or network access is needed.
    """

    source_name = "browser"

    def __init__(self, html_fetcher: Optional[Callable[[str], Any]] = None, timeout_ms: int = 8000):
        self.html_fetcher = html_fetcher
        self.timeout_ms = timeout_ms

    @staticmethod
    def parse_status_urls_from_html(html: str, screen_name: str) -> List[DiscoveryCandidate]:
        status_ids = []
        seen = set()
        for match in re.finditer(r'(?:https?://x\.com)?/([^/"\s]+)/status/(\d+)', html or ""):
            user, status_id = match.groups()
            if user.lower() != screen_name.lower() or status_id in seen:
                continue
            seen.add(status_id)
            status_ids.append(status_id)

        text = re.sub(r"<[^>]+>", " ", html or "")
        text = re.sub(r"\s+", " ", unescape(text)).strip()
        return [
            DiscoveryCandidate(
                url=f"https://x.com/{screen_name}/status/{status_id}",
                score=0.1,
                reposts=0,
                likes=0,
                user=screen_name,
                source=BrowserXSource.source_name,
                id=status_id,
                type="TWEET",
                is_video=False,
                media_url=None,
                thumbnail=None,
                description=text[:500],
            )
            for status_id in status_ids
        ]

    async def scan_accounts(
        self,
        accounts: List[XAccount],
        max_items: int = 20,
        progress_callback: Callable[[str], None] = print,
    ) -> List[DiscoveryCandidate]:
        hits: List[DiscoveryCandidate] = []
        for account in accounts:
            html = await self._fetch_html(account.screen_name, progress_callback)
            if not html:
                continue
            hits.extend(self.parse_status_urls_from_html(html, account.screen_name))
            if len(hits) >= max_items:
                break
        return hits[:max_items]

    async def _fetch_html(self, screen_name: str, progress_callback: Callable[[str], None]) -> str:
        if self.html_fetcher:
            result = self.html_fetcher(screen_name)
            if asyncio.iscoroutine(result):
                result = await result
            return result or ""

        try:
            from playwright.async_api import async_playwright
        except Exception as exc:
            progress_callback(f"BrowserXSource no disponible: Playwright no instalado ({exc}).")
            return ""

        profile_url = f"https://x.com/{screen_name}"
        storage_state = os.environ.get("ECONOMIKA_X_BROWSER_STORAGE_STATE")
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                context_kwargs = {}
                if storage_state:
                    context_kwargs["storage_state"] = storage_state
                context = await browser.new_context(**context_kwargs)
                page = await context.new_page()
                await page.goto(profile_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                html = await page.content()
                await browser.close()
                return html
        except Exception as exc:
            progress_callback(f"BrowserXSource fallo para @{screen_name}: {exc}")
            return ""
