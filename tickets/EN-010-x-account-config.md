# EN-010 X Account Config

## Objective

Define the local account configuration needed for X ingestion without committing credentials, cookies, tokens, or browser profile data.

## Scope

- Keep X authentication state inside ignored local runtime artifacts.
- Document the manual login command in the README.
- Preserve account-specific secrets outside version control.

## Out of Scope

- Tweet extraction.
- Metrics extraction.
- Media extraction.
- SQLite persistence.
- Dashboard, rendering, AI, or publishing workflows.

## Acceptance Criteria

- `runtime/` remains ignored by git.
- The X browser profile is stored under `runtime/browser_profile`.
- No committed cookies, tokens, or account credentials are introduced.
- Manual login can be initiated with:

```bash
python -m app.discovery.x_browser_source --login
```

## Validation Commands

```bash
python -m compileall app tests
python -m pytest
```
