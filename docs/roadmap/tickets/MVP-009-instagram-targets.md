# MVP-009 - Instagram Targets

## Goal

Ensure CentralPublishingHub supports:

- `instagram_reel`
- `instagram_story`
- `instagram_feed`

## Current State

EconomikaNoticias has direct helpers for Reels and Stories. CentralPublishingHub advertises Instagram Reels/Stories and central publishing support, but Feed/Post format support needs explicit contract validation.

## Proposed Change

Route Instagram publication through CentralPublishingHub and define per-target format rules.

## Files Likely Affected

- `services/publishing_hub_client.py`
- `core/publisher.py`
- CentralPublishingHub router/publisher code
- docs/tests

## Implementation Steps

1. Define target names exactly.
2. Validate vertical video for Reels and Stories.
3. Define Feed/Post allowed media shapes and duration constraints.
4. Return per-target results.
5. Add tests for target normalization.

## Acceptance Criteria

- `instagram_reel`, `instagram_story`, and `instagram_feed` are accepted targets.
- Invalid media format returns a clear error per target.
- EconomikaNoticias does not need Instagram credentials.

## Manual Test Plan

Submit one vertical video to Reels and Stories, then test Feed/Post only when the format is valid.

## Risks

Instagram Graph API requirements differ between Reels, Stories, and Feed.

## Out of Scope

Facebook publication.

