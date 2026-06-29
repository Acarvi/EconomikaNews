# Local Pipeline Health Report

The local pipeline health report turns generated manifests into a compact Markdown operations view. It reports readiness, artifact counts, errors and warnings, source provenance, packet paths, caption previews, and a manual upload checklist.

## Usage

Generate a report from the standard local manifests:

```powershell
py scripts\build_pipeline_report.py
```

To include the pipeline runner outcome:

```powershell
py scripts\run_local_pipeline.py --overwrite --summary-json runtime\reports\latest_pipeline_summary.json
py scripts\build_pipeline_report.py --pipeline-summary runtime\reports\latest_pipeline_summary.json
```

The default Markdown output is:

```text
runtime/reports/latest_pipeline_report.md
```

Use `--output-json PATH` to also write the machine-readable report summary. Both output formats are written atomically through adjacent `.tmp` files.

## Readiness

`overall_ready` is true only when the publish queue manifest is valid, at least one packet is ready for manual upload, and the report has no errors. Missing or invalid render and video manifests are warnings when ready publish packets remain available. A missing or invalid publish queue manifest, invalid publish packets, packet errors, no ready packets, or failed pipeline stages makes the report not ready.

Missing and invalid input files do not crash report generation. Their status is recorded in the Markdown and JSON summaries.

## Local Boundary

This report is for local, manual operational review. It does not call TikTok, Instagram, or YouTube APIs; perform OAuth or browser automation; schedule posts; or claim that any packet was published. Manual upload continues from `runtime/publish_queue/`.

To create a single ready-to-watch copied MP4 preview from the first ready packet, run:

```powershell
py scripts\generate_preview_reel.py --overwrite --open
```

The preview command writes `runtime/preview_reels/<post_id>/reel.mp4` plus the caption, metadata, card preview when available, and a short upload checklist. See [`preview_reel.md`](preview_reel.md).

Generated files under `runtime/reports/` and `runtime/preview_reels/` are runtime artifacts and must not be committed.

After manual upload, record the platform outcome with `update_publish_status.py`. This local-only tracker writes `runtime/publish_status/status.json`; the pipeline report does not claim or infer that a packet was published. See [`manual_publish_status.md`](manual_publish_status.md).

For normal daily operation, [`daily_workflow.md`](daily_workflow.md) runs the pipeline and this report together. The individual report command remains available for debugging and targeted regeneration.
