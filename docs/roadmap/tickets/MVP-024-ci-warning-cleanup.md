# MVP-024 CI Warning Cleanup

## Goal

Reduce CI/local test warning noise and tighten regression feedback.

## Why

Warnings can hide real regressions. The suite already exists, so the next step is making failures and warnings easier to interpret.

## Scope

- Review `pytest -q` warnings.
- Fix low-risk deprecations.
- Add warning filters only when fixing upstream noise is not practical.
- Keep CI dependencies aligned with what tests import.

## Non-goals

- Large dependency upgrades.
- GUI automation.
- Live platform API calls in default CI.

## Implementation Steps

1. Capture current local warning output.
2. Classify warnings by source.
3. Fix project-owned warnings first.
4. Add targeted pytest filters for third-party warnings if needed.
5. Confirm CI still compiles `server.py` and `core/publisher.py`.

## Acceptance Criteria

- `pytest -q` output is materially quieter.
- Any remaining warnings are documented or intentional.
- CI remains green.

## Validation Commands

```bash
pytest -q
```

