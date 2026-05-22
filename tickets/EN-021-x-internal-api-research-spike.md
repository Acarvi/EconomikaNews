# EN-021 X internal API research spike

## Objective

Prototype a free backend-style X ingestion research provider using X internal web API calls with manually supplied session credentials from environment variables.

## Scope

- Add an experimental `XInternalApiProvider` implementing the EN-020 ingestion provider contract.
- Build env-based headers for internal X API requests without printing secrets.
- Add redaction helpers for tokens, cookies, and bearer values.
- Add best-effort normalization for known tweet-like JSON structures.
- Add a one-account probe script for local manual research.
- Document DevTools capture workflow, failure modes, and safety constraints.
- Add no-network tests.

## Out of scope

- Browser automation.
- Playwright.
- Real scheduled scanning.
- 500-account ingestion.
- SQLite, dashboard, rendering, or publishing.
- Captcha/challenge bypass.
- Committed cookies, tokens, auth headers, or raw debug payloads.

## Acceptance criteria

- Missing endpoint or credentials returns an `IngestionResult` with clear errors instead of crashing.
- HTTP `401`, `403`, `429`, and challenge-like responses are classified clearly.
- Provider builds realistic headers from env vars.
- Secrets are redacted from debug/error output.
- Probe script prints normalized summaries only.
- Tests run without network access.

## Validation commands

```bash
python -m compileall app tests scripts
python -m pytest
```
