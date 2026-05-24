# EN-032 Approved Bundle Index

## Objective

Add a stable approved bundle index so future rendering and publishing stages can consume `runtime/approved/index.json` instead of scanning bundle folders ad hoc.

## Scope

- Add `scripts/build_approved_bundle_index.py`.
- Read direct child bundle folders from `runtime/approved`.
- Validate each bundle `metadata.json`.
- Write `runtime/approved/index.json` atomically.
- Report invalid bundle counts and optional invalid bundle details.
- Add no-network tests covering valid, invalid, sorting, media normalization, CLI, and atomic write behavior.
- Update approved media bundle docs and README local pipeline commands.

## Out of scope

- Rendering.
- Publishing.
- Scheduling.
- AI generation.
- Dashboard changes.
- Media downloading changes.
- Database schema changes.
- Cloud storage.
- Committed runtime media, outputs, database files, or generated index files.

## Regression tests

- Missing bundles directory creates an empty index and exits `0`.
- Empty bundles directory creates an empty index.
- Valid metadata creates one index bundle.
- Bundles sort by score descending, `reviewed_at` descending, and `post_id` ascending.
- Missing metadata, invalid JSON, missing `post_id`, and non-approved `review_status` are counted invalid and excluded.
- Downloaded and `skipped_existing` local media entries are normalized into `media_files`.
- Failed and unsupported local media entries are excluded from `media_files`.
- Bundles with `bundle_errors` remain indexed but are not `ready_for_render`.
- Index writes use `index.json.tmp -> index.json`.
- Output parent directories are created.
- CLI summary is printed.

## CI/CD checks

- `python -m compileall app tests scripts`
- `python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- `python -m pytest -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- Run the index builder against a temp `runtime/approved` equivalent.
- Confirm missing bundle directories produce an empty index and exit `0`.
- Confirm invalid bundle folders do not block valid bundles.
- Confirm no generated `runtime/approved/index.json` file is tracked.

## Senior review notes

- Risk assessment: Low; the new script is read-only against bundle metadata until the final atomic index write.
- Regression confidence: High; behavior is covered by no-network temp directory tests.
- Follow-ups: Rendering and publishing stages can consume `runtime/approved/index.json` in later tickets.

## Rollback notes

- Revert strategy: Revert the script, tests, docs, and ticket.
- Data/runtime impact: Remove generated `runtime/approved/index.json` if created locally; approved bundle folders remain unchanged.
