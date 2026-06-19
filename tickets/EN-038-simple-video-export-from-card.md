# EN-038 Simple Video Export From Card

## Objective

Add a local video export step that converts rendered static card PNGs into short vertical MP4 videos. This prepares the pipeline for later social-platform upload work without implementing publishing.

## Scope

- Add `scripts/export_card_videos.py`.
- Read `runtime/renders/manifest.json` and export one video per selected render.
- Include only `ready_for_publish: true` renders by default.
- Support `--include-not-ready`, `--overwrite`, `--dry-run`, `--limit`, `--duration-seconds`, and `--fps`.
- Write `runtime/videos/<post_id>/video.mp4` and `runtime/videos/<post_id>/video_metadata.json` atomically.
- Add minimal `imageio` and `imageio-ffmpeg` dependencies for MP4 writing without requiring system ffmpeg.
- Add no-network tests using a fake video writer.
- Document the local video export command and outputs.

## Out of scope

- Publishing or upload APIs.
- Scheduling.
- AI generation.
- Text-to-speech, audio, or subtitles.
- Animations.
- Dashboard changes.
- Media compositing.
- Database changes.
- Cloud storage.
- Committed runtime video files.

## Regression tests

- Missing manifest returns exit code 1.
- Invalid JSON and invalid manifest shapes return exit code 1.
- Empty render manifests produce a zero summary.
- Ready renders export video and metadata with a fake writer.
- Not-ready renders are skipped by default.
- `--include-not-ready` includes not-ready renders but marks them not ready for upload.
- Missing `post_id`, missing `card_path`, and missing card files are skipped with errors.
- Existing videos are skipped unless `--overwrite` is passed.
- `--dry-run` creates no directories or files.
- Metadata and video writes use temporary files and atomic replace.
- Temporary video files are cleaned up on writer failure.
- CLI summary JSON is printed.

## CI/CD checks

- `python -m compileall app tests scripts`
- `python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- `python -m pytest -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- `python scripts\build_render_manifest.py`
- `python scripts\export_card_videos.py --overwrite`
- `dir runtime\videos\2057499359705813029`
- `start runtime\videos\2057499359705813029\video.mp4`

## Senior review notes

- Risk assessment: low, because this is a local-only exporter that reads the existing render manifest and writes ignored runtime artifacts.
- Regression confidence: high for control flow and metadata because tests inject a fake writer and cover skip/error paths.
- Follow-ups: add real platform upload/publishing in a separate ticket only after local video artifacts are stable.

## Rollback notes

- Revert strategy: remove the exporter script, tests, docs, dependency additions, and README link.
- Data/runtime impact: generated `runtime/videos/` artifacts are ignored and can be deleted safely.
