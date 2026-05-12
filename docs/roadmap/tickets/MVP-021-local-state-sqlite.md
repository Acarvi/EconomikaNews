# MVP-021 Local State SQLite

## Goal

Introduce SQLite-backed local state for candidates, review decisions, render artifacts and publish attempts.

## Why

Current JSON files are simple but scattered. SQLite will make restart/retry behavior easier without moving the app to cloud.

## Scope

- Add `storage/sqlite_store.py`.
- Store candidate lifecycle state.
- Store review decisions and edits.
- Store render artifact paths.
- Store publish intent attempts and results.

## Non-goals

- Cloud database.
- Multi-user sync.
- Deleting all JSON files immediately.

## Implementation Steps

1. Define minimal schema.
2. Add store initialization and migrations.
3. Add repository functions for candidate/review/render/publish status.
4. Keep JSON history compatibility during transition.
5. Add tests with temporary SQLite database.

## Acceptance Criteria

- App can persist and reload candidate/review/render/publish status.
- Tests do not write to production data paths.
- JSON files remain readable until migration is complete.

## Validation Commands

```bash
pytest -q
```

