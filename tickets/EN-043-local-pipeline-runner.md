# EN-043 Local Pipeline Runner

## Objective

Add a one-command local runner for the complete artifact pipeline. Produce a clear machine-readable execution summary without adding platform publishing behavior.

## Scope

- Add `scripts/run_local_pipeline.py` to execute the seven existing pipeline scripts in order.
- Support overwrite, dry-run, limit, stage skips, Python executable selection, and stop or continue on error.
- Parse JSON stage stdout while retaining raw stdout and stderr.
- Print a final summary and optionally write it atomically.
- Skip manifest writers during dry-run so no artifact manifests are written.
- Add fast no-network tests using mocked subprocesses.
- Document the command and publishing boundary.

## Out of scope

- TikTok, Instagram, or YouTube APIs.
- OAuth or browser automation.
- Scheduling.
- AI caption generation or LLM text rewriting.
- Audio, subtitles, or animations.
- Dashboard or database changes.
- Cloud storage.
- Committed runtime files.

## Regression tests

- Protect default stage order and stage skip reporting.
- Verify overwrite, dry-run, and limit flags reach only supported scripts.
- Verify manifest writers are skipped during dry-run.
- Cover parsed JSON and retained non-JSON subprocess output.
- Cover stop-on-error, continue-on-error, and subprocess launch failures.
- Verify artifact paths and custom Python executable commands.
- Verify atomic summary writes and clear summary write failures.

## CI/CD checks

- `python -m compileall app tests scripts`
- `python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- `python -m pytest -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- `python scripts\run_local_pipeline.py --overwrite`
- `python scripts\run_local_pipeline.py --dry-run`
- `Get-Content runtime\publish_queue\manifest.json -TotalCount 180`

## Senior review notes

- Risk assessment: low to moderate; orchestration is new, but each artifact stage remains independently owned and unchanged.
- Regression confidence: high for command construction, failure flow, summaries, and dry-run behavior because subprocesses are mocked deterministically.
- Follow-ups: manual upload or a future central publishing service can consume `runtime/publish_queue/`; platform APIs remain outside this repository.

## Rollback notes

- Revert strategy: remove the runner, tests, documentation, README entry, and ticket.
- Data/runtime impact: the runner only invokes existing generators; their ignored runtime artifacts can be deleted safely.
