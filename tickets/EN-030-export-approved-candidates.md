# EN-030 Export Approved Candidates

Add an export step so dashboard-approved candidates can move toward the
production queue, while keeping rendering and publishing out of scope.

## Scope

- Add `scripts/export_approved_candidates.py`.
- Read candidates from `runtime/outputs/x_candidates.json`.
- Read review state from `runtime/economika_news.db`.
- Export only candidates with review status `approved`.
- Enrich exported candidates with review metadata.
- Keep source candidates JSON read-only.
- Add no-network tests.
- Update docs.

## Out of Scope

- Rendering
- Publishing
- Scheduling
- AI caption/title generation
- Editing
- CentralPublishingHub integration
- Queue processor
- Media download changes
- Committed runtime/secrets/db/output files
