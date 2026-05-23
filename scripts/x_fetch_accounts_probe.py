from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

from app.config.runtime_config import load_runtime_config, apply_runtime_config_to_env
from app.ingestion.models import SourceAccount
from app.ingestion.x_internal_api_provider import XInternalApiProvider
from app.storage.sqlite_seen_posts import get_seen_post_ids, upsert_seen_posts

DEFAULT_ACCOUNTS_FILE = "config/accounts.example.yaml"
DEFAULT_DB_PATH = "runtime/economika_news.db"
DEFAULT_OUTPUT_JSON_PATH = "runtime/outputs/x_candidates.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe multiple X accounts sequentially and produce a candidates list."
    )
    parser.add_argument(
        "--config",
        help="Path to the runtime configuration YAML file.",
    )
    parser.add_argument(
        "--accounts-file",
        default=None,
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
        const=DEFAULT_OUTPUT_JSON_PATH,
        default=None,
        help=(
            "Optional path to write the JSON candidate list to. "
            "If flag is passed without value, defaults to config path or 'runtime/outputs/x_candidates.json'."
        ),
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Path to the SQLite database for seen-posts caching.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable SQLite seen-posts caching.",
    )
    parser.add_argument(
        "--only-new",
        action="store_true",
        help="Output only new candidates (requires cache enabled).",
    )

    args = parser.parse_args()

    if args.no_cache and args.only_new:
        print("Error: --only-new requires cache enabled", file=sys.stderr)
        return 1

    # Load runtime config if provided
    config = None
    if args.config:
        try:
            config = load_runtime_config(Path(args.config))
            apply_runtime_config_to_env(config)
        except Exception as exc:
            print(f"Error loading runtime config: {exc}", file=sys.stderr)
            return 1

    # Resolve accounts_file
    accounts_file = None
    if args.accounts_file is not None:
        accounts_file = args.accounts_file
    elif config and config.paths.accounts_file:
        accounts_file = config.paths.accounts_file
    else:
        accounts_file = DEFAULT_ACCOUNTS_FILE

    # Resolve db_path
    db_path = None
    if args.db_path is not None:
        db_path = args.db_path
    elif os.environ.get("ECONOMIKA_DB_PATH"):
        db_path = os.environ.get("ECONOMIKA_DB_PATH")
    elif config and config.paths.db_path:
        db_path = config.paths.db_path
    else:
        db_path = DEFAULT_DB_PATH

    # Resolve output_json
    output_json = None
    if args.output_json is not None:
        if args.output_json == DEFAULT_OUTPUT_JSON_PATH:
            if config and config.paths.output_json:
                output_json = config.paths.output_json
            else:
                output_json = DEFAULT_OUTPUT_JSON_PATH
        else:
            output_json = args.output_json

    # 1. Load accounts config
    config_path = Path(accounts_file)
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
                    "source": post.source,
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

    # 5. Seen-post cache integration
    cache_enabled = not args.no_cache
    if cache_enabled:
        db_path_str = db_path
        db_path_obj = Path(db_path_str)

        # Check seen status
        post_ids = [c["post_id"] for c in sorted_candidates]
        seen_ids = get_seen_post_ids(db_path_obj, post_ids)

        # Mark is_new
        for c in sorted_candidates:
            c["is_new"] = c["post_id"] not in seen_ids

        # Compute counts BEFORE applying --only-new filtering
        new_candidates = sum(1 for c in sorted_candidates if c["is_new"])
        already_seen_candidates = sum(1 for c in sorted_candidates if not c["is_new"])

        # Upsert ALL candidates
        upsert_seen_posts(db_path_obj, sorted_candidates)

        # Filter if --only-new is active
        if args.only_new:
            sorted_candidates = [c for c in sorted_candidates if c["is_new"]]
    else:
        db_path_str = None
        new_candidates = None
        already_seen_candidates = None

    # 6. Output JSON summary
    output_data = {
        "provider_name": provider.provider_name,
        "account_count": len(accounts_list),
        "fetched_accounts": [acc["handle"] for acc in accounts_list if isinstance(acc, dict) and "handle" in acc],
        "total_posts": total_posts_fetched,
        "unique_posts": len(sorted_candidates),
        "candidates": sorted_candidates,
        "errors": errors,
        "cache_enabled": cache_enabled,
        "db_path": db_path_str,
        "new_candidates": new_candidates,
        "already_seen_candidates": already_seen_candidates,
    }

    output_str = json.dumps(output_data, indent=2, sort_keys=True)
    print(output_str)

    # 6. Save if output path requested
    if output_json:
        output_path = Path(output_json)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output_str, encoding="utf-8")
        except Exception as exc:
            print(f"Error writing output JSON to {output_path}: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
