# EN-011 Playwright Persistent Browser Profile

## Objective

Add the foundation for a headed Playwright Chromium session that uses a persistent local browser profile for manual X login.

## Scope

- Add Playwright as a project dependency.
- Add runtime path defaults for `runtime/browser_profile` and `runtime/debug`.
- Add a manual CLI command that opens `https://x.com/home` in a headed persistent Chromium context.
- Allow the operator to finish by closing the browser or pressing Enter.
- Save a best-effort debug screenshot to `runtime/debug/x_home.png`.
- Add tests for imports, default paths, and runtime directory creation without launching a browser in CI.

## Out of Scope

- Tweet extraction.
- Metrics extraction.
- Media extraction.
- SQLite persistence.
- Dashboard, rendering, AI, or publishing workflows.
- Committed cookies, tokens, or browser profile data.

## Acceptance Criteria

- `python -m app.discovery.x_browser_source --login` creates runtime directories and launches the manual login browser.
- Tests do not launch Chromium.
- Runtime artifacts stay ignored by git.

## Validation Commands

```bash
python -m compileall app tests
python -m pytest
```

## Outcome / Current finding

- Playwright isolated profiles can hit X login loops.
- Reusing a real profile may require shutting down the browser because of profile locks.
- Therefore this remains a fallback and diagnostic foundation, not the required daily workflow.
