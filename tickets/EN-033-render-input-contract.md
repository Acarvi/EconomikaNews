# EN-033 Render Input Contract

## Objective

Add a render input contract generator that converts approved bundle index entries into stable JSON files for a future renderer.

## Scope

- Add `scripts/build_render_inputs.py`.
- Read `runtime/approved/index.json`.
- Write one deterministic `runtime/render_inputs/<post_id>.json` file per included bundle.
- Include only `ready_for_render: true` bundles by default.
- Support `--include-not-ready`, `--overwrite`, and `--dry-run`.
- Add no-network tests for valid, invalid, skipped, dry-run, overwrite, and atomic-write behavior.
- Document the render input contract and link it from the README.

## Out of scope

- Actual image or video rendering.
- ffmpeg, moviepy, or PIL generation.
- Text-to-speech.
- AI generation.
- Publishing.
- Scheduling.
- Dashboard changes.
- Media downloading changes.
- Database changes.
- Cloud storage.
- Committed runtime render input files.

## Regression tests

- Missing index file exits with code `1`.
- Invalid JSON exits with code `1`.
- Invalid top-level JSON shapes exit with code `1`.
- Empty bundle list returns a zero summary.
- Ready bundle writes a render input.
- Not-ready bundle is skipped by default.
- `--include-not-ready` writes a render input with `render.ready: false` and notes.
- Existing output is skipped when `--overwrite` is false.
- `--overwrite` rewrites an existing file.
- `--dry-run` creates no directories or files.
- Invalid individual bundle without `post_id` is skipped with an error.
- Headline generation is deterministic from `text_prefix`.
- Missing or blank text uses `Untitled`.
- Media files are copied from the index bundle.
- Atomic write uses a temporary file and replace.

## CI/CD checks

- `python -m compileall app tests scripts`
- `python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp=%TEMP%\economika-pytest-tmp`
- `python -m pytest -p no:cacheprovider --basetemp=%TEMP%\economika-pytest-tmp`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- Run the render input builder against a temporary index file.
- Confirm generated JSON schema fields match `docs/render_input_contract.md`.
- Confirm `runtime/render_inputs/` files are ignored and not tracked.

## Senior review notes

- Risk assessment: Low. The new script reads an index and writes runtime JSON only; it does not mutate bundle metadata or call network/rendering libraries.
- Regression confidence: High. Tests cover CLI failure modes, helper behavior, write safety, and deterministic output shape.
- Follow-ups: Implement the renderer in a separate ticket once the input contract is accepted.

## Rollback notes

- Revert strategy: Revert this ticket's script, tests, docs, and README link.
- Data/runtime impact: Generated `runtime/render_inputs/` files are disposable runtime artifacts and can be deleted.
