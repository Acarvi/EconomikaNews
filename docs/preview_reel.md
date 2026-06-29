# Preview Reel MVP

The preview reel command is the fastest path from an approved local item to a usable vertical reel preview. It runs the local pipeline, selects a ready publish packet, copies the final MP4 and upload assets into one simple folder, and can open the video and folder on Windows.

## Command

```powershell
py scripts\generate_preview_reel.py --overwrite --open
```

Generate a preview for a specific post:

```powershell
py scripts\generate_preview_reel.py --post-id 2057499359705813029 --overwrite --open
```

If `--post-id` is omitted, the command uses the first packet with `packet_ready=true` in `runtime/publish_queue/manifest.json`.

## Output

Each preview is written to:

```text
runtime/preview_reels/<post_id>/
```

The folder contains:

```text
runtime/preview_reels/<post_id>/reel.mp4
runtime/preview_reels/<post_id>/card.png
runtime/preview_reels/<post_id>/caption.txt
runtime/preview_reels/<post_id>/metadata.json
runtime/preview_reels/<post_id>/preview_report.md
```

`card.png` is copied when a matching render card is available. The command always prints a JSON summary with the final paths, open status, warnings, and errors.

## Manual Next Step

Watch `reel.mp4`, copy `caption.txt`, then upload the MP4 and caption manually to TikTok, Instagram Reels, and YouTube Shorts. After upload, record the outcome with `update_publish_status.py`.

```powershell
py scripts\update_publish_status.py mark --post-id <post_id> --platform tiktok --status published --external-url "https://..."
```

## Boundaries

This command does not implement TikTok, Instagram, or YouTube APIs; OAuth; browser automation publishing; scheduling; AI caption generation; audio/music; voiceover; subtitles; cloud storage; or database changes. Generated files under `runtime/preview_reels/` are local runtime artifacts and must not be committed.
