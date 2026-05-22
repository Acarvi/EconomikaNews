from __future__ import annotations

import argparse
import json
import mimetypes
import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.ingestion.models import SourceAccount, SourceMedia, SourcePost
from app.ingestion.x_internal_api_provider import XInternalApiProvider

DEFAULT_OUTPUT_DIR = Path("runtime/downloads/x")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch one X account and download media from returned posts."
    )
    parser.add_argument("--handle", required=True)
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--limit-posts", type=int, default=5)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--resolve-user-id", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    provider = XInternalApiProvider()
    result = provider.fetch_recent_posts(
        account=SourceAccount(handle=args.handle),
        lookback_hours=args.lookback_hours,
    )
    user_agent = _media_user_agent()
    selected_posts = result.posts[: max(args.limit_posts, 0)]
    files: list[str] = []
    files_downloaded = 0
    errors = list(result.errors)

    for post in selected_posts:
        for index, media in enumerate(post.media, start=1):
            if not media.url:
                continue
            target = build_media_target_path(Path(args.output_dir), post.post_id, media, index)
            files.append(target.as_posix())
            if args.dry_run:
                continue
            try:
                download_media(media.url, target, user_agent=user_agent)
                files_downloaded += 1
            except OSError as exc:
                errors.append(f"download_error: {media.url}: {exc}")
            except URLError as exc:
                errors.append(f"download_error: {media.url}: {exc.reason}")

    print(
        json.dumps(
            {
                "provider_name": result.provider_name,
                "account": result.account.handle,
                "resolved_user_id": (
                    provider.last_resolved_user_id if args.resolve_user_id else None
                ),
                "post_count": len(result.posts),
                "posts_seen": len(selected_posts),
                "posts_with_media": sum(1 for post in selected_posts if post.media),
                "files_downloaded": files_downloaded,
                "files": files,
                "errors": errors,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def build_media_target_path(
    output_dir: Path,
    post_id: str,
    media: SourceMedia,
    index: int,
) -> Path:
    extension = _media_extension(media)
    prefix = media.media_type if media.media_type in {"image", "video"} else "media"
    return output_dir / post_id / f"{prefix}_{index}{extension}"


def download_media(url: str, target: Path, *, user_agent: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"user-agent": user_agent}, method="GET")
    with urlopen(request, timeout=60.0) as response:
        target.write_bytes(response.read())


def _media_extension(media: SourceMedia) -> str:
    if media.media_type == "image":
        return _extension_from_url(media.url) or ".jpg"
    if media.media_type == "video":
        return _extension_from_url(media.url) or ".mp4"
    return _extension_from_url(media.url) or ".bin"


def _extension_from_url(url: str | None) -> str | None:
    if not url:
        return None
    suffix = Path(url.split("?", 1)[0]).suffix
    if suffix:
        return suffix
    guess = mimetypes.guess_extension(url)
    return guess


def _media_user_agent() -> str:
    headers_file = os.environ.get("X_INTERNAL_HEADERS_FILE")
    if not headers_file:
        return os.environ.get("X_USER_AGENT") or DEFAULT_USER_AGENT
    try:
        payload = json.loads(Path(headers_file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return os.environ.get("X_USER_AGENT") or DEFAULT_USER_AGENT
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(key, str) and key.lower() == "user-agent" and isinstance(value, str):
                return value
    return os.environ.get("X_USER_AGENT") or DEFAULT_USER_AGENT


if __name__ == "__main__":
    raise SystemExit(main())
