import asyncio
import http.cookiejar
import json
import math
import os
import re
from datetime import datetime
from html import unescape
from pathlib import Path
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
    return is_schema_failure(exc) or "404" in msg or "403" in msg or "lookup" in msg


def calculate_viral_score(reposts: int, likes: int, followers: Optional[int]) -> float:
    safe_followers = max(int(followers or 1000), 100)
    return ((reposts * 4) + likes) / (math.sqrt(safe_followers) * 2)


def candidate_to_dict(candidate: DiscoveryCandidate) -> dict:
    return candidate.to_dict()


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html or "")
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_screen_name(value: str) -> str:
    return (value or "").strip().lstrip("@")


def parse_compact_metric(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)

    raw = str(value).strip().lower().replace("\xa0", " ")
    if not raw:
        return 0

    raw = raw.replace(" ", "")
    raw = raw.replace(",", ".") if raw.count(",") == 1 and raw.count(".") == 0 else raw.replace(",", "")

    suffix_multipliers = {
        "k": 1_000,
        "mil": 1_000,
        "m": 1_000_000,
        "mill": 1_000_000,
        "millones": 1_000_000,
    }

    match = re.match(r"^(\d+(?:\.\d+)?)([a-z]+)?$", raw)
    if not match:
        digits = re.sub(r"[^\d]", "", raw)
        return int(digits) if digits else 0

    number = float(match.group(1))
    suffix = match.group(2) or ""
    multiplier = suffix_multipliers.get(suffix, 1)
    return int(number * multiplier)


