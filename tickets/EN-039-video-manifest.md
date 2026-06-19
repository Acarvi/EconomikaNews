# EN-039 Video Manifest

## Objective

Add a local video manifest builder that indexes generated MP4 files and their metadata. This gives future upload and publishing stages a stable artifact list without scanning `runtime/videos/` ad hoc.

## Scope

- Add `scripts/build_video_manifest.py`.
- Scan direct child directories under `runtime/videos/`.
- Read `video.mp4` file stats and optional `video_metadata.json`.
- Validate metadata fields needed for upload readiness.
- Write `runtime/videos/manifest.json` atomically.
- Report invalid videos and not-ready video errors in CLI summary JSON.
- Add no-network tests using fake MP4 bytes and metadata JSON.
- Document the video manifest command, input, output, and readiness rules.

## Out of scope

- Publishing or upload APIs.
- Scheduling.
- AI generation.
- Text-to-speech/audio.
- Animations.
- Dashboard changes.
- Media compositing.
- Video rendering changes.
- Database changes.
- Cloud storage.
- Committed runtime video or manifest files.

## Regression tests

- Missing and empty video directories create empty manifests.
- Valid video plus matching metadata creates one ready manifest entry.
- Missing and zero-byte `video.mp4` files are counted as invalid.
- Missing or invalid metadata keeps the video entry but marks it not ready.
- Metadata `post_id`, `video_path`, `ready_for_upload`, `video_errors`, dimensions, duration, and FPS affect readiness.
- Direct files inside `runtime/videos/`, including `manifest.json`, are ignored.
- `--include-invalid` controls whether invalid details are written to the manifest.
- Summary errors include invalid video errors and not-ready video errors.
- Manifest writes use a temporary file and atomic replace.
- CLI summary JSON is printed.

## CI/CD checks

- `python -m compileall app tests scripts`
- `python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- `python -m pytest -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- `python scripts\build_video_manifest.py`
- `Get-Content runtime\videos\manifest.json -TotalCount 160`

## Senior review notes

- Risk assessment: low, because the script only reads local video artifacts and metadata JSON, then writes an ignored runtime manifest.
- Regression confidence: high for manifest behavior because tests cover ready, not-ready, invalid, sorting, summary, and CLI paths without video decoding.
- Follow-ups: consume `runtime/videos/manifest.json` from a future upload/publishing ticket.

## Rollback notes

- Revert strategy: remove the script, tests, docs, README link, and ticket.
- Data/runtime impact: generated `runtime/videos/manifest.json` is ignored and can be deleted safely.
