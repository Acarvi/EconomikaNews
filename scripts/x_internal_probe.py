from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.config.runtime_config import load_runtime_config, apply_runtime_config_to_env
from app.ingestion.models import SourceAccount
from app.ingestion.x_internal_api_provider import XInternalApiProvider


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe one X account through the experimental internal API provider."
    )
    parser.add_argument("--handle", required=True)
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument(
        "--resolve-user-id",
        action="store_true",
        help="Allow handle -> userId resolution via X_INTERNAL_USER_LOOKUP_TEMPLATE_URL.",
    )
    parser.add_argument("--show-media", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    parser.add_argument(
        "--config",
        help="Path to the runtime configuration YAML file.",
    )
    args = parser.parse_args()

    if args.config:
        try:
            config = load_runtime_config(Path(args.config))
            apply_runtime_config_to_env(config)
        except Exception as exc:
            print(f"Error loading runtime config: {exc}", file=sys.stderr)
            return 1

    provider = XInternalApiProvider()
    result = provider.fetch_recent_posts(
        account=SourceAccount(handle=args.handle),
        lookback_hours=args.lookback_hours,
    )
    resolved_user_id = provider.last_resolved_user_id if args.resolve_user_id else None

    if args.print_json:
        print(
            json.dumps(
                {
                    "provider_name": result.provider_name,
                    "account": result.account.handle,
                    "resolved_user_id": resolved_user_id,
                    "post_count": len(result.posts),
                    "errors": result.errors,
                    "posts": [
                        _post_summary(post, show_media=args.show_media)
                        for post in result.posts
                    ],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    print(f"provider: {result.provider_name}")
    print(f"account: {result.account.handle}")
    if args.resolve_user_id:
        print(f"resolved_user_id: {resolved_user_id}")
    print(f"posts: {len(result.posts)}")
    if result.errors:
        print("errors:")
        for error in result.errors:
            print(f"- {error}")
    if result.posts:
        print("post summaries:")
        for post in result.posts:
            metrics = post.metrics
            print(
                "- "
                f"id={post.post_id} "
                f"url={post.url} "
                f"text={post.text[:100]!r} "
                f"media={len(post.media)} "
                f"likes={metrics.likes} "
                f"reposts={metrics.reposts} "
                f"replies={metrics.replies} "
                f"views={metrics.views}"
            )
    return 0


def _post_summary(post: object, *, show_media: bool = False) -> dict[str, object]:
    summary = {
        "post_id": getattr(post, "post_id"),
        "url": getattr(post, "url"),
        "text_prefix": getattr(post, "text")[:100],
        "media_count": len(getattr(post, "media")),
        "metrics": getattr(post, "metrics").__dict__,
    }
    if show_media:
        summary["media"] = [
            {
                "media_type": getattr(media, "media_type"),
                "url": getattr(media, "url"),
                "preview_url": getattr(media, "preview_url"),
                "local_path": getattr(media, "local_path"),
            }
            for media in getattr(post, "media")
        ]
    return summary


if __name__ == "__main__":
    raise SystemExit(main())
