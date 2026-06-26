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

For the quickest local video review, generate a copied preview folder with:

```powershell
py scripts\generate_preview_reel.py --overwrite --open
```

This writes `runtime/preview_reels/<post_id>/reel.mp4`, `caption.txt`, and `preview_report.md`. See [`preview_reel.md`](preview_reel.md).

After each manual upload attempt, record the outcome with `update_publish_status.py`:

```powershell
py scripts\update_publish_status.py mark --post-id <post_id> --platform tiktok --status published --external-url "https://..."
py scripts\update_publish_status.py summary --format text
```

The status tracker writes only to local `runtime/publish_status/status.json`. See [`manual_publish_status.md`](manual_publish_status.md) for statuses, filters, and strict manifest validation.

No TikTok, Instagram, or YouTube APIs, OAuth, browser automation, scheduling, or cloud storage are implemented. Generated runtime files must not be committed.

The individual pipeline and report scripts remain available for debugging and targeted reruns.
