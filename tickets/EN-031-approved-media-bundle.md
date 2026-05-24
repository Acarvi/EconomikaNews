# Ticket: EN-031 Build Approved Media Bundle

## Objective

Create a local approved-media bundle step that takes approved candidates and materializes stable per-post folders with metadata and downloaded media, preparing for future rendering and publishing.

## Scope

- Create a feature CLI script `scripts/build_approved_media_bundle.py`.
- Read approved candidates from `runtime/outputs/approved_candidates.json` (customizable path).
- For each approved candidate, build a bundle under `runtime/approved/<post_id>/`.
- Write `metadata.json` atomically via `metadata.json.tmp` and replace.
- Extract direct media URLs (`http://`, `https://`) while filtering out dangerous/non-http URLs and ignoring `t.co` URLs.
- Download media using standard library `urllib.request`.
- Name downloaded files deterministically: `media_1.<ext>`, `media_2.<ext>`, etc.
- Support extension inference priority: `content-type` -> URL path suffix -> `.bin` fallback. Query parameters are ignored for extension inference.
- Support `--overwrite` flag for media files (using tmp + atomic replace) and `--dry-run` flag (no files written, no directories created).
- Skip existing media files if `--overwrite` is false, and count as `media_skipped`.
- Handle errors gracefully: log invalid-candidate and media errors to the summary and individual media errors to metadata while continuing the run.
- Write usage documentation under `docs/approved_media_bundle.md` and link in `README.md`.
- Implement thorough no-network tests using mock downloader.

## Out of scope

- Video rendering
- Captions generation
- Publishing / scheduling
- AI summarization / generation
- Dashboard changes / queue worker
- Cloud storage
- Committed runtime media/output files

## Regression tests

- Test missing approved file returns exit code 1.
- Test invalid top-level JSON returns exit code 1.
- Test top-level JSON object validation (`candidates` missing or not a list) returns exit code 1.
- Test empty approved list writes summary with zero bundles.
- Test candidate without media creates metadata with `local_media` empty.
- Test candidate with media writes media file and metadata `local_media` entry.
- Test overwrite false skips existing media.
- Test overwrite true replaces existing media atomically.
- Test dry-run writes no files and creates no directories.
- Test media download error records error but continues.
- Test extension inference priority (`content-type` > URL path suffix > `.bin` fallback), and query parameters ignored.
- Test dangerous or non-http URLs are skipped.
- Test `t.co` URLs are skipped.
- Test candidate-level tweet URLs are not treated as media.
- Test X/Twitter status URLs are skipped.
- Test invalid candidate without `post_id` skipped with error.
- Verify no runtime/approved files are tracked.

## CI/CD checks

- `python -m compileall app tests scripts`
- `python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- `python -m pytest -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- Tracked runtime/secret artifact scan must be clean.

## Manual validation

- Export approved:
  `python scripts\export_approved_candidates.py --db-path runtime\economika_news.db`
- Build bundle:
  `python scripts\build_approved_media_bundle.py`
- Validate output directory:
  Check for folder `runtime/approved/<post_id>/` and verify structure:
  - `metadata.json` exists
  - `media_1.<ext>` exists for candidates with media

## Senior review notes

- Risk assessment: Low. The script runs as a standalone CLI step and only modifies local `runtime/approved/` files.
- Regression confidence: High. Extensive unit tests covering all paths and edge cases.
- Follow-ups: Future ticket will consume these materialized bundles for rendering.

## Rollback notes

- Revert strategy: Revert PR #31, delete branch.
- Data/runtime impact: No database schema changes are introduced. Deleting the `runtime/approved/` folder will clean up the materialized bundles.
