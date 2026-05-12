# MVP-020 Instagram Reel Story E2E

## Goal

Validate Instagram Reel and Instagram Story publishing through CentralPublishingHub.

## Why

Instagram Reel and Story are required MVP targets. Meta constraints and media processing should be handled by the Hub.

## Scope

- Send `instagram_reel` and `instagram_story` in the same publish intent when selected.
- Confirm Hub target-level results.
- Mark `instagram_feed` as planned / `NOT_IMPLEMENTED` until implemented.
- Document required Meta credentials and account constraints.

## Non-goals

- Direct Graph API publishing from EconomikaNoticias.
- Facebook Reels.
- Feed/Post implementation unless already supported by Hub.

## Implementation Steps

1. Confirm Hub supports `instagram_reel` and `instagram_story`.
2. Run dry-run/mock publish.
3. Run one real Reel and one real Story publish with an approved account.
4. Capture target-level result shape.
5. Ensure unsupported `instagram_feed` returns a clear planned/not implemented result.

## Acceptance Criteria

- Reel and Story targets are accepted by Hub.
- Target-level success/failure is visible to the user.
- Feed/Post unsupported state is explicit and non-fatal.

## Validation Commands

```bash
pytest -q tests/test_platform_normalization.py tests/test_publisher_hub_contract.py
pytest -q
```

