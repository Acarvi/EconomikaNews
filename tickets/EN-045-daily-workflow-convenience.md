# EN-045 Daily Workflow Convenience

## Objective

Add one convenient local command that runs the artifact pipeline, generates its health report, and optionally opens local review paths. Keep all publishing and upload activity manual.

## Scope

- Add `scripts/run_daily_workflow.py` as a thin subprocess wrapper.
- Run the existing local pipeline with a stable summary path.
- Generate the existing Markdown health report and optional JSON report.
- Forward overwrite, dry-run, continue-on-error, output paths, and Python executable selection.
- Optionally open the report and publish queue folder with the operating system default handler.
- Print a concise final JSON summary.
- Add deterministic no-network tests with mocked subprocess and opener behavior.
- Document the daily workflow and debugging alternatives.

## Out of scope

- TikTok, Instagram, or YouTube APIs.
- OAuth or browser automation publishing.
- Scheduling.
- AI caption generation or LLM text rewriting.
- Audio, subtitles, or animations.
- Dashboard or database changes.
- Cloud storage.
- Committed runtime files.

## Regression tests

- Protect pipeline then report command order and exact flag/path forwarding.
- Verify pipeline and report failures produce unsuccessful final summaries.
- Verify report generation continues after pipeline failure when a summary exists.
- Verify report generation is skipped clearly when a failed pipeline leaves no summary.
- Verify existing report and queue paths can be opened through the mocked helper.
- Verify missing paths and opener failures are warnings rather than hard failures.
- Verify subprocess launch failures and CLI summary output.

## CI/CD checks

- `py -m compileall app tests scripts`
- `py -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- `py -m pytest -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- `py scripts\run_daily_workflow.py --overwrite`
- `py scripts\run_daily_workflow.py --dry-run`
- `py scripts\run_daily_workflow.py --overwrite --open-report --open-publish-queue`
- `Get-Content runtime\reports\latest_pipeline_report.md -TotalCount 220`

## Senior review notes

- Risk assessment: low; the wrapper delegates artifact writes and validation to existing tested scripts.
- Regression confidence: high for command construction, failure handling, optional opening, and final summary behavior.
- Follow-ups: use individual pipeline/report commands when stage-level diagnosis is needed.

## Rollback notes

- Revert strategy: remove the wrapper, tests, docs, README section, related doc additions, and ticket.
- Data/runtime impact: generated report, summary, and publish queue files remain ignored and can be deleted safely.
