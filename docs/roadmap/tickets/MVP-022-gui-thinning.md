# MVP-022 GUI Thinning

## Goal

Reduce `main.py` by moving workflow logic behind stable orchestration wrappers.

## Why

`main.py` currently owns UI, discovery, AI, render, review, publishing, threading and cloud sync concerns. This makes small changes risky.

## Scope

- Add orchestration functions/classes used by GUI callbacks.
- Move one panel/workflow at a time.
- Keep Tkinter visuals mostly unchanged.
- Preserve current launch behavior.

## Non-goals

- Rebuilding the GUI.
- Changing visual design.
- Moving every function in one PR.

## Implementation Steps

1. List GUI callbacks and the workflow they invoke.
2. Move manual/RSS processing behind orchestration after discovery contract lands.
3. Move AI/render/publish sequences behind use-case wrappers.
4. Keep compatibility shims where widgets still expect legacy dicts.
5. Add focused tests for orchestration wrappers.

## Acceptance Criteria

- `main.py` has fewer direct calls into low-level modules.
- GUI workflows still run.
- No broad visual changes are included.

## Validation Commands

```bash
pytest -q
```

