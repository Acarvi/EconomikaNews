# MVP-005 - Central Publishing Contract

## Goal

Make CentralPublishingHub the primary publication and scheduling path.

## Current State

`core/publisher.py` calls CentralPublishingHub but also contains direct Instagram Graph API helpers and temporary hosting. `server.py` also processes a publishing queue directly.

## Proposed Change

Turn `core/publisher.py` into an adapter/client for CentralPublishingHub. Move or deprecate direct Graph API behavior from EconomikaNoticias.

## Files Likely Affected

- `core/publisher.py`
- `server.py`
- `services/publishing_hub_client.py`
- tests for payload construction

## Implementation Steps

1. Add `publish` and `schedule` client methods.
2. Normalize `targets` to hub-compatible `platforms` if needed.
3. Include `account_id`, caption, title, media path or URL, publish mode, and scheduled time.
4. Store returned job id in local state once MVP-006 exists.
5. Keep direct fallback explicit and disabled by default.

## Acceptance Criteria

- Publishing path sends a single request to CentralPublishingHub.
- Graph API direct publishing is not the default path.
- Hub response status and target results are preserved.
- Platform names are normalized consistently.

## Manual Test Plan

Submit a mocked publish payload and confirm hub receives the expected request for Instagram and YouTube targets.

## Risks

CentralPublishingHub currently uses `platforms` and `shorts_title`, while target contract uses `targets` and `title`.

## Out of Scope

Implementing Instagram or YouTube API logic in EconomikaNoticias.