def extract_compact_metric_from_text(text: str, labels: Iterable[str]) -> int:
    clean = re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()
    if not clean:
        return 0

    label_pattern = "|".join(re.escape(label) for label in labels)
    patterns = [
        rf"(?P<num>\d[\d.,]*(?:\s?(?:k|m|mil|mill|millones))?)\s*(?:{label_pattern})\b",
        rf"(?:{label_pattern})\s*(?P<num>\d[\d.,]*(?:\s?(?:k|m|mil|mill|millones))?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean, re.I)
        if match:
            return parse_compact_metric(match.group("num"))
    return 0


def extract_metrics_from_text(text: str) -> dict:
    clean = re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()
    return {
        "reposts": extract_compact_metric_from_text(clean, ("repost", "reposts", "retweet", "retweets", "rt", "rts", "reenvios", "compartidos")),
        "likes": extract_compact_metric_from_text(clean, ("like", "likes", "me gusta", "megustas", "favoritos", "faves")),
        "replies": extract_compact_metric_from_text(clean, ("reply", "replies", "respuesta", "respuestas")),
        "views": extract_compact_metric_from_text(clean, ("view", "views", "visualizacion", "visualizaciones", "impresion", "impresiones")),
    }


def _extract_status_ids_from_html(html: str) -> List[dict]:
    results = []
    seen_ids = set()
    article_blocks = re.findall(r"(?is)<article\b.*?</article>", html or "")
    blocks = article_blocks or [html or ""]

    for block in blocks:
        timestamp_match = re.search(r'time[^>]+datetime=["\']([^"\']+)["\']', block, re.I)
        text = _strip_html(block)
        metrics = extract_metrics_from_text(text)
        for status_match in re.finditer(r'(?:https?://(?:www\.)?x\.com)?/([^/"\s]+)/status/(\d+)', block, re.I):
            screen_name, status_id = status_match.groups()
            if status_id in seen_ids:
                continue
            seen_ids.add(status_id)
            results.append({
                "screen_name": _clean_screen_name(screen_name),
                "status_id": status_id,
                "status_url": f"https://x.com/{_clean_screen_name(screen_name)}/status/{status_id}",
                "text": text,
                "timestamp": timestamp_match.group(1) if timestamp_match else None,
                "metrics": metrics,
            })

    return results


def _parse_browser_candidates_from_html(
    html: str,
    screen_name: str,
    followers_hint: Optional[int] = None,
    max_tweets: int = 5,
    max_total_candidates: int = 20,
) -> List[DiscoveryCandidate]:
    rows = _extract_status_ids_from_html(html)
    if not rows:
        return []

    safe_followers = followers_hint or 1000
    candidates: List[DiscoveryCandidate] = []
    screen_name = _clean_screen_name(screen_name)

    for row in rows[:max_tweets]:
        metrics = row["metrics"]
        likes = metrics.get("likes", 0)
        reposts = metrics.get("reposts", 0)
        score_source = "browser_no_metrics"
        score = 0.1
        if likes or reposts:
            score = calculate_viral_score(reposts, likes, safe_followers)
            score_source = "browser_metrics" if followers_hint else "browser_metrics_default_followers_1000"

        candidates.append(
            DiscoveryCandidate(
                url=row["status_url"],
                score=score,
                reposts=reposts,
                likes=likes,
                user=row["screen_name"] or screen_name,
                source="browser",
                id=row["status_id"],
                type="TWEET",
                is_video="video" in row["text"].lower() or ".mp4" in row["text"].lower(),
                media_url=None,
                thumbnail=None,
                description=row["text"][:500],
                score_source=score_source,
                timestamp=row["timestamp"],
            )
        )
        if len(candidates) >= max_total_candidates:
            break

    return candidates


class TwikitXSource:
    """Twikit-backed X source helpers."""

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
            score_source="twikit",
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

    The runtime fetches X profile HTML with Playwright or a custom fetcher.
    Parser helpers are static so CI can unit-test them without browser access.
    """

    source_name = "browser"

    def __init__(
        self,
        html_fetcher: Optional[Callable[[str], Any]] = None,
        timeout_ms: int = 8000,
        max_tweets_per_account: int = 5,
        max_total_candidates: int = 20,
        user_data_dir: Optional[str] = None,
    ):
        self.html_fetcher = html_fetcher
        self.timeout_ms = timeout_ms
        self.max_tweets_per_account = max_tweets_per_account
        self.max_total_candidates = max_total_candidates
        self.user_data_dir = user_data_dir

    @staticmethod
    def parse_status_urls_from_html(html: str, screen_name: str) -> List[DiscoveryCandidate]:
        screen_name = _clean_screen_name(screen_name)
        return [
            candidate
            for candidate in _parse_browser_candidates_from_html(
                html,
                screen_name,
                max_tweets=5,
                max_total_candidates=20,
            )
            if candidate.user.lower() == screen_name.lower()
        ]

    @staticmethod
    def parse_compact_metric(value: Any) -> int:
        return parse_compact_metric(value)

    @staticmethod
    def extract_metrics_from_text(text: str) -> dict:
        return extract_metrics_from_text(text)

    @classmethod
    def parse_candidates_from_html(
        cls,
        html: str,
        screen_name: str,
        followers_hint: Optional[int] = None,
        max_tweets_per_account: int = 5,
        max_total_candidates: int = 20,
    ) -> List[DiscoveryCandidate]:
        screen_name = _clean_screen_name(screen_name)
        return [
            candidate
            for candidate in _parse_browser_candidates_from_html(
                html,
                screen_name,
                followers_hint=followers_hint,
                max_tweets=max_tweets_per_account,
                max_total_candidates=max_total_candidates,
            )
            if candidate.user.lower() == screen_name.lower()
        ]

    async def scan_accounts(
        self,
        accounts: List[XAccount],
        max_items: int = 20,
        progress_callback: Callable[[str], None] = print,
    ) -> List[DiscoveryCandidate]:
        hits: List[DiscoveryCandidate] = []
        for account in accounts:
            if len(hits) >= max_items:
                break
            if account.followers_hint is None:
                progress_callback(f"BrowserXSource: using fallback followers_hint=1000 for @{account.screen_name}.")
            html = await self._fetch_profile_html(account.screen_name, progress_callback)
            if not html:
                continue
            candidates = self.parse_candidates_from_html(
                html,
                account.screen_name,
                followers_hint=account.followers_hint,
                max_tweets_per_account=self.max_tweets_per_account,
                max_total_candidates=max_items - len(hits),
            )
            hits.extend(candidates)
        return hits[:max_items]

    async def _fetch_profile_html(self, screen_name: str, progress_callback: Callable[[str], None]) -> str:
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
        root_dir = Path(__file__).resolve().parents[2]
        user_data_dir = self.user_data_dir or self._find_user_data_dir(root_dir)
        cookies_txt = root_dir / "config" / "x.com_cookies.txt"
        cookies_json = root_dir / "config" / "x.com_cookies.json"

        try:
            async with async_playwright() as playwright:
                context = None
                browser = None
                if user_data_dir:
                    browser = await playwright.chromium.launch_persistent_context(
                        user_data_dir=str(user_data_dir),
                        headless=True,
                        timeout=self.timeout_ms,
                    )
                    context = browser
                else:
                    browser = await playwright.chromium.launch(headless=True)
                    context = await browser.new_context()
                    await self._inject_cookies(context, cookies_txt, cookies_json)

                page = await context.new_page()
                await page.goto(profile_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                await self._light_scroll(page)
                html = await page.content()
                await context.close()
                if browser and browser is not context:
                    await browser.close()
                return html
        except Exception as exc:
            progress_callback(f"BrowserXSource fallo para @{screen_name}: {exc}")
            return ""

    async def _inject_cookies(self, context: Any, cookies_txt: Path, cookies_json: Path) -> None:
        cookies = []
        if cookies_json.exists():
            try:
                with cookies_json.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    cookies.extend(data)
                elif isinstance(data, dict):
                    for name, value in data.items():
                        cookies.append(
                            {
                                "name": name,
                                "value": value,
                                "domain": ".x.com",
                                "path": "/",
                            }
                        )
            except Exception:
                pass

        if not cookies and cookies_txt.exists():
            cookies.extend(self._parse_netscape_cookie_file(cookies_txt))

        if cookies:
            await context.add_cookies(cookies)

    @staticmethod
    def _parse_netscape_cookie_file(path: Path) -> List[dict]:
        jar = http.cookiejar.MozillaCookieJar(str(path))
        try:
            jar.load(ignore_discard=True, ignore_expires=True)
        except Exception:
            return []

        cookies = []
        for cookie in jar:
            cookies.append(
                {
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                    "expires": int(cookie.expires) if cookie.expires else None,
                    "httpOnly": False,
                    "secure": bool(cookie.secure),
                    "sameSite": "Lax",
                }
            )
        return cookies

    @staticmethod
    def _find_user_data_dir(root_dir: Path) -> Optional[Path]:
        candidates = [
            root_dir / "user_data_scraper",
            root_dir / "user_data_scraper" / "Default",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    async def _light_scroll(self, page: Any) -> None:
        try:
            await page.mouse.wheel(0, 1400)
            await page.wait_for_timeout(750)
            await page.mouse.wheel(0, 1400)
            await page.wait_for_timeout(750)
        except Exception:
            return
