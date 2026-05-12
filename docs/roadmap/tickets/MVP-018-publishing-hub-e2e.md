# MVP-018 Publishing Hub E2E

## Goal

Validate the EconomikaNoticias -> CentralPublishingHub contract with `video_path`.

## Why

EconomikaNoticias should send publish intents only. CentralPublishingHub should own temporary hosting and platform-specific APIs.

## Scope

- Confirm active payload shape:

```json
{
  "account_id": "economika",
  "video_path": "...",
  "caption": "...",
  "title": "...",
  "targets": ["youtube_shorts", "instagram_reel", "instagram_story"],
  "publish_mode": "now"
}
```

- Validate `/api/v1/publish` and health checks.
- Keep compatibility fields only if Hub still needs them.
- Ensure EconomikaNoticias does not use Catbox/Gofile/Uguu in the active path.

## Non-goals

- Implementing platform-specific publishing in EconomikaNoticias.
- Universal scheduling.
- Removing legacy helpers if tests still depend on them.

## Implementation Steps

1. Add a Hub dry-run/manual validation script or test helper if available.
2. Exercise `PublishingHubClient.publish(...)` with a mocked Hub.
3. Confirm payload target normalization.
4. Confirm failure is recorded as a local failed intent without attempting local hosting.
5. Update manual checklist with observed Hub behavior.

## Acceptance Criteria

- One approved render sends one publish intent to Hub.
- Payload contains normalized targets.
- Hub errors are visible and retryable.
- No local temporary host is used in the active publish path.

## Validation Commands

```bash
pytest -q tests/test_publisher_hub_contract.py tests/test_publisher_payloads.py
pytest -q
```

