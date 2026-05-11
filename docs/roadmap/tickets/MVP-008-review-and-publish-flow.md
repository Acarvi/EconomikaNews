# MVP-008 - Review And Publish Flow

## Goal

Connect manual review to CentralPublishingHub submission and local state updates.

## Current State

The Tkinter review UI allows editing and selected publishing actions, but state and publishing are coupled to current `core.publisher` behavior.

## Proposed Change

Review item fields should map to a structured post draft, selected targets, publish mode, and hub request.

## Files Likely Affected

- `main.py`
- `core/publisher.py`
- `services/publishing_hub_client.py`
- SQLite store from MVP-006

## Implementation Steps

1. Ensure UI edits update the draft object.
2. Add target selection for Instagram Reel, Story, Feed/Post, and YouTube Shorts.
3. Add publish now and schedule paths.
4. Send payload to CentralPublishingHub.
5. Store hub result locally.

## Acceptance Criteria

- Operator can edit headline/caption/title before publishing.
- Operator can select one or more MVP targets.
- Publish result is stored locally.
- Hub errors are visible and non-destructive to the draft.

## Manual Test Plan

Create one draft, edit text, select Instagram Reel and YouTube Shorts, publish to mocked hub, and verify local status.

## Risks

The current UI has legacy platform labels, including Facebook.

## Out of Scope

Full UI redesign or multi-user review.

