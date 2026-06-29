# EN-049: Real X Ingestion Adapter

## Goal
Implement a real X/Twitter ingestion adapter that can fetch recent posts from configured accounts and write a JSON file compatible with `scripts/make_reels_from_x.py`.

## Background
The previous MVP (EN-048) relied on a sample JSON file to test the reel generation logic. To be useful in production, we need the ability to fetch real posts from X accounts.

## Requirements
1. **Script**: `scripts/fetch_x_posts.py`
2. **Provider Architecture**: Support multiple scraping/API methods (`manual-json`, `gallery-dl`, `yt-dlp`, `x-api`) to handle varying levels of platform restriction.
3. **Data Normalization**: Extract `text`, `url`, `post_id`, `created_at`, metrics, and media.
4. **Output Shape**: Must be a JSON object containing a `posts` array compatible with `make_reels_from_x.py`.
5. **CLI Interface**: Allow specifying accounts, max posts, dates, and provider overrides.
6. **Testing**: No-network unit tests using mocked subprocesses and `tmp_path`.

## Non-Goals
- Full reliability bypassing X captchas/paywalls.
- Committing secrets or cookies.
- Publishing functionality.

## Acceptance Criteria
- `fetch_x_posts.py` successfully normalizes posts and saves `latest_posts.json`.
- The `make_reels_from_x.py` script can consume `latest_posts.json` and generate an MP4.
- Providers fail clearly with setup instructions when dependencies are missing.
- Tests pass with >75% coverage.
