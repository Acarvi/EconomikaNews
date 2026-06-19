# Video Manifest

The video manifest step builds a stable JSON index of generated local MP4 artifacts so future upload or publishing stages can consume known outputs without scanning `runtime/videos/` ad hoc.

```text
runtime/videos/<post_id>/video.mp4
runtime/videos/<post_id>/video_metadata.json
  -> scripts/build_video_manifest.py
  -> runtime/videos/manifest.json
```

## Usage

Default command:

```powershell
python scripts\build_video_manifest.py
```

Input:

```text
runtime/videos/<post_id>/video.mp4
runtime/videos/<post_id>/video_metadata.json
```

Output:

```text
runtime/videos/manifest.json
```

CLI options:

- `--videos-dir`: video output directory. Default: `runtime/videos`.
- `--output-json`: manifest path. Default: `runtime/videos/manifest.json`.
- `--include-invalid`: include invalid video details in `invalid_videos`.
- `--pretty`: accepted for CLI compatibility; output is written with two-space indentation.

Missing video directories exit successfully and create an empty manifest. Files directly inside `runtime/videos/`, including an existing `manifest.json`, are ignored. Only direct child directories are treated as post video directories.

## Ready For Upload

A video entry has `ready_for_upload: true` only when:

- `video.mp4` exists.
- `video.mp4` has a file size greater than zero.
- `video_metadata.json` exists and is valid JSON.
- The metadata `post_id` matches the video directory name.
- The metadata `video_path` matches the discovered `video.mp4`.
- The metadata has `ready_for_upload: true`.
- `width`, `height`, `duration_seconds`, and `fps` are greater than zero.
- No `video_errors` are recorded.

If metadata is missing or invalid, the video is still included with `ready_for_upload: false` and explanatory `video_errors`.

If `video.mp4` is missing or empty, the video directory is counted as invalid and excluded from `videos` by default. Use `--include-invalid` to include invalid video details in the manifest.

## Source Provenance

The manifest preserves source provenance for manual review and captioning:

- `source_account_handle`
- `source_url`

The builder prefers top-level values from `video_metadata.json`. For older metadata files, it falls back to `source_manifest_entry.account_handle` and `source_manifest_entry.url`. If provenance is unavailable, these fields are written as empty strings.

## Scope

This step reads local MP4 file stats and local metadata JSON only. It does not decode full videos in tests and does not make network calls.

Publishing is not implemented yet. Upload APIs, scheduling, AI generation, text-to-speech/audio, animation, dashboard changes, media compositing, video rendering changes, database writes, and cloud storage are out of scope.

## Manifest Shape

```json
{
  "generated_at": "2026-06-19T10:00:00Z",
  "videos_dir": "runtime/videos",
  "video_count": 1,
  "invalid_video_count": 0,
  "videos": [
    {
      "post_id": "post-1",
      "video_path": "runtime/videos/post-1/video.mp4",
      "metadata_path": "runtime/videos/post-1/video_metadata.json",
      "file_size_bytes": 123456,
      "created_at": "2026-06-19T10:00:00Z",
      "duration_seconds": 6,
      "fps": 30,
      "width": 1080,
      "height": 1920,
      "source_card_path": "runtime/renders/post-1/card.png",
      "source_account_handle": "juanrallo",
      "source_url": "https://x.com/juanrallo/status/2057499359705813029",
      "ready_for_upload": true,
      "video_errors": []
    }
  ],
  "invalid_videos": []
}
```

Writes are atomic:

```text
manifest.json.tmp -> manifest.json
```

Generated manifests and video files under `runtime/videos/` are runtime artifacts and must not be committed.
