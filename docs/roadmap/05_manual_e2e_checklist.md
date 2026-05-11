# Manual E2E Checklist

Use this checklist after each MVP-flow change. Prefer dry-run/mock publishing first, then real platform tests.

## 1. Start CentralAIService

- Start the service with its documented local command.
- Confirm `GET /health` returns OK.
- Confirm the configured URL matches `CENTRAL_AI_SERVICE_URL` or `CENTRAL_AI_SERVICE_URL` equivalent in docs.

## 2. Start CentralPublishingHub

- Start the Hub with its documented local command.
- Confirm `GET /health` returns OK.
- Confirm `/api/v1/publish` and `/api/v1/schedule` contracts are available.
- Confirm `CENTRAL_PUBLISHING_HUB_URL` points at this Hub.

## 3. Start EconomikaNoticias GUI

- Launch the GUI from the repo root.
- Confirm no hidden Sentinel/bootstrap service is required.
- Confirm preflight checks show CentralAIService and CentralPublishingHub status clearly.

## 4. Health Checks

- CentralAIService health: OK.
- CentralPublishingHub health: OK.
- Local FFmpeg available.
- Required environment variables loaded.

## 5. Discovery Via Manual Links

- Paste one manual news or X link.
- Start processing.
- Confirm a normalized candidate is created.
- Confirm failure of X metadata extraction does not block a manual/news candidate.

## 6. Discovery Via RSS Fallback

- Run discovery with Twikit unavailable or cookies absent.
- Confirm RSS sources from `config/news_sources.json` are used.
- Confirm candidates include id, url, source, score and description.

## 7. Generate Draft

- Select one candidate.
- Generate headline, caption, title, source and optional trim hints through CentralAIService.
- Confirm the GUI shows editable text.

## 8. Render Tiny Video

- Render a short local video or image-based reel.
- Confirm the output file exists.
- Confirm artifact metadata includes `video_path`.
- Play the output locally enough to confirm it is non-empty and vertical.

## 9. Publish To Hub Dry-Run/Mock

- Use Hub dry-run/mock mode if available.
- Send payload:

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

- Confirm Hub accepts the intent and reports target-level results.

## 10. Publish YouTube Shorts

- Use a known test account or approved production account.
- Confirm OAuth/token state is valid.
- Publish one short.
- Record returned id/url.

## 11. Publish Instagram Reel/Story

- Confirm Meta token, IG user id and permissions.
- Publish one Reel.
- Publish one Story.
- Record returned ids/urls/statuses.

## 12. Verify Logs/Results

- Check GUI logs.
- Check Hub logs.
- Confirm no local Catbox/Gofile/Uguu upload happened from EconomikaNoticias.
- Confirm failed publish intents are visible and retryable.
- Confirm no secrets/cookies/generated files were added to git.

