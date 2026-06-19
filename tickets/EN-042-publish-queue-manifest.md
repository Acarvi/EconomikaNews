# EN-042 Publish Queue Manifest

## Objective

Add a manifest builder for local publish queue packets so future dashboard, manual-review, and publishing stages can consume a stable packet list. The manifest should preserve source provenance, platform targets, caption previews, and packet readiness.

## Scope

- Add `scripts/build_publish_queue_manifest.py`.
- Scan direct child packet folders under `runtime/publish_queue/`.
- Validate `video.mp4`, `caption.txt`, and `metadata.json`.
- Read packet metadata and preserve source account handle, source URL, platforms, and manual upload state.
- Include caption length and normalized caption preview.
- Write `runtime/publish_queue/manifest.json` atomically.
- Add no-network tests with fake MP4 bytes.
- Document the manifest command, input/output, and readiness rules.

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

- Missing and empty queue directories create empty manifests.
- Valid packets create manifest entries with provenance, platforms, caption length, and caption preview.
- Missing and zero-byte videos are counted as invalid.
- Missing caption and metadata keep packets not ready and appear in summary errors.
- Invalid metadata JSON keeps packets not ready.
- Metadata `post_id`, `video_path`, and `caption_path` mismatches keep packets not ready.
- `packet_ready: false`, metadata packet errors, `manual_upload: false`, and empty platforms keep packets not ready.
- Direct files inside the queue directory, including `manifest.json`, are ignored.
- `--include-invalid` controls invalid packet details.
- Manifest writes are atomic.
- CLI summary JSON is printed.

## CI/CD checks

- `python -m compileall app tests scripts`
- `python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- `python -m pytest -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- `python scripts\build_publish_queue_manifest.py`
- `Get-Content runtime\publish_queue\manifest.json -TotalCount 180`

## Senior review notes

- Risk assessment: low, because the builder only reads local ignored publish queue artifacts and writes an ignored runtime manifest.
- Regression confidence: high for manifest behavior because tests cover valid, invalid, not-ready, summary, and CLI paths.
- Follow-ups: consume `runtime/publish_queue/manifest.json` from future dashboard/manual review or upload tickets.

## Rollback notes

- Revert strategy: remove the script, tests, docs, README link, and ticket.
- Data/runtime impact: generated `runtime/publish_queue/manifest.json` is ignored and can be deleted safely.
