from __future__ import annotations

import argparse
import json

from app.ingestion.models import SourceAccount
from app.ingestion.x_internal_api_provider import XInternalApiProvider


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe one X account through the experimental internal API provider."
    )
    parser.add_argument("--handle", required=True)
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()

    result = XInternalApiProvider().fetch_recent_posts(
        account=SourceAccount(handle=args.handle),
        lookback_hours=args.lookback_hours,
    )

    if args.print_json:
        print(
            json.dumps(
                {
                    "provider_name": result.provider_name,
                    "account": result.account.handle,
                    "post_count": len(result.posts),
                    "errors": result.errors,
                    "posts": [_post_summary(post) for post in result.posts],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    print(f"provider: {result.provider_name}")
    print(f"account: {result.account.handle}")
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


def _post_summary(post: object) -> dict[str, object]:
    return {
        "post_id": getattr(post, "post_id"),
        "url": getattr(post, "url"),
        "text_prefix": getattr(post, "text")[:100],
        "media_count": len(getattr(post, "media")),
        "metrics": getattr(post, "metrics").__dict__,
    }


if __name__ == "__main__":
    raise SystemExit(main())
