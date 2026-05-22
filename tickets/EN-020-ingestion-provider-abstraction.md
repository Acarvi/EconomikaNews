# EN-020 Ingestion provider abstraction

## Objective

Add a normalized ingestion provider abstraction so EconomikaNews can support multiple X ingestion strategies without coupling downstream product code to vendor-specific payloads.

## Scope

- Add normalized ingestion models for source accounts, media, engagement metrics, source posts, and ingestion results.
- Add an `IngestionProvider` Protocol for fetching recent posts.
- Add a deterministic fake provider for tests and local development.
- Document the architecture decision in ADR 0003.
- Update the README with the current ingestion direction.

## Out of scope

- Real X scraping.
- Playwright/browser automation.
- X internal API implementation.
- HTTP clients.
- Paid provider integrations.
- Scheduler integration.
- SQLite persistence.
- Dashboard, scoring, rendering, or publishing changes.

## Acceptance criteria

- `app.ingestion` exposes normalized models, the provider Protocol, and the fake provider.
- The fake provider performs no network access.
- The fake provider returns an `IngestionResult` with exactly two stable sample posts.
- The fake provider includes at least one image media item and one video media item.
- Tests import the ingestion package and validate the fake provider behavior.
- README and ADR describe browser automation as diagnostic/fallback rather than the core ingestion architecture.

## Validation commands

```bash
python -m compileall app tests
python -m pytest
```
