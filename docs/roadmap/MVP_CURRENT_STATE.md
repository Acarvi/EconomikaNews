# MVP Current State

## What Works

- Local Tkinter GUI starts from `main.py`.
- Root launcher `EconomikaNoticias.bat` starts the MVP without requiring users to find folders or run a generic script.
- `scripts/start_economika.ps1` checks Python, checks local service health, tries standard service folders, and then launches the GUI.
- Manual URLs are the reliable MVP path for controlled article/video creation.
- X Viral Scout remains the primary discovery direction for viral tweets from configured X accounts.
- RSS/news discovery is available as an explicit secondary fallback.
- CentralAIService and CentralPublishingHub clients are present and covered by lightweight smoke/contract tests.

## Experimental

- Twikit/X discovery depends on X behavior, cookies, and schema stability.
- BrowserXSource depends on local Playwright availability and browser automation compatibility.
- X discovery failures should be treated as recoverable discovery failures, not full-app failures.

## Missing

- Full production-grade X session management.
- Fully automated publish E2E validation against real social platforms.
- One-click installation of external service dependencies.
- CI coverage for Playwright browser execution. CI intentionally stays lightweight for now.

## How To Start

1. Double click `EconomikaNoticias.bat`.
2. The launcher checks Python.
3. The launcher checks CentralAIService at `http://localhost:8080/health`.
4. The launcher checks CentralPublishingHub at `http://localhost:8000/health`, `/docs`, or `/`.
5. The GUI opens through `python main.py`.

## How To Validate

Run:

```powershell
python -m py_compile server.py main.py core/viral_scout.py core/publisher.py services/discovery/x_sources.py
pytest -q
powershell -ExecutionPolicy Bypass -File .\scripts\diagnose_mvp.ps1
```

Service health warnings are acceptable when the local services are not running. Compile or test failures are not acceptable for MVP readiness.

## Required Services

- CentralAIService: `D:\Scripts\CentralAIService`, expected health endpoint `http://localhost:8080/health`.
- CentralPublishingHub: `D:\Scripts\CentralPublishingHub`, expected health endpoint `http://localhost:8000/health`, with `/docs` or `/` accepted as fallback.

## If X/Twikit Fails

- Keep using Manual URLs for the reliable MVP flow.
- Confirm X accounts and cookies are configured locally and are not committed to Git.
- Try `ECONOMIKA_X_SOURCE=auto` to allow fallback behavior.
- Treat schema, 403, 404, and lookup errors as recoverable discovery failures.

## If BrowserXSource Fails

- Confirm Playwright is installed in the local environment.
- Browser mode is local-only for now and is not required in CI.
- Use Twikit or Manual URLs while browser automation is unavailable.

