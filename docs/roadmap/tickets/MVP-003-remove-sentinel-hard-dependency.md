# MVP-003 - Remove Sentinel Hard Dependency

## Goal

Ensure EconomikaNoticias imports, tests, pushes, and runs without SentinelAPI.

## Current State

`main.py` and `server.py` add `../SentinelAPI` to `sys.path` and attempt to import `bootstrap.activate_security`.

## Proposed Change

Make Sentinel optional behind:

```txt
ENABLE_SENTINEL=false
```

If disabled or unavailable, the app should continue without modifying `sys.path`.

## Files Likely Affected

- `main.py`
- `server.py`
- tests for import smoke coverage

## Implementation Steps

1. Add a small optional Sentinel bootstrap helper.
2. Default `ENABLE_SENTINEL` to false.
3. Remove unconditional sibling path insertion.
4. Add import tests with Sentinel absent from `sys.path`.
5. Keep warning logs concise and non-fatal when enabled but missing.

## Acceptance Criteria

- `python -m pytest` does not require `../SentinelAPI`.
- Importing `main.py` and `server.py` does not fail when SentinelAPI is absent.
- Sentinel can still be enabled explicitly for local security experiments.

## Manual Test Plan

Temporarily run with no Sentinel path and verify imports plus a server health check.

## Risks

Existing local users may assume Sentinel is active by default.

## Out of Scope

Changing SentinelAPI itself.

