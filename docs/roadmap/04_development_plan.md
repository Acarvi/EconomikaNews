# Development Plan

## Phase 0: Documentation And Contracts

- Add this roadmap and tickets.
- Record target contracts for CentralAIService and CentralPublishingHub.
- Record current mismatches without refactoring the system.

## Phase 1: Remove SentinelAPI As A Mandatory Dependency

- Guard Sentinel bootstrap behind `ENABLE_SENTINEL=false`.
- Ensure imports and tests pass when `../SentinelAPI` does not exist.
- Keep optional compatibility for local users who intentionally enable it.

## Phase 2: Centralized Settings And Service Clients

- Add explicit settings for:
  - `CENTRAL_AI_SERVICE_URL`
  - `CENTRAL_PUBLISHING_HUB_URL`
  - `ECONOMIKA_ADMIN_API_KEY`
  - `ECONOMIKA_ACCOUNT_ID`
- Add HTTP clients:
  - `services/central_ai_client.py`
  - `services/publishing_hub_client.py`
- Move health-check and payload construction into clients.
- Keep current public functions as wrappers during transition.

## Phase 3: Stable CentralAIService Client

- Make CentralAIService the primary draft/refine path.
- Adapt existing tuple return from `core/ai_handler.py` to structured response internally.
- Add response parsing, warnings, and clear errors.
- Keep local fallback optional and explicit.

## Phase 4: Stable CentralPublishingHub Client

- Make CentralPublishingHub the primary publish/schedule path.
- Normalize targets to `instagram_reel`, `instagram_story`, `instagram_feed`, and `youtube_shorts`.
- Move direct Graph API and YouTube upload usage out of the product path.
- Keep emergency direct fallback only if explicitly configured.

## Phase 5: SQLite Local Draft State

- Add a small SQLite store for local draft and render state.
- Store generated AI content, render path, status, and hub job references.
- Keep generated media files out of git.

## Phase 6: Connect Review UI To Publish

- Let operator review/edit headline, caption, title, source, and targets.
- Submit reviewed post to CentralPublishingHub.
- Store response in SQLite.
- Refresh local status from hub job state where possible.

## Phase 7: Smoke Tests And E2E

- Add import smoke tests without SentinelAPI.
- Mock hub clients.
- Test response parsing, publish payload construction, platform normalization, and SQLite store.
- Add a manual E2E checklist.

## Phase 8: Optional Deployment And Automation

- Decide whether EconomikaNoticias server remains a candidate intake service only.
- Document hosted hub URLs and production `.env` shape.
- Add optional automation after MVP is stable.

