# Target HTTP Contracts

These are the target contracts for the Economika ecosystem MVP. They may require updates in CentralAIService and CentralPublishingHub, or temporary adapters inside EconomikaNoticias during migration.

## Shared Requirements

- All services expose `GET /health`.
- EconomikaNoticias configures service URLs through environment variables.
- Auth for protected hub calls should use `ECONOMIKA_ADMIN_API_KEY`, preferably as `X-API-Key`.
- Payloads must not contain secrets.
- Local paths are acceptable in local development only when the receiving service can access the same filesystem. Hosted production should use public or signed URLs.

## CentralAIService

### `GET /health`

Expected response:

```json
{
  "status": "ok",
  "service": "CentralAIService"
}
```

### `POST /v1/analyzer/draft`

Request:

```json
{
  "project": "economika_noticias",
  "input_type": "tweet_or_media",
  "source_url": "https://x.com/i/status/...",
  "description": "...",
  "media_path": "D:/path/to/local/media.mp4",
  "target_platforms": ["instagram_reel", "youtube_shorts"],
  "editorial_profile": "economika"
}
```

Response:

```json
{
  "headline": "...",
  "caption": "...",
  "youtube_title": "...",
  "caption_b": "...",
  "source": "...",
  "best_segment_start": "00:00",
  "best_segment_end": "END",
  "confidence": 0.0,
  "warnings": []
}
```

Notes:

- `youtube_title` should be mapped to existing legacy `shorts_title` until old code is removed.
- `caption_b` is optional but useful for review UI A/B variants.
- `best_segment_start` and `best_segment_end` should be present for video inputs and default to `00:00`/`END`.

### `POST /v1/analyzer/refine`

Request:

```json
{
  "project": "economika_noticias",
  "draft": {
    "headline": "...",
    "caption": "...",
    "youtube_title": "...",
    "source": "..."
  },
  "feedback": "Make the caption shorter and less sensational.",
  "target_platforms": ["instagram_reel", "youtube_shorts"],
  "editorial_profile": "economika"
}
```

Response follows the same shape as `POST /v1/analyzer/draft`.

## CentralPublishingHub

### `GET /health`

Expected response:

```json
{
  "status": "ok",
  "service": "CentralPublishingHub"
}
```

### `POST /api/v1/publish`

Request:

```json
{
  "account_id": "economika",
  "media_path": "D:/path/to/rendered-video.mp4",
  "video_url": "https://public-url-if-needed.example/video.mp4",
  "caption": "...",
  "title": "...",
  "targets": [
    "instagram_reel",
    "instagram_story",
    "instagram_feed",
    "youtube_shorts"
  ],
  "publish_mode": "now",
  "scheduled_at": null
}
```

Response:

```json
{
  "job_id": "...",
  "status": "queued",
  "results": [
    {
      "target": "instagram_reel",
      "success": true,
      "external_id": "...",
      "url": "...",
      "error": null
    }
  ]
}
```

Allowed `status` values:

- `queued`
- `published`
- `partial_failed`
- `failed`

### `POST /api/v1/schedule`

Request is the same base payload as publish, with:

```json
{
  "publish_mode": "scheduled",
  "scheduled_at": "2026-05-11T18:00:00+02:00"
}
```

The hub owns schedule persistence and retry behavior.

### `GET /api/v1/queue`

Expected response:

```json
{
  "jobs": [
    {
      "job_id": "...",
      "account_id": "economika",
      "status": "queued",
      "targets": ["instagram_reel"],
      "scheduled_at": null,
      "created_at": "..."
    }
  ]
}
```

## Compatibility Notes

Current CentralPublishingHub uses `platforms` and `shorts_title`; target contract uses `targets` and `title`. Current EconomikaNoticias should include an adapter until both sides agree on the target names.

Current CentralAIService `/v1/analyzer/draft` expects `video_path`, `global_comments`, and `custom_prompt`. The target product-level request should be implemented in CentralAIService or translated by a dedicated `central_ai_client.py`.

