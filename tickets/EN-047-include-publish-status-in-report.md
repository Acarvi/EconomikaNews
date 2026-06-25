# EN-047 Include publish status in report

## Objective

Include manual publish status tracking in the local pipeline health report so the user can see which platform uploads are pending, published, skipped, failed, etc. directly from `runtime/reports/latest_pipeline_report.md`.

## Scope

- Update `scripts/build_pipeline_report.py` to optionally read publish status.
- Add CLI arg `--publish-status-file` (defaulting to `runtime/publish_status/status.json`).
- Include publish status in JSON summary output.
- Include publish status in Markdown report.
- Preserve behavior when status file is missing or invalid.
- Add no-network tests.
- Update docs.

## Out of scope

- TikTok, Instagram, or YouTube APIs and OAuth.
- Browser automation, publishing, or scheduling.
- AI caption generation or text rewriting.
- Audio, subtitles, or animations.
- Dashboard or database changes.
- Cloud storage or committed runtime files.

## Regression tests

- Verify missing status file defaults platform statuses to pending and exposes `publish_status_found=false`.
- Verify valid status file shows published platform in Markdown with `external_url` and `notes`.
- Verify manual upload checklist item checked/unchecked states for `published`, `pending`, `skipped`, `failed`.
- Verify JSON summary fields: `publish_status_found`, `publish_status_counts`, `publish_complete`, etc.
- Verify invalid status JSON reported as warnings but doesn't crash or alter `overall_ready`.
- Verify unmatched status entry appears in unmatched section.
- Run tests in a new file `tests/test_build_pipeline_report_status.py` using `tmp_path` and no network.

## CI/CD checks

- `py -m compileall app tests scripts`
- `$env:PYTHONPATH="d:\Scripts\EconomikaNews"; py -m pytest --cov=app --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp=economika-pytest-tmp`

## Manual validation

- `py scripts\build_pipeline_report.py --pipeline-summary runtime\reports\latest_pipeline_summary.json`
- Inspect `runtime/reports/latest_pipeline_report.md` manual publish status tables and checklist items.

## Senior review notes

- Risk assessment: Low; the feature strictly parses a local JSON file and renders Markdown / JSON summary fields.
- Regression confidence: High after verification with the full repository test suite.

## Rollback notes

- Revert strategy: Revert the EN-047 commit; no database or environment rollback is required.
- Data/runtime impact: Ignored status file `runtime/publish_status/status.json` can remain untouched.
