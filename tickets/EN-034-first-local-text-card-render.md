# EN-034 First Local Text-Card Render

## Objective

Add the first local static PNG renderer that converts ready render input JSON files into simple text-card PNGs under `runtime/renders/<post_id>/card.png`.

## Scope

- Add `scripts/render_text_cards.py`.
- Read direct JSON files from `runtime/render_inputs` by default.
- Validate schema version, `post_id`, and `render.ready`.
- Render deterministic vertical PNG news cards with Pillow.
- Skip not-ready, invalid, and existing outputs while continuing through later files.
- Support overwrite, dry-run, dimensions, background, and limit CLI options.
- Print a JSON summary to stdout.
- Add no-network tests for rendering, skipping, invalid input, dry-run, overwrite, and atomic writes.
- Document local usage in `docs/text_card_renderer.md` and link it from the README.

## Out of scope

- Video rendering.
- ffmpeg or moviepy.
- Text-to-speech.
- AI generation.
- Publishing.
- Scheduling.
- Dashboard changes.
- Media downloading changes.
- Database changes.
- Cloud storage.
- Media compositing.
- Committed runtime render files.
- Face, person, or image generation.

## Regression tests

- Missing and empty input directories return zero summaries.
- Invalid JSON and invalid top-level JSON are recorded without crashing.
- Missing `post_id` and `render.ready: false` inputs are skipped.
- A valid render input creates a non-empty PNG with expected dimensions.
- Existing cards are skipped unless `--overwrite` is set.
- Dry-run creates no directories or files.
- Long headline/body content does not crash rendering.
- Media metadata adds a label path without media compositing.
- CLI prints summary JSON.
- Atomic PNG writes use a temp PNG followed by `os.replace`.

## CI/CD checks

- `python -m compileall app tests scripts`
- `python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- `python -m pytest -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- Run `python scripts\render_text_cards.py`.
- Run `dir runtime\renders`.
- Open a generated `runtime\renders\<post_id>\card.png` locally.

## Senior review notes

- Risk assessment: low; the renderer is local-only and does not touch ingestion, dashboard, publishing, scheduling, or databases.
- Regression confidence: covered by no-network unit tests and summary validation.
- Follow-ups: add media compositing or video rendering only in later scoped tickets.

## Rollback notes

- Revert the renderer script, tests, docs, README entry, ticket, and Pillow dependency.
- Data/runtime impact: generated `runtime/renders/` artifacts are ignored local files and can be deleted without repository impact.
