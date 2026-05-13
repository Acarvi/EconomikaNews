# Publishing Contracts

CentralPublishingHub owns publishing.

EconomikaNoticias should be a client of the Hub, not the owner of platform upload logic. It should send publish intents and avoid duplicating upload, OAuth, hosting, polling, and platform-specific behavior.

## Known Fields

- `account_id`
- `video_path`
- `video_url`
- `caption`
- `title`
- `targets`
- `publish_mode`
- `scheduled_at`
- `platforms` legacy
- `shorts_title` legacy

## Known Targets

- `instagram_reel`
- `instagram_story`
- `instagram_feed`
- `youtube_shorts`

## API Key

`X-API-Key` can be sent when `ECONOMIKA_ADMIN_API_KEY` is configured.

## Example: Local File Publish Intent

```json
{
  "account_id": "default",
  "video_path": "D:\\Scripts\\EconomikaNoticias\\output\\example.mp4",
  "caption": "Draft caption for review",
  "title": "Draft title",
  "targets": ["instagram_reel", "youtube_shorts"],
  "publish_mode": "manual_review",
  "scheduled_at": null
}
```

## Example: Public URL Publish Intent

```json
{
  "account_id": "default",
  "video_url": "https://example.com/public/video.mp4",
  "caption": "Draft caption for review",
  "title": "Draft title",
  "targets": ["instagram_reel", "instagram_story"],
  "publish_mode": "manual_review",
  "scheduled_at": "2026-05-13T18:00:00+02:00"
}
```

## Legacy Shape

```json
{
  "account_id": "default",
  "video_path": "D:\\Scripts\\EconomikaNoticias\\output\\short.mp4",
  "caption": "Caption",
  "platforms": ["instagram", "youtube"],
  "shorts_title": "Shorts title"
}
```

## Decisions To Preserve

- CentralPublishingHub owns publishing.
- EconomikaNoticias should not duplicate upload logic.
- Temporary media hosting should be handled in the Hub when platforms require public URLs.

