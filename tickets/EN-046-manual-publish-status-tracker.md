# EN-046 Manual Publish Status Tracker

## Objective

Add a local status tracker that records the result of each manual publish queue upload per post and platform without introducing platform publishing integrations.

## Scope

- Add `scripts/update_publish_status.py` with `mark`, `list`, and `summary` commands.
- Store local status in `runtime/publish_status/status.json` with atomic writes and change history.
- Track external URLs, notes, update timestamps, and the first published timestamp.
- Validate post/platform pairs against the optional publish queue manifest, with warning and strict modes.
- Synthesize `pending` entries for untracked queue packet/platform combinations.
- Add JSON and compact text output plus no-network tests and operator documentation.

## Out of scope

- TikTok, Instagram, or YouTube APIs and OAuth.
- Browser automation, publishing, or scheduling.
- AI caption generation or text rewriting.
- Audio, subtitles, or animations.
- Dashboard or database changes.
- Cloud storage or committed runtime files.

## Regression tests

- Cover missing and invalid status files, entry creation/update, history, timestamps, URL, and notes.
- Cover invalid platforms/statuses and strict/non-strict manifest validation.
- Cover pending manifest entries, list filters, summary counts, text output, and atomic writes.
- Run entirely against `tmp_path` and fake manifests with no network access.

## CI/CD checks

- `py -m compileall app tests scripts`
- `py -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- `py -m pytest -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- Confirm the tracked secret/runtime artifact scan is clean, including `runtime/publish_status/`.

## Manual validation

- `py scripts\update_publish_status.py list --format text`
- `py scripts\update_publish_status.py summary --format text`
- `py scripts\update_publish_status.py mark --post-id 2057499359705813029 --platform tiktok --status published --external-url "https://example.com/manual-test" --notes "Manual test"`
- Repeat list and summary commands and inspect `runtime/publish_status/status.json`.

## Senior review notes

- Risk assessment: Low; the feature writes only an ignored local JSON artifact and performs no network operations.
- Regression confidence: High after focused CLI tests and the full repository suite.
- Follow-ups: Platform publishing, scheduling, dashboards, and remote persistence remain separate future work.

## Rollback notes

- Revert strategy: Revert the EN-046 commit; no schema or service rollback is required.
- Data/runtime impact: Existing ignored `runtime/publish_status/status.json` can be retained or deleted manually without affecting the pipeline.
