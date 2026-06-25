# Manual Publish Status

The manual publish status tracker records what happened after a publish queue packet was uploaded by hand. It tracks each `post_id` and platform independently in a local JSON file; it does not publish content or call any platform API.

Supported platforms are `tiktok`, `instagram_reels`, and `youtube_shorts`. Supported statuses are `pending`, `drafted`, `uploaded`, `published`, `skipped`, and `failed`.

## Mark a Status

Mark a post as published and retain its external URL and operator note:

```powershell
py scripts\update_publish_status.py mark --post-id 2057499359705813029 --platform tiktok --status published --external-url "https://..." --notes "Uploaded manually"
```

Mark a platform as skipped:

```powershell
py scripts\update_publish_status.py mark --post-id 2057499359705813029 --platform instagram_reels --status skipped --notes "Not suitable"
```

Every mark appends a history item. The first `published` mark also sets `published_at`. Writes use an adjacent temporary file and atomic replacement.

When `runtime/publish_queue/manifest.json` exists, the command checks the post and platform against it. A mismatch prints a warning but is still recorded. Add `--strict` to reject mismatches instead. The manifest is optional, so an operator can still record a result when the queue artifact is unavailable.

## List Statuses

```powershell
py scripts\update_publish_status.py list --format text
```

JSON is the default format. Use `--post-id` or `--platform` to filter results. Queue packet/platform combinations with no recorded entry appear as `pending`, making the list useful before the first mark.

## Summarize Statuses

```powershell
py scripts\update_publish_status.py summary --format text
```

The summary counts each status by platform and reports the total queueable packet/platform combinations from the manifest when it is available. Untracked queue combinations count as `pending`.

## Integration with Pipeline Report

The pipeline report builder (`build_pipeline_report.py`) automatically integrates manual publish statuses:
- It reads the status file (default: `runtime/publish_status/status.json`) by default.
- Shows status tables in the packet section and integrates status details (`external_url`, `notes`, `updated_at`) directly.
- Keeps the manual upload checklist up-to-date (checked for `published` or `skipped`, retry prompt for `failed`).
- Computes overall publish completion counts and flags (`publish_complete`, `publish_pending_count`, `publish_failed_count`).

See [`pipeline_report.md`](pipeline_report.md) for more details.

## Local Output and Boundary

The default status file is:

```text
runtime/publish_status/status.json
```

Override it with `--status-file`; override the queue manifest with `--publish-queue-manifest`. `--now` accepts an ISO timestamp on `mark` for controlled manual operations and tests.

This tracker is local only. It has no TikTok, Instagram, or YouTube APIs, OAuth, browser automation, scheduling, AI caption generation, audio, subtitles, animations, dashboard changes, database changes, or cloud storage. Files under `runtime/publish_status/` must not be committed.
