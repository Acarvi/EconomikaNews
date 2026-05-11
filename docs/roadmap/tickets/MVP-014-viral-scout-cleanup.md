# MVP-014 Viral Scout Cleanup

## Goal

Split discovery from scoring, logging and fallback handling inside the Viral Scout path.

## Why

Current Viral Scout behavior is hard to reason about because one class manages cookies, Twikit calls, Nitter, RSS, scores, history and verbose progress logs. Cleanup will make failure behavior predictable.

## Scope

- Move scoring into a separate helper.
- Move fallback selection into discovery orchestration.
- Keep history checks explicit.
- Remove hard dependency on Twikit success.
- Make logs concise and source-scoped.

## Non-goals

- Removing all legacy code.
- Changing scoring thresholds beyond what tests require.
- Fixing X private API behavior.

## Implementation Steps

1. Identify the minimal compatibility surface used by `main.py` and `server.py`.
2. Extract score calculation for X and RSS candidates.
3. Normalize warning messages for Twikit/Nitter failures.
4. Ensure no-source/no-result paths fall through to RSS.
5. Add tests for Twikit recoverable errors and RSS fallback.

## Acceptance Criteria

- A recoverable Twikit error does not abort discovery.
- Nitter no-entry/403/DNS failures produce one concise warning per source/account.
- RSS fallback remains available.
- Existing tests continue to pass.

## Validation Commands

```bash
pytest -q tests/test_viral_scout_resilience.py
pytest -q
```

