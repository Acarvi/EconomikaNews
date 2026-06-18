# EN-035 Render Manifest

## Objective

Add a local render manifest builder so future publishing and video stages can consume a stable list of generated render artifacts instead of scanning `runtime/renders/` directly.

## Scope

- Add `scripts/build_render_manifest.py`.
- Scan direct child render directories for `card.png`.
- Link each card to `runtime/render_inputs/<post_id>.json` when present.
- Read PNG dimensions and file size with Pillow.
- Write `runtime/renders/manifest.json` atomically.
- Report invalid render counts and optional invalid render details.
- Add no-network tests using `tmp_path` and generated PNGs.
- Document usage and ready-for-publish rules.

## Out of scope

- Publishing.
- Video rendering.
- ffmpeg or moviepy.
- AI generation.
- Scheduling.
- Dashboard changes.
- Media compositing.
- Image redesign.
- Database changes.
- Cloud storage.
- Committed runtime render files.

## Regression tests

- Missing render directory creates an empty manifest and exits zero.
- Empty render directory creates an empty manifest.
- Valid card plus matching render input creates a ready manifest entry.
- Missing and unreadable cards are counted invalid.
- Missing render input, post ID mismatch, and `render.ready: false` keep entries but mark them not ready.
- Dimensions and file size are captured.
- Direct files inside the render directory, including `manifest.json`, are ignored.
- `--include-invalid` controls invalid render details.
- Manifest writes use a temporary file and atomic replace.
- CLI prints summary JSON.

## CI/CD checks

- `python -m compileall app tests scripts`
- `python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp=runtime/pytest-tmp`
- `python -m pytest -q tests`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- Run `python scripts\build_render_manifest.py` after rendering local cards.
- Confirm `runtime/renders/manifest.json` is created locally and remains untracked.

## Senior review notes

- Risk assessment: Low. The change is isolated to local manifest generation and reads existing runtime artifacts.
- Regression confidence: High after unit coverage for happy path, invalid renders, not-ready metadata, CLI summary, and atomic writes.
- Follow-ups: Future tickets can consume `manifest.json` for publishing or video stages.

## Rollback notes

- Revert strategy: Revert this ticket's script, tests, docs, README entry, and ticket file.
- Data/runtime impact: Remove any local `runtime/renders/manifest.json` generated during validation.
