# Current State Analysis

This analysis is based on the current EconomikaNoticias repo plus local README and basic source inspection of sibling repos `CentralAIService` and `CentralPublishingHub`.

## EconomikaNoticias

### `main.py`

- Contains Tkinter GUI, batch processing, render orchestration, review UI, cloud sync actions, and publish actions in one large entry point.
- Bootstraps SentinelAPI by adding `../SentinelAPI` to `sys.path`, then importing `bootstrap.activate_security`.
- Calls `check_centralai_health(CENTRAL_AI_URL)` before processing.
- Imports `core.publisher` and `core.youtube_uploader`, meaning publishing concerns are still visible in the product app.
- Has platform controls for YouTube, Facebook, Instagram Reels, and IG Stories; MVP should remove Facebook from the primary flow and add/feed normalize Instagram Feed/Post.

### `server.py`

- Defines a FastAPI server inside EconomikaNoticias for viral scout, pending tweets, scheduling, and queue processing.
- Bootstraps SentinelAPI similarly to `main.py`.
- Contains queue processing that calls `core.publisher.upload_reel`, `upload_story`, and `upload_facebook_reel` directly.
- This overlaps with CentralPublishingHub responsibilities. For MVP, `server.py` can remain for compatibility, but publication state and retries should move to CentralPublishingHub as the primary path.

### `core/ai_handler.py`

- Already delegates some work to CentralAIService.
- Uses `CENTRAL_AI_URL` with default `http://localhost:8080`.
- Current request shape differs from the target product-level contract:
  - video path path: `{"video_path": ..., "global_comments": ..., "custom_prompt": ...}`
  - static path: `/v1/analyzer/storyboard`
- Returns a tuple expected by existing EconomikaNoticias code.
- Should become an adapter around a typed HTTP client while preserving the tuple API temporarily.

### `core/publisher.py`

- Normalizes `CENTRAL_PUBLISHING_HUB_URL`, builds `/api/v1`, and calls the hub for publish/schedule.
- Also still contains direct Instagram Graph API helpers and polling.
- Uploads media to Catbox before sending to the hub.
- Queues failed posts locally in JSON.
- This is a transitional mix: product app client, emergency fallback, temporary hosting, and direct platform publisher. The target is to make the hub client primary and move platform publishing behavior into CentralPublishingHub.

### `core/youtube_uploader.py`

- Contains direct YouTube OAuth and upload logic.
- CentralPublishingHub also has a `core/youtube_uploader.py`.
- For the MVP architecture, YouTube credential handling and upload should live in CentralPublishingHub. EconomikaNoticias should only request `youtube_shorts` as a target.

### `core/generator.py`

- Owns local render logic and 1080x1920 output. This is correctly part of EconomikaNoticias for the MVP.
- The current public functions are media-specific (`generate_reel_from_image`, `process_video_for_reel`). A small contract wrapper should later expose `render_post(post_draft) -> rendered_video_path`.

### `core/viral_scout.py`

- Handles candidate discovery, accounts, cookies, processed/rejected history, and Nitter fallback.
- This can remain in EconomikaNoticias for MVP because discovery is product-specific.
- It writes local history JSON files under `data/`.

### `utils/network.py`

- Provides health checks for CentralAIService and CentralPublishingHub.
- Auto-starts sibling repos via relative paths (`../CentralAIService`, `../CentralPublishingHub`) when localhost services are down.
- This violates the target principle unless guarded by an explicit opt-in flag.

### `.gitignore`

- Correctly ignores `.env`, cookies, tokens, media files, generated output, and local JSON state.
- New SQLite files should be ignored unless a blank schema/migration file is intentionally tracked.

### `Dockerfile`

- Packages `server.py` as the cloud/server entry point.
- Copies `core`, `config`, `data`, `prompts`, and `utils`.
- This still treats EconomikaNoticias server as a backend with publishing/scout behavior. It should not become the central publishing service.

### `requirements.txt` and `requirements-server.txt`

- `requirements.txt` includes local GUI/render/discovery plus YouTube libraries.
- `requirements-server.txt` also includes Google AI and YouTube libraries, even though the server comment says heavy processing is local.
- As publishing and AI move to hubs, EconomikaNoticias should eventually reduce direct provider/platform dependencies where possible.

### `docs/DEVELOPER.md`

- Documents a hybrid cloud-local architecture where `server.py` owns the cloud publishing queue.
- This conflicts with the corrected ecosystem architecture where CentralPublishingHub owns publishing queue/retries/state.

## CentralAIService

README and `main.py` show:

- `GET /health`
- `POST /v1/analyzer/draft`
- `POST /v1/analyzer/storyboard`
- `POST /v1/analyzer/refine`
- `POST /v1/ai/generate`

Current `DraftRequest` expects:

```json
{
  "video_path": "...",
  "global_comments": "",
  "target_format": "reel",
  "context_script": "",
  "custom_prompt": null
}
```

The target MVP contract is more product-oriented and should either be added to CentralAIService or adapted by EconomikaNoticias until the service is upgraded.

## CentralPublishingHub

README and `routers/publish.py` show:

- `GET /health`
- `POST /api/v1/publish`
- `POST /api/v1/schedule`
- `POST /api/v1/publish-now`
- `GET /api/v1/queue`
- `GET /api/v1/locations`

Current `PostPayload` expects:

```json
{
  "video_url": "...",
  "video_path": "...",
  "caption": "...",
  "target_time": null,
  "platforms": ["instagram_reel"],
  "location_id": null,
  "shorts_title": "Noticia",
  "account_id": "economika"
}
```

The target MVP payload uses `targets`, `title`, `publish_mode`, and `scheduled_at`. This mismatch should be documented and resolved through versioned API contracts or a compatibility adapter.

## SentinelAPI

SentinelAPI is present locally, but the MVP must not depend on it. Current bootstrap in `main.py` and `server.py` should become optional and disabled by default with `ENABLE_SENTINEL=false`.

