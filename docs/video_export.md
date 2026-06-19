# Video Export

The video export step converts already-rendered static text card PNGs into short local vertical MP4 files. It prepares local media files for later social workflows without publishing, scheduling, upload APIs, audio, animation, or AI generation.

```text
runtime/renders/manifest.json
runtime/renders/<post_id>/card.png
  -> scripts/export_card_videos.py
  -> runtime/videos/<post_id>/video.mp4
  -> runtime/videos/<post_id>/video_metadata.json
```

## Usage

Default command:

```powershell
python scripts\export_card_videos.py
```

Input:

```text
runtime/renders/manifest.json
runtime/renders/<post_id>/card.png
```

Output:

```text
runtime/videos/<post_id>/video.mp4
runtime/videos/<post_id>/video_metadata.json
```

CLI options:

- `--manifest-file`: render manifest path. Default: `runtime/renders/manifest.json`.
- `--output-dir`: video output directory. Default: `runtime/videos`.
- `--duration-seconds`: MP4 duration. Default: `6`.
- `--fps`: frames per second. Default: `30`.
- `--include-not-ready`: include manifest entries where `ready_for_publish` is not true.
- `--overwrite`: replace existing `video.mp4` files with atomic MP4 swaps.
- `--dry-run`: print the summary without creating directories or writing files.
- `--limit`: export at most this many selected render entries.

By default, only manifest entries with `ready_for_publish: true` are exported. With `--include-not-ready`, not-ready renders can still be converted for inspection, but their metadata keeps `ready_for_upload: false`.

## Scope

This step makes one simple MP4 per render by repeating the static `card.png` for `duration_seconds * fps` frames. It preserves the source card dimensions, normally `1080x1920`, and writes no audio track.

The script uses local files only. It does not make network calls, publish posts, schedule posts, upload videos, generate AI media, create text-to-speech audio, add subtitles, animate cards, composite media, change the dashboard, write to a database, or use cloud storage.

## Metadata Shape

```json
{
  "post_id": "post-1",
  "source_card_path": "runtime/renders/post-1/card.png",
  "source_manifest_entry": {},
  "video_path": "runtime/videos/post-1/video.mp4",
  "duration_seconds": 6,
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "ready_for_upload": true,
  "video_errors": []
}
```

Writes are atomic:

```text
video.tmp.mp4 -> video.mp4
video_metadata.json.tmp -> video_metadata.json
```

Generated files under `runtime/videos/` are runtime artifacts and must not be committed.
