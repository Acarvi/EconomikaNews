# EN-044 Local Pipeline Health Report

## Objective

Add a local Markdown health report that summarizes pipeline manifests and an optional runner summary for quick operational review. Preserve the manual-upload boundary without adding publishing integrations.

## Scope

- Add `scripts/build_pipeline_report.py`.
- Read render, video, and publish queue manifests without crashing on missing or invalid inputs.
- Optionally include a local pipeline runner summary.
- Report artifact readiness counts, warnings, errors, packet provenance, paths, caption previews, and manual upload checklists.
- Write Markdown and optional JSON summaries atomically.
- Add no-network tests using temporary fake manifests.
- Document report generation and readiness behavior.

## Out of scope

- TikTok, Instagram, or YouTube APIs.
- OAuth or browser automation.
- Scheduling.
- AI caption generation or LLM text rewriting.
- Audio, subtitles, or animations.
- Dashboard or database changes.
- Cloud storage.
- Committed runtime report files.

## Regression tests

- Valid manifests produce a ready Markdown report with counts and packet paths.
- Source provenance, caption paths, and manual upload checklist content are retained.
- Missing render and video manifests produce warnings without blocking ready packets.
- Missing or invalid publish queue manifests produce errors and prevent readiness.
- Invalid JSON inputs do not crash generation.
- Optional pipeline summaries and failed stages are rendered.
- Optional JSON output is valid and atomic writes leave no temporary files.
- CLI stdout contains the required machine-readable summary fields.

## CI/CD checks

- `py -m compileall app tests scripts`
- `py -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- `py -m pytest -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- `py scripts\run_local_pipeline.py --overwrite --summary-json runtime\reports\latest_pipeline_summary.json`
- `py scripts\build_pipeline_report.py --pipeline-summary runtime\reports\latest_pipeline_summary.json`
- `Get-Content runtime\reports\latest_pipeline_report.md -TotalCount 220`

## Senior review notes

- Risk assessment: low; the report reads ignored local JSON artifacts and writes ignored report files.
- Regression confidence: high for readiness, tolerance, Markdown content, runner summary handling, and atomic output behavior.
- Follow-ups: future local review tools may consume the optional JSON report without changing the publishing boundary.

## Rollback notes

- Revert strategy: remove the report script, tests, docs, README additions, runner-doc addition, and ticket.
- Data/runtime impact: generated files under `runtime/reports/` are ignored and can be deleted safely.
