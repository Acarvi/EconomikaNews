from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

from app.ingestion.models import SourceAccount
from app.ingestion.x_internal_api_provider import XInternalApiProvider


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe multiple X accounts sequentially and produce a candidates list."
    )
    parser.add_argument(
        "--accounts-file",
        default="config/accounts.example.yaml",
        help="Path to the YAML accounts configuration file.",
    )
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=24,
        help="How many hours to look back for recent tweets.",
    )
    parser.add_argument(
        "--limit-per-account",
        type=int,
        default=20,
        help="Maximum number of posts to fetch per account before deduplication.",
    )
    parser.add_argument(
        "--resolve-user-id",
        action="store_true",
        help="Allow handle -> userId resolution via X_INTERNAL_USER_LOOKUP_TEMPLATE_URL.",
    )
    parser.add_argument(
        "--include-media",
        action="store_true",
        help="Include media details in the output candidates.",
    )
    parser.add_argument(
        "--output-json",
        nargs="?",
        const="runtime/outputs/x_candidates.json",
        default=None,
        help=(
            "Optional path to write the JSON candidate list to. "
            "If flag is passed without value, defaults to 'runtime/outputs/x_candidates.json'."
        ),
    )

    args = parser.parse_args()

    # 1. Load accounts config
    config_path = Path(args.accounts_file)
    if not config_path.exists():
        print(f"Error: Accounts configuration file not found: {config_path}", file=sys.stderr)
        return 1

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
    except Exception as exc:
        print(f"Error reading accounts configuration: {exc}", file=sys.stderr)
        return 1

    if not config_data or not isinstance(config_data, dict) or "accounts" not in config_data:
        print("Error: Invalid configuration format. Expected top-level 'accounts' key.", file=sys.stderr)
        return 1

    accounts_list = config_data["accounts"]
    if not isinstance(accounts_list, list):
        print("Error: 'accounts' must be a list of accounts.", file=sys.stderr)
        return 1

    # 2. Ingest sequentially
    provider = XInternalApiProvider()
    errors: list[str] = []
    deduplicated_candidates: dict[str, dict[str, Any]] = {}
    total_posts_fetched = 0

    for account_data in accounts_list:
        if not isinstance(account_data, dict) or "handle" not in account_data:
            errors.append("Invalid account entry skipped: missing 'handle'.")
            continue

        handle = account_data["handle"]
        category = account_data.get("category")
        weight = float(account_data.get("weight", 1.0))
        followers_hint = account_data.get("followers_hint")

        account_obj = SourceAccount(
            handle=handle,
            category=category,
            weight=weight,
            followers_hint=followers_hint,
        )

        try:
            result = provider.fetch_recent_posts(
                account=account_obj,
                lookback_hours=args.lookback_hours,
            )

            # Record any provider errors
            if result.errors:
                for err in result.errors:
                    errors.append(f"{handle}: {err}")

            # Keep only the requested limit per account
            fetched_posts = result.posts[: args.limit_per_account]
            total_posts_fetched += len(fetched_posts)

            # 3. Deduplicate & compute score
            for post in fetched_posts:
                metrics = post.metrics
                likes = metrics.likes if metrics.likes is not None else 0
                reposts = metrics.reposts if metrics.reposts is not None else 0
                replies = metrics.replies if metrics.replies is not None else 0
                views = metrics.views if metrics.views is not None else 0

                engagement_score = likes * 1 + reposts * 3 + replies * 2
                views_score = views
                score = (views_score + engagement_score) * weight

                candidate: dict[str, Any] = {
                    "score": score,
                    "account_handle": handle,
                    "post_id": post.post_id,
                    "url": post.url,
                    "text_prefix": post.text[:100],
                    "metrics": {
                        "likes": metrics.likes,
                        "reposts": metrics.reposts,
                        "replies": metrics.replies,
                        "views": metrics.views,
                    },
                    "media_count": len(post.media),
                }

                if args.include_media:
                    candidate["media"] = [
                        {
                            "media_type": med.media_type,
                            "url": med.url,
                            "preview_url": med.preview_url,
                            "local_path": med.local_path,
                        }
                        for med in post.media
                    ]

                # Resolve duplicate post IDs by keeping the higher-scoring candidate
                existing = deduplicated_candidates.get(post.post_id)
                if existing is None or score > existing["score"]:
                    deduplicated_candidates[post.post_id] = candidate

        except Exception as exc:
            errors.append(f"Unexpected error fetching {handle}: {exc}")

    # 4. Sort descending by score
    sorted_candidates = sorted(
        deduplicated_candidates.values(),
        key=lambda c: c["score"],
        reverse=True,
    )

    # 5. Output JSON summary
    output_data = {
        "provider_name": provider.provider_name,
        "account_count": len(accounts_list),
        "fetched_accounts": [acc["handle"] for acc in accounts_list if isinstance(acc, dict) and "handle" in acc],
        "total_posts": total_posts_fetched,
        "unique_posts": len(sorted_candidates),
        "candidates": sorted_candidates,
        "errors": errors,
    }

    output_str = json.dumps(output_data, indent=2, sort_keys=True)
    print(output_str)

    # 6. Save if output path requested
    if args.output_json:
        output_path = Path(args.output_json)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output_str, encoding="utf-8")
        except Exception as exc:
            print(f"Error writing output JSON to {output_path}: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
