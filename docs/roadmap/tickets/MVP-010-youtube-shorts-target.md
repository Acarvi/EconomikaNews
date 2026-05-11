# MVP-010 - YouTube Shorts Target

## Goal

Ensure CentralPublishingHub supports `youtube_shorts`.

## Current State

EconomikaNoticias has direct YouTube upload code. CentralPublishingHub also contains YouTube uploader code and should own OAuth/token handling.

## Proposed Change

EconomikaNoticias sends title, caption/description, media, account, and `youtube_shorts` target to the hub.

## Files Likely Affected

- `core/youtube_uploader.py` in EconomikaNoticias for deprecation/fallback
- `services/publishing_hub_client.py`
- CentralPublishingHub YouTube uploader/router code

## Implementation Steps

1. Move default YouTube upload path to hub.
2. Enforce title length <= 100.
3. Ensure `#Shorts` is present in title or description.
4. Validate vertical/square format and duration.
5. Return YouTube external id and URL in hub result.

## Acceptance Criteria

- EconomikaNoticias does not need YouTube OAuth secrets for the primary path.
- Hub handles token refresh and upload.
- Invalid title/duration/aspect returns clear target error.

## Manual Test Plan

Publish one valid vertical video through hub to YouTube Shorts sandbox/test account.

## Risks

YouTube upload quota and channel verification can block real publishing.

## Out of Scope

Channel management UI.

