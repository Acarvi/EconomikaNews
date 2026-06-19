# Publish Queue Manifest

The publish queue manifest step builds a stable JSON index of prepared local manual-upload packets. Future dashboard, review, or publishing stages can consume this manifest instead of scanning `runtime/publish_queue/` ad hoc.

```text
runtime/publish_queue/<post_id>/video.mp4
runtime/publish_queue/<post_id>/caption.txt
runtime/publish_queue/<post_id>/metadata.json
  -> scripts/build_publish_queue_manifest.py
  -> runtime/publish_queue/manifest.json
```

## Usage

Default command:

```powershell
python scripts\build_publish_queue_manifest.py
```

Input:

```text
runtime/publish_queue/<post_id>/video.mp4
runtime/publish_queue/<post_id>/caption.txt
runtime/publish_queue/<post_id>/metadata.json
```

Output:

```text
runtime/publish_queue/manifest.json
```

CLI options:

- `--queue-dir`: publish queue directory. Default: `runtime/publish_queue`.
- `--output-json`: manifest path. Default: `runtime/publish_queue/manifest.json`.
- `--include-invalid`: include invalid packet details in `invalid_packets`.
- `--pretty`: accepted for CLI compatibility; output is written with two-space indentation.

Missing queue directories exit successfully and create an empty manifest. Files directly inside `runtime/publish_queue/`, including an existing `manifest.json`, are ignored. Only direct child directories are treated as post packet directories.

## Packet Ready

A packet entry has `packet_ready: true` only when:

- `video.mp4` exists.
- `video.mp4` has a file size greater than zero.
- `caption.txt` exists.
- `metadata.json` exists and is valid JSON.
- Metadata `post_id` matches the packet directory name.
- Metadata `video_path` matches the discovered packet video path.
- Metadata `caption_path` matches the discovered caption path.
- Metadata has `packet_ready: true`.
- Metadata has `manual_upload: true`.
- Metadata `packet_errors` is empty.
- Metadata `platforms` is a non-empty list.
- No new packet errors are recorded.

If `caption.txt` or `metadata.json` is missing or invalid, the packet is still included with `packet_ready: false` and explanatory `packet_errors`.

If `video.mp4` is missing or empty, the packet directory is counted as invalid and excluded from `packets` by default. Use `--include-invalid` to include invalid packet details in the manifest.

## Manifest Fields

Each packet entry includes source provenance, platform list, file size, caption length, and a normalized caption preview. The preview is the first 140 characters after whitespace normalization.

```json
{
  "post_id": "post-1",
  "packet_dir": "runtime/publish_queue/post-1",
  "video_path": "runtime/publish_queue/post-1/video.mp4",
  "caption_path": "runtime/publish_queue/post-1/caption.txt",
  "metadata_path": "runtime/publish_queue/post-1/metadata.json",
  "file_size_bytes": 85142,
  "created_at": "2026-06-19T10:00:00Z",
  "caption_length": 244,
  "caption_preview": "ECONOMIKA - senal detectada. Fuente: @juanrallo URL: ...",
  "source_account_handle": "juanrallo",
  "source_url": "https://x.com/juanrallo/status/2057499359705813029",
  "platforms": ["tiktok", "instagram_reels", "youtube_shorts"],
  "manual_upload": true,
  "packet_ready": true,
  "packet_errors": []
}
```

## Scope

This is a local manual-upload manifest only. Publishing is not implemented. The script does not call TikTok, Instagram, or YouTube APIs; perform OAuth; automate browsers; schedule posts; generate AI captions; add audio/subtitles/animations; change the dashboard; write to a database; or use cloud storage.

Generated manifests and packets under `runtime/publish_queue/` are runtime artifacts and must not be committed.
