# EN-036 Text Card Visual Design V2

## Objective

Improve the static PNG text-card visual design so generated cards feel like polished vertical social/news assets while preserving the existing render input contract, CLI, output path, and manifest compatibility.

## Scope

- Update `scripts/render_text_cards.py` visual layout for the default `1080x1920` card.
- Add clear `ECONOMIKA` branding, source context, deterministic badges, metric chips, compact metric formatting, and a cleaner footer.
- Keep body text conditional so duplicate headline/body content is not repeated.
- Preserve static PNG output under `runtime/renders/<post_id>/card.png`.
- Add/update no-network tests for PNG creation, overwrite behavior, dry-run behavior, skipped inputs, long text, media inputs, compact number formatting, badge inference, and footer identity helpers.
- Update documentation for the visual v2 layout and renderer scope.

## Out of scope

- Video rendering.
- ffmpeg/moviepy.
- AI generation.
- Text rewriting.
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
- Compact number formatting covers raw, thousands, and millions values.
- Badge inference covers `BREAKING`, X-sourced posts, and fallback `NEWS`.
- Footer helper handles X URLs, missing URLs, and account handles.

## CI/CD checks

- `python -m compileall app tests scripts`
- `python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- `python -m pytest -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- Run `python scripts\render_text_cards.py --overwrite`.
- Open a generated card such as `runtime\renders\2057499359705813029\card.png`.
- Confirm the card has top branding, badge, headline hierarchy, metric chips, and a footer that avoids full raw URLs.

## Senior review notes

- Risk assessment: Low to medium. The change is local to static PNG presentation, but text layout must continue to tolerate unusual input length and small test dimensions.
- Regression confidence: Covered by renderer behavior tests plus helper tests for deterministic formatting and labels.
- Follow-ups: Future tickets can add media compositing or video output without changing this ticket's render input contract.

## Rollback notes

- Revert strategy: Revert the renderer, tests, docs, and ticket changes from this branch.
- Data/runtime impact: No database or persistent runtime data changes. Generated `runtime/renders/` artifacts remain untracked and can be deleted/regenerated.
