from __future__ import annotations

import os
from pathlib import Path

import yaml


def main() -> int:
    print("=== X Internal Runtime Config Setup Helper ===")
    print("This script will guide you to create your local runtime config file at:")
    print("runtime/config/x_internal.local.yaml\n")

    # Ensure runtime/config/ directory exists
    config_dir = Path("runtime/config")
    config_dir.mkdir(parents=True, exist_ok=True)

    # Prompt user for inputs
    headers_file = input("Enter headers_file path [runtime/secrets/x_headers.json]: ").strip()
    if not headers_file:
        headers_file = "runtime/secrets/x_headers.json"

    timeline_url = input("Enter UserTweets template URL (timeline_template_url): ").strip()
    if not timeline_url:
        timeline_url = "PASTE_USER_TWEETS_TEMPLATE_URL_HERE"

    user_lookup_url = input("Enter UserByScreenName template URL (user_lookup_template_url): ").strip()
    if not user_lookup_url:
        user_lookup_url = "PASTE_USER_BY_SCREEN_NAME_TEMPLATE_URL_HERE"

    accounts_file = input("Enter accounts_file path [runtime/config/accounts.local.yaml]: ").strip()
    if not accounts_file:
        accounts_file = "runtime/config/accounts.local.yaml"

    db_path = input("Enter db_path [runtime/economika_news.db]: ").strip()
    if not db_path:
        db_path = "runtime/economika_news.db"

    output_json = input("Enter output_json path [runtime/outputs/x_candidates.json]: ").strip()
    if not output_json:
        output_json = "runtime/outputs/x_candidates.json"

    local_config = {
        "x_internal": {
            "headers_file": headers_file,
            "timeline_template_url": timeline_url,
            "user_lookup_template_url": user_lookup_url,
            "user_id": None,
        },
        "paths": {
            "accounts_file": accounts_file,
            "db_path": db_path,
            "output_json": output_json,
        },
    }

    dest_file = config_dir / "x_internal.local.yaml"
    dest_file.write_text(
        yaml.safe_dump(local_config, sort_keys=False),
        encoding="utf-8",
    )

    print(f"\n[SUCCESS] Local runtime config file created at: {dest_file}")
    print("Verify its contents and ensure it's not committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
