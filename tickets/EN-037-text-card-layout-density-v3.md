# EN-037 Text Card Layout Density V3

## Objective

Improve text-card layout density so generated static PNG cards use vertical space more intentionally and look closer to publishable vertical social/news assets while preserving the render input contract, CLI, output path, and manifest compatibility.

## Scope

- Update `scripts/render_text_cards.py` to better distribute content across the default `1080x1920` card.
- Add deterministic lower information sections using existing render input fields only.
- Add `POST SIGNAL`, `WHY THIS SURFACED`, source signal rows with compact metrics, and an approved editorial status chip when review status is available.
- Preserve static PNG output under `runtime/renders/<post_id>/card.png`.
- Preserve EN-036 branding, badge logic, compact metric formatting, clean footer, and body deduplication behavior.
- Add/update no-network tests for the new deterministic helper behavior.
- Update renderer documentation for the visual v3 layout.

## Out of scope

- Video rendering.
- ffmpeg/moviepy.
- AI generation.
- Text rewriting.
- External API calls.
- Publishing.
- Scheduling.
- Dashboard changes.
- Media compositing.
- Downloading media.
- Database changes.
- Cloud storage.
- Committed runtime render files.
- Bundled fonts or font files.

## Regression tests

- Valid render input still creates a PNG with the requested dimensions.
- Existing cards are skipped when `--overwrite` is not set.
- Existing cards are rewritten when `--overwrite` is set.
- `--dry-run` creates no render files or directories.
- `render.ready: false` inputs are skipped without errors.
- Invalid JSON is recorded and does not stop later processing.
- Long headline/body content renders without crashing.
- `media.has_media` inputs still render.
- Compact number formatting remains covered.
- Badge inference remains covered.
- Footer helper behavior remains covered.
- `build_surface_reasons` covers high views, high reposts, high replies, strong likes, and fallback editorial candidate labels.
- `build_signal_rows` covers account, source, score, compact metrics, media, review status, and post ID fields when available.

## CI/CD checks

- `python -m compileall app tests scripts`
- `python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- `python -m pytest -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- Run `python scripts\render_text_cards.py --overwrite`.
- Run `python scripts\build_render_manifest.py`.
- Open a generated card such as `runtime\renders\2057499359705813029\card.png`.
- Confirm the card keeps top branding and headline hierarchy while using the lower half for metric chips, deterministic surfaced labels, source signal rows, approved status, and a clean footer.

## Senior review notes

- Risk assessment: Low to medium. The change is still local to static PNG layout, but tighter vertical positioning must tolerate long text and small test dimensions.
- Regression confidence: Renderer behavior tests protect core CLI/output behavior, and helper tests protect deterministic label/row generation.
- Follow-ups: Future tickets can add media compositing or video output without changing this ticket's render input contract.

## Rollback notes

- Revert strategy: Revert the renderer, tests, docs, and ticket changes from this branch.
- Data/runtime impact: No database or persistent runtime data changes. Generated `runtime/renders/` artifacts remain untracked and can be deleted/regenerated.
