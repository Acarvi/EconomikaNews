# EN-024 X media extraction download probe

## Objective

Expose usable image/video media URLs from X internal timeline payloads and add a local probe that downloads returned media into ignored runtime storage.

## Scope

- Extract image media URLs from `media_url_https` or `media_url`.
- Extract video media URLs from the highest bitrate MP4 variant, with safe fallback when no MP4 exists.
- Add optional media details to `scripts/x_internal_probe.py`.
- Add `scripts/x_download_media_probe.py` for local media downloads under `runtime/downloads/x`.
- Add no-network tests using sample JSON only.

## Out of scope

- Multi-account scanning.
- Scheduler, SQLite, dashboard, rendering, or publishing.
- Browser automation.
- Paid providers.
- Committed secrets or runtime files.

## Acceptance criteria

- Images produce `SourceMedia(media_type="image", url=..., preview_url=...)`.
- Videos prefer the highest bitrate MP4 variant.
- Unknown media shapes do not crash normalization.
- Download probe supports `--dry-run` and writes only under ignored runtime paths by default.
- Tests do not make network calls.

## Validation commands

- `python -m compileall app tests scripts`
- `python -m pytest`
- `git status --short`
- `git ls-files runtime "*/x_headers.json" x_headers.json .env ".env.*"`
