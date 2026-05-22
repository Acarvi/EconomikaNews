from __future__ import annotations

import argparse
import json
from getpass import getpass
from pathlib import Path

DEFAULT_OUTPUT = Path("runtime/secrets/x_headers.json")
OPTIONAL_HEADER_PROMPTS = (
    ("referer", "request referer URL"),
    ("user-agent", "browser user-agent"),
    ("x-twitter-active-user", "x-twitter-active-user"),
    ("x-twitter-auth-type", "x-twitter-auth-type"),
    ("x-twitter-client-language", "x-twitter-client-language"),
    ("x-client-transaction-id", "x-client-transaction-id"),
    ("accept", "accept"),
    ("accept-language", "accept-language"),
    ("content-type", "content-type"),
    ("sec-ch-ua", "sec-ch-ua"),
    ("sec-ch-ua-mobile", "sec-ch-ua-mobile"),
    ("sec-ch-ua-platform", "sec-ch-ua-platform"),
    ("sec-fetch-dest", "sec-fetch-dest"),
    ("sec-fetch-mode", "sec-fetch-mode"),
    ("sec-fetch-site", "sec-fetch-site"),
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a local ignored X internal API headers JSON file."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    headers: dict[str, str] = {}
    bearer = getpass('authorization bearer token, without "Bearer" prefix: ').strip()
    if bearer:
        headers["authorization"] = f"Bearer {bearer}"

    cookie = getpass("full cookie header: ").strip()
    if cookie:
        headers["cookie"] = cookie

    csrf = getpass("x-csrf-token / ct0: ").strip()
    if csrf:
        headers["x-csrf-token"] = csrf

    for key, label in OPTIONAL_HEADER_PROMPTS:
        value = input(f"{label} (blank to skip): ").strip()
        if value:
            headers[key] = value

    output.write_text(
        json.dumps(headers, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Created {output.as_posix()}")
    print("Set:")
    print(f'  $env:X_INTERNAL_HEADERS_FILE="{output.as_posix()}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
