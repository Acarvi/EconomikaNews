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

## Implementation Notes

- X is the primary product source: configured Spanish liberal/economy/politics accounts are scanned for viral tweets.
- Twikit remains the current primary implementation, but it is fragile because private X schema changes can trigger `KEY_BYTE`, `urls` or `indices` failures.
- `services.discovery.x_sources.TwikitXSource` now centralizes Twikit error classification, scoring and tweet normalization helpers so the implementation can be replaced incrementally.
- `BrowserXSource` is an experimental fallback adapter. It can parse status links from X profile HTML and is selected only with `ECONOMIKA_X_SOURCE=browser` or after Twikit schema degradation with `ECONOMIKA_X_SOURCE=auto`.
- `BrowserXSource` now performs real browser/profile extraction and can reuse local cookies or a local user-data profile when available.
- RSS/news remains secondary and explicit. It is not the default product discovery source.
- X debug dumps are opt-in with `ECONOMIKA_DEBUG_X=true` and go under ignored `debug/`.
- Existing tests continue to pass.

## Validation Commands

```bash
pytest -q tests/test_viral_scout_resilience.py
pytest -q
```

