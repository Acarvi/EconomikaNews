# EN-040 Local Publishing Queue

## Objective

Add a local publish queue packet builder that prepares generated videos, deterministic captions, and metadata for manual upload. This creates a stable handoff folder without implementing platform publishing APIs.

## Scope

- Add `scripts/build_publish_queue.py`.
- Read `runtime/videos/manifest.json`.
- Include only `ready_for_upload: true` videos by default.
- Copy ready videos into `runtime/publish_queue/<post_id>/video.mp4`.
- Generate deterministic Spanish `caption.txt` from existing metadata only.
- Generate `metadata.json` for manual upload packets.
- Support `--include-not-ready`, `--overwrite`, `--dry-run`, `--limit`, and `--platform`.
- Add no-network tests with fake MP4 bytes.
- Document the manual publish queue workflow.

## Out of scope

- TikTok, Instagram, or YouTube APIs.
- OAuth.
- Browser automation.
- Scheduling.
- AI caption generation or text rewriting via LLM.
- Audio, subtitles, or animations.
- Dashboard changes.
- Database changes.
- Cloud storage.
- Committed runtime publish files.

## Regression tests

- Missing and invalid video manifests return exit code 1.
- Invalid manifest shape returns exit code 1.
- Empty manifests produce zero-packet summaries.
- Ready videos create packet folders with copied video, caption, and metadata.
- Captions remain under 500 characters.
- Missing source handles use `Fuente: desconocida`.
- Source handles appear in captions when available.
- Not-ready videos are skipped by default and packaged as not ready when included.
- Missing video files are skipped with errors.
- Existing packets are skipped unless `--overwrite` is passed.
- Dry runs create no files.
- `--limit` limits selected packets.
- Platform normalization supports defaults, repeated values, and comma-separated values.
- Invalid platforms return clear errors.
- Atomic temp files are not left behind on success.
- Runtime publish queue files are not tracked.

## CI/CD checks

- `python -m compileall app tests scripts`
- `python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- `python -m pytest -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- `python scripts\build_publish_queue.py --overwrite`
- `dir runtime\publish_queue\2057499359705813029`
- `Get-Content runtime\publish_queue\2057499359705813029\caption.txt`
- `Get-Content runtime\publish_queue\2057499359705813029\metadata.json -TotalCount 120`

## Senior review notes

- Risk assessment: low, because packets are local ignored runtime artifacts and the script performs no platform calls.
- Regression confidence: high for queue behavior because tests cover manifest loading, packet writes, captions, platform parsing, skip paths, and dry run.
- Follow-ups: add actual upload/publishing integrations only in a separate ticket after manual packets are validated.

## Rollback notes

- Revert strategy: remove the script, tests, docs, README link, and ticket.
- Data/runtime impact: generated `runtime/publish_queue/` artifacts are ignored and can be deleted safely.
