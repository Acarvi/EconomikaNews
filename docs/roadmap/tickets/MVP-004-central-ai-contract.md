# MVP-004 - Central AI Contract

## Goal

Make CentralAIService the primary AI path for EconomikaNoticias drafts and refinements.

## Current State

`core/ai_handler.py` calls CentralAIService but uses a prompt-heavy compatibility shape and returns a tuple. Current CentralAIService expects `video_path`, `global_comments`, and `custom_prompt` for `/v1/analyzer/draft`.

## Proposed Change

Introduce a structured client and adapter for the target draft/refine contract. Keep `generate_content_ai(...)` as a wrapper until the GUI is migrated.

## Files Likely Affected

- `core/ai_handler.py`
- `services/central_ai_client.py`
- tests for parsing and fallback behavior

## Implementation Steps

1. Define `DraftRequest` and `DraftResponse` shapes in client code.
2. Map current tweet/media data into target payload.
3. Parse `headline`, `caption`, `youtube_title`, `caption_b`, `source`, and segment timestamps.
4. Preserve tuple output for legacy callers.
5. Add optional local fallback only behind explicit config.

## Acceptance Criteria

- CentralAIService is the default path.
- Missing hub returns a clear error state, not a traceback.
- Draft response parsing is covered by tests.
- `youtube_title` maps to legacy `shorts_title`.

## Manual Test Plan

Run one draft against local CentralAIService and confirm the review UI receives headline/caption/title/source/timestamps.

## Risks

Current CentralAIService contract does not exactly match target payload yet.

## Out of Scope

Provider-level prompt engineering inside CentralAIService.

