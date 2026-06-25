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

## Integration with Publish Status

By default, the report generator reads local manual upload statuses from:
```text
runtime/publish_status/status.json
```
Use `--publish-status-file PATH` to specify a different path. 

- **Missing Status File**: Exposes `publish_status_found=false`. All packet/platform combinations default to `pending` status without causing a fatal error.
- **Invalid JSON**: Exposes `publish_status_found=true` and `publish_status_valid=false`. The report includes a warning with the validation error detail, but does not crash or alter `overall_ready`.
- **Merged Platform Status**: The report matches entries by `post_id` + `platform` and appends a "Manual Publish Status" table to each Publish Queue packet section.
- **Cheklist Updates**: Checklist items are updated based on platform status:
  - `published` / `skipped`: Rendered as checked (`- [x]`).
  - `failed`: Rendered as unchecked (`- [ ]`) and prompts for retry.
  - `pending` / others: Rendered as unchecked (`- [ ]`) prompting for manual upload.
- **Unmatched Status Entries**: Any recorded status in the file that does not match a post/platform in the active publish queue manifest is listed under the "Unmatched Publish Status Entries" section.

## Local Boundary

This report is for local, manual operational review. It does not call TikTok, Instagram, or YouTube APIs; perform OAuth or browser automation; schedule posts; or claim that any packet was published. Manual upload continues from `runtime/publish_queue/`.

Generated files under `runtime/reports/` are runtime artifacts and must not be committed.

After manual upload, record the platform outcome with `update_publish_status.py`. This local-only tracker writes `runtime/publish_status/status.json`. See [`manual_publish_status.md`](manual_publish_status.md).

For normal daily operation, [`daily_workflow.md`](daily_workflow.md) runs the pipeline and this report together. The individual report command remains available for debugging and targeted regeneration.
