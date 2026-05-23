# EN-029 Dashboard Review State

Add a minimal local human-review layer to the existing candidate dashboard so
candidate posts can move from raw discovery into reviewed candidates without
changing the source candidate JSON.

## Scope

- Add SQLite-backed review-state storage at `runtime/economika_news.db`.
- Add approve, reject, and reset-to-pending actions in the local dashboard.
- Show review status and summary counts in the dashboard.
- Add filters for `pending`, `approved`, `rejected`, and `all`.
- Keep the dashboard local-only and simple.
- Add no-network tests.

## Out of Scope

- Rendering
- Publishing
- Scheduling
- Caption or title generation
- Editing
- Authentication
- Queue
- CentralPublishingHub integration
- Committed runtime files
