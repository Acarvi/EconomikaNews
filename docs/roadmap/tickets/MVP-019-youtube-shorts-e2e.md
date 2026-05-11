# MVP-019 YouTube Shorts E2E

## Goal

Validate YouTube Shorts publishing through CentralPublishingHub.

## Why

YouTube is one of the required MVP targets, but OAuth/token handling and target mapping should live in the Hub, not in the GUI.

## Scope

- Send `youtube_shorts` target through Hub.
- Validate OAuth/token prerequisites.
- Record Hub response fields needed by EconomikaNoticias.
- Keep local `core/youtube_uploader.py` as legacy until Hub path is proven.

## Non-goals

- Direct YouTube upload from EconomikaNoticias.
- Token migration in this ticket unless Hub requires it.
- Scheduling.

## Implementation Steps

1. Confirm Hub supports `youtube_shorts`.
2. Run dry-run/mock publish with `youtube_shorts`.
3. Run one real publish with a test or approved account.
4. Record expected success/error payloads.
5. Add tests for target preservation in publish payload.

## Acceptance Criteria

- Hub accepts a `youtube_shorts` target.
- A real or approved mock publish returns a target-level result.
- OAuth/token errors are clear and do not crash the GUI.

## Validation Commands

```bash
pytest -q tests/test_publisher_hub_contract.py
pytest -q
```

