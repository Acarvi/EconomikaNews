# Publish Queue

The publish queue step prepares generated local videos for manual social upload. It reads the video manifest, copies ready MP4 files into per-post packet folders, and writes a deterministic caption and packet metadata.

```text
runtime/videos/manifest.json
runtime/videos/<post_id>/video.mp4
  -> scripts/build_publish_queue.py
  -> runtime/publish_queue/<post_id>/video.mp4
  -> runtime/publish_queue/<post_id>/caption.txt
  -> runtime/publish_queue/<post_id>/metadata.json
```

## Usage

Default command:

```powershell
python scripts\build_publish_queue.py
```

Input:

```text
runtime/videos/manifest.json
runtime/videos/<post_id>/video.mp4
```

Output:

```text
runtime/publish_queue/<post_id>/video.mp4
runtime/publish_queue/<post_id>/caption.txt
runtime/publish_queue/<post_id>/metadata.json
```

CLI options:

- `--video-manifest`: video manifest path. Default: `runtime/videos/manifest.json`.
- `--output-dir`: packet output directory. Default: `runtime/publish_queue`.
- `--include-not-ready`: include videos where `ready_for_upload` is not true.
- `--overwrite`: replace existing packet files with atomic swaps.
- `--dry-run`: print the summary without creating directories or writing files.
- `--limit`: build at most this many selected packets.
- `--platform`: repeatable or comma-separated platform list. Allowed values: `tiktok`, `instagram_reels`, `youtube_shorts`. Default: all three.

By default, only video manifest entries with `ready_for_upload: true` are packaged.

## Caption

Captions are deterministic and use existing metadata only. The script does not summarize articles, rewrite text with an LLM, invent claims, or call AI services.

The caption includes:

- A short Economika line.
- Source handle when present, otherwise `Fuente: desconocida`.
- Source URL when present.
- Post ID.
- Deterministic hashtags: `#Economika #Economia #Politica #Shorts`.

Captions are kept under 500 characters.

Publish packet metadata includes `source_account_handle` and `source_url` from the video manifest entry. These values are carried forward for manual review and captioning only; the script still performs no platform publishing and no AI caption generation.

## Scope

This is a manual-upload export step only. It does not implement TikTok, Instagram, or YouTube APIs; OAuth; browser automation; scheduling; AI caption generation; audio; subtitles; animations; dashboard changes; database writes; cloud storage; or platform publishing.

Generated files under `runtime/publish_queue/` are runtime artifacts and must not be committed.
