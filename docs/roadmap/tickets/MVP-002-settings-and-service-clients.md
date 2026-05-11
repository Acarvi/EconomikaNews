# MVP-002 - Settings And Service Clients

## Goal

Create explicit configuration and HTTP clients for CentralAIService and CentralPublishingHub.

## Current State

`core/ai_handler.py` uses `CENTRAL_AI_URL`. `core/publisher.py` uses `CENTRAL_PUBLISHING_HUB_URL`. `utils/network.py` includes auto-start behavior through sibling paths.

## Proposed Change

Add central settings and clients:

- `CENTRAL_AI_SERVICE_URL=http://localhost:8080`
- `CENTRAL_PUBLISHING_HUB_URL=http://localhost:8000`
- `ECONOMIKA_ADMIN_API_KEY=...`
- `ECONOMIKA_ACCOUNT_ID=economika`

New files:

- `services/central_ai_client.py`
- `services/publishing_hub_client.py`

## Files Likely Affected

- `core/ai_handler.py`
- `core/publisher.py`
- `utils/network.py`
- `requirements.txt`
- `docs/DEVELOPER.md`

## Implementation Steps

1. Add settings helper with defaults and legacy env aliases.
2. Implement CentralAIService health/draft/refine methods.
3. Implement CentralPublishingHub health/publish/schedule/queue methods.
4. Add request timeout and clear exception types.
5. Replace direct request construction in wrappers gradually.

## Acceptance Criteria

- No code needs `../CentralAIService` or `../CentralPublishingHub`.
- Service URLs are visible in one settings path.
- Clients are testable with mocked HTTP.
- Existing wrappers keep backward-compatible function signatures.

## Manual Test Plan

Set local URLs in `.env`, run health checks, and confirm both clients report service status.

## Risks

Changing env var names can break existing local setups unless aliases are supported.

## Out of Scope

Changing the hub implementations themselves.

## Implementation Notes

- Added `config/settings.py` with explicit environment-backed settings for CentralAIService, CentralPublishingHub, optional `ECONOMIKA_ADMIN_API_KEY`, and `ECONOMIKA_ACCOUNT_ID`.
- Added `services/central_ai_client.py` for `/health`, `/v1/analyzer/draft`, and `/v1/analyzer/refine` using `requests` with timeouts.
- Added `services/publishing_hub_client.py` for `/health`, `/api/v1/publish`, `/api/v1/schedule`, and `/api/v1/queue`, including `X-API-Key` when configured and base URL normalization to avoid duplicated `/api/v1`.
- Added mocked client/settings tests; no real network calls are made by the new test coverage.

