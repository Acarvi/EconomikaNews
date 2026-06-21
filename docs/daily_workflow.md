# Daily Local Workflow

The daily workflow wrapper runs the existing local pipeline and health report commands in sequence. It provides stable output paths and can open the final report and publish queue folder for manual review.

## Daily Command

```powershell
py scripts\run_daily_workflow.py --overwrite --open-report --open-publish-queue
```

Safe dry run:

```powershell
py scripts\run_daily_workflow.py --dry-run --open-report
```

The wrapper forwards `--overwrite`, `--dry-run`, and `--continue-on-error` to the local pipeline runner. Custom paths are available through `--summary-json`, `--report-md`, `--report-json`, and `--publish-queue-dir`.

## Outputs

Default local outputs are:

```text
runtime/reports/latest_pipeline_summary.json
runtime/reports/latest_pipeline_report.md
runtime/publish_queue/
```

The wrapper captures subprocess output and prints one concise final JSON summary. If the pipeline fails after writing its summary, report generation is still attempted. Problems opening local files or folders are warnings and do not turn an otherwise successful workflow into a failure.

## Manual Boundary

Manual upload starts from `runtime/publish_queue/`. Opening the queue folder or report is only a local convenience; the wrapper does not publish anything.

No TikTok, Instagram, or YouTube APIs, OAuth, browser automation, scheduling, or cloud storage are implemented. Generated runtime files must not be committed.

The individual pipeline and report scripts remain available for debugging and targeted reruns.
