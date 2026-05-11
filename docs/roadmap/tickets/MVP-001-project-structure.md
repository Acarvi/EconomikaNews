# MVP-001 - Project Structure

## Goal

Define a cleaner project structure for EconomikaNoticias without moving large files yet.

## Current State

`main.py` contains GUI, orchestration, review, and publishing actions. `server.py` overlaps with backend queue/publishing responsibilities. Service code is mixed into `core/`.

## Proposed Change

Plan a gradual structure where product app code, service clients, local state, and render pipeline have clear boundaries.

## Files Likely Affected

- `main.py`
- `server.py`
- `core/`
- `services/`
- `data/`
- `docs/DEVELOPER.md`

## Implementation Steps

1. Create `services/` for HTTP clients.
2. Create `state/` or `storage/` for SQLite store code.
3. Add small adapter modules before moving large GUI code.
4. Document deprecated paths.
5. Keep `main.py` as entry point during MVP.

## Acceptance Criteria

- A documented target structure exists.
- No large module move is required for MVP.
- New code has obvious ownership.
- Existing entry points continue working.

## Manual Test Plan

Run current GUI/CLI import path and confirm no module path changes are required.

## Risks

Premature file moves could break the current Tkinter flow and cloud server.

## Out of Scope

Moving `main.py` or rewriting the GUI.

