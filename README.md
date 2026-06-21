# Economica News

Economica News is a local-first rebuild of the EconomikaNews repository: a small product for discovering high-signal economic and political stories, scoring them, generating short-form media candidates, reviewing them, queueing approved posts, and handing publication to the central publishing service.

## Current Status

Post-wipe clean rebuild.

## MVP Flow

discover -> score -> generate -> review -> queue -> publish

## Technical Risk

The biggest technical risk is X ingestion.

## Ingestion Direction

Economica News core code uses an ingestion provider abstraction. Dashboard, scoring, rendering, review, queueing, and publishing code should depend on normalized ingestion models rather than X-specific or vendor-specific payloads.

The first real provider candidate is EN-021: a free experimental X internal API research spike. This path may use unofficial/internal X APIs and should be treated as unstable until proven otherwise.

Playwright/browser login is diagnostic and fallback tooling only. It is not the production ingestion path and should not be treated as core architecture.

## Architecture Rule

Publishing belongs to CentralPublishingHub, not Economica News. This repository may prepare and queue publishing requests, but platform publishing logic must live in the central service.

## First Phases

- Phase 0: skeleton
- Phase 1: ingestion provider abstraction
- Phase 2: EN-021 X internal API research spike

## Local Commands

```bash
python -m pytest
python -m compileall app tests scripts
```

Engineering quality standards: [`docs/engineering_quality.md`](docs/engineering_quality.md).

## Local Candidate Dashboard

Generate candidate JSON:

```bash
python scripts\x_fetch_accounts_probe.py --config runtime\config\x_internal.local.yaml --resolve-user-id --include-media --output-json
```

Start the local dashboard:

```bash
python scripts\run_dashboard.py --db-path runtime\economika_news.db
```

Open `http://127.0.0.1:8088`.

Candidate review status is stored in SQLite. The candidate JSON file remains
read-only.

Export approved candidates:

```bash
python scripts\export_approved_candidates.py --db-path runtime\economika_news.db
```

Build approved media bundles:

```bash
python scripts\build_approved_media_bundle.py
```

Build the approved bundle index:

```bash
python scripts\build_approved_bundle_index.py
```

Build render input contract files:

```bash
python scripts\build_render_inputs.py
```

Render local static visual text cards:

```bash
python scripts\render_text_cards.py
```

Build the render manifest:

```bash
python scripts\build_render_manifest.py
```

Export simple local MP4 videos from rendered cards:

```bash
python scripts\export_card_videos.py
```

Build the video manifest:

```bash
python scripts\build_video_manifest.py
```

Build local manual-upload publish queue packets:

```bash
python scripts\build_publish_queue.py
```

Build the publish queue manifest:

```bash
python scripts\build_publish_queue_manifest.py
```

Run the complete local artifact pipeline:

```bash
python scripts\run_local_pipeline.py --overwrite
```

Generate the local pipeline health report:

```bash
py scripts\build_pipeline_report.py
```

## Daily Local Workflow

Run the pipeline, generate its health report, and open the local review paths:

```bash
py scripts\run_daily_workflow.py --overwrite --open-report --open-publish-queue
```

For more details on bundling, the index, metadata schema, and CLI options, see [`docs/approved_media_bundle.md`](docs/approved_media_bundle.md). For renderer input JSON files, see [`docs/render_input_contract.md`](docs/render_input_contract.md). For static PNG text cards, see [`docs/text_card_renderer.md`](docs/text_card_renderer.md). For the generated render manifest, see [`docs/render_manifest.md`](docs/render_manifest.md). For local MP4 video export, see [`docs/video_export.md`](docs/video_export.md). For the generated video manifest, see [`docs/video_manifest.md`](docs/video_manifest.md). For local publish queue packets, see [`docs/publish_queue.md`](docs/publish_queue.md). For the generated publish queue manifest, see [`docs/publish_queue_manifest.md`](docs/publish_queue_manifest.md). For one-command local orchestration, see [`docs/local_pipeline_runner.md`](docs/local_pipeline_runner.md). For the Markdown health report, see [`docs/pipeline_report.md`](docs/pipeline_report.md). For daily operation, see [`docs/daily_workflow.md`](docs/daily_workflow.md).

## Commit Hygiene

Do not commit `runtime/`, `.env`, browser profiles, tokens, cookies, outputs, or other local artifacts.
