# Local Pipeline Runner

The local pipeline runner executes the complete artifact preparation flow with one command. It orchestrates existing scripts and does not upload or publish content.

```powershell
python scripts\run_local_pipeline.py --overwrite
```

## Stages

Stages run in this order:

1. `build_render_inputs`
2. `render_cards`
3. `build_render_manifest`
4. `export_videos`
5. `build_video_manifest`
6. `build_publish_queue`
7. `build_publish_queue_manifest`

Each stage runs as a subprocess using the selected Python executable. A failed stage stops later stages by default. Use `--continue-on-error` to run the remaining stages while retaining a failing final exit code.

## Options

- `--overwrite` forwards overwrite behavior to `build_render_inputs.py`, `render_text_cards.py`, `export_card_videos.py`, and `build_publish_queue.py`.
- `--limit N` forwards the limit to card rendering, video export, and publish queue generation. `build_render_inputs.py` does not support a limit.
- `--python-executable PATH` selects the Python executable used for every stage.
- `--summary-json PATH` atomically writes the final summary in addition to printing it.
- `--continue-on-error` continues after failures. `--stop-on-error` is the default.

Individual stages can be omitted with `--skip-render-inputs`, `--skip-cards`, `--skip-render-manifest`, `--skip-videos`, `--skip-video-manifest`, `--skip-publish-queue`, and `--skip-publish-queue-manifest`. Skipped stages remain visible in the summary with a reason.

## Dry Run

```powershell
python scripts\run_local_pipeline.py --dry-run
```

Dry-run is forwarded to the four scripts that support it: render input generation, card rendering, video export, and publish queue generation. The three manifest builders are skipped with reason `dry-run` because they write manifest files and do not expose their own dry-run option. This keeps the pipeline dry-run free of artifact writes. An explicitly requested `--summary-json` is still written.

## Summary JSON

The command prints one final JSON object containing timestamps, elapsed time, overall success, selected execution flags, stage results, errors, and standard artifact paths. Each stage records its command, return code, raw stdout and stderr, parsed JSON stdout when available, timing, skip state, and error.

The runner exits `0` only when every non-skipped stage succeeds. It exits `1` after any stage or summary-file write failure.

## Health Report

After running the pipeline, generate a compact local health report:

```powershell
py scripts\build_pipeline_report.py
```

See [`pipeline_report.md`](pipeline_report.md) for runner-summary integration and report readiness rules.

## Publishing Boundary

The final local handoff remains `runtime/publish_queue/`. Manual upload starts from the packet directories and `runtime/publish_queue/manifest.json`. The runner has no TikTok, Instagram, or YouTube API integration, OAuth, browser automation, or scheduling behavior.

Generated runtime artifacts must not be committed.
