# X/Twitter Ingestion Adapter

This document describes the design and usage of the Real X Ingestion Adapter (`scripts/fetch_x_posts.py`), implemented in EN-049.

## Purpose

The adapter is responsible for fetching recent posts from real X/Twitter accounts and normalizing them into a standard JSON shape that can be consumed by the Economika X-to-Reel generator. It supports multiple providers to handle changing platform restrictions and available tools.

## Fastest Real-Account Flow

To fetch real accounts and generate reels immediately:

```powershell
py scripts\fetch_x_posts.py --accounts juanrallo --max-posts-per-account 20 --output-json runtime\x_posts\latest_posts.json
py scripts\make_reels_from_x.py --input-json runtime\x_posts\latest_posts.json --top 3 --overwrite --open
```

## Provider Setup

The script supports multiple scraping/API providers. By default (`--provider auto`), it will attempt to use the X API if a token is present, fallback to `gallery-dl` if installed, or fail with setup instructions.

### 1. gallery-dl (Preferred MVP)
Fast and practical CLI scraper for media and timelines.
- **Install**: `py -m pip install gallery-dl`
- **Usage**: Automatically selected if installed.

### 2. Cookies (Optional)
If X blocks unauthenticated requests, you can pass your browser cookies to the provider (if supported):
- **Usage**: `--cookies-from-browser firefox` (or `chrome`, `edge`)

### 3. X API
Official API usage, most reliable but requires a developer account.
- **Setup**: Set environment variable `X_BEARER_TOKEN` with your API token.
- **Usage**: Automatically selected if token is found.

### 4. Manual Fallback
If automated providers fail, you can manually supply a JSON file (e.g. copied from network tools).
- **Usage**: 
  ```powershell
  py scripts\fetch_x_posts.py --provider manual-json --input-json samples\x_posts_sample.json --output-json runtime\x_posts\latest_posts.json
  ```

## Limitations

- **X Restrictions**: X/Twitter aggressively limits unauthenticated scraping. The `gallery-dl` provider may fail if blocked.
- **No Captcha Bypass**: If an account hits a captcha wall, the fetch will fail.
- **No Credentials Committed**: Cookies and tokens must be supplied locally. Do not commit `.env` or runtimes.
- **No Publishing APIs**: This adapter is strictly for ingestion. Publishing remains a manual step.
