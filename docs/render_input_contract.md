# Render Input Contract

The render input step converts approved bundle index entries into stable JSON files that a future renderer can consume without re-reading bundle metadata or making network calls.

```text
runtime/approved/index.json
  -> scripts/build_render_inputs.py
  -> runtime/render_inputs/<post_id>.json
```

Rendering is not implemented in this step. The script does not call ffmpeg, moviepy, PIL, text-to-speech, AI generation, publishing, scheduling, or media download code.

## Usage

Default command:

```powershell
python scripts\build_render_inputs.py
```

Input:

```text
runtime/approved/index.json
```

Output:

```text
runtime/render_inputs/<post_id>.json
```

CLI options:

- `--index-file`: approved bundle index path. Default: `runtime/approved/index.json`.
- `--output-dir`: render input output directory. Default: `runtime/render_inputs`.
- `--include-not-ready`: include bundles with `ready_for_render: false`; their `render.ready` is `false`.
- `--overwrite`: replace existing render input files with atomic tmp-file swaps.
- `--dry-run`: print the summary without creating directories or writing files.

By default, only bundles with `ready_for_render: true` are included. Existing output files are skipped unless `--overwrite` is set.

## Input Rules

The index must be a JSON object with a `bundles` list. Missing files, invalid JSON, non-object top-level JSON, a missing `bundles` key, or a non-list `bundles` value exit with code `1` and print a clear stderr error.

Invalid individual bundles are skipped and recorded in the summary `errors`. The script continues processing later valid bundles.

Each included bundle must have `post_id`. A render input is considered ready only when:

- `ready_for_render` is `true`.
- `post_id` exists.
- `review_status` is `approved`.

When `--include-not-ready` is used, not-ready bundles are still written, but `render.ready` is `false` and `render.notes` explains why.

## Text Rules

Text fields are deterministic and do not use AI generation:

- `text.headline`: first 100 characters of stripped `text_prefix`.
- `text.headline`: `Untitled` when `text_prefix` is missing or blank.
- `text.body`: original `text_prefix`, or an empty string when missing.
- `render.language`: `en`.

The script does not translate, rewrite, summarize, or enrich text.

## Schema

Each render input uses `schema_version: 1`:

```json
{
  "schema_version": 1,
  "post_id": "post-1",
  "source": "x",
  "account_handle": "economika",
  "url": "https://x.com/economika/status/1",
  "text": {
    "headline": "Markets rally after a central bank signal",
    "body": "Markets rally after a central bank signal",
    "source_text_prefix": "Markets rally after a central bank signal"
  },
  "engagement": {
    "score": 123.0,
    "metrics": {
      "likes": 10
    }
  },
  "review": {
    "status": "approved",
    "reviewed_at": "2026-05-24T10:00:00Z",
    "review_note": null
  },
  "bundle": {
    "bundle_dir": "runtime/approved/post-1",
    "metadata_path": "runtime/approved/post-1/metadata.json",
    "bundle_errors": []
  },
  "media": {
    "has_media": true,
    "files": [
      {
        "index": 1,
        "filename": "media_1.jpg",
        "local_path": "runtime/approved/post-1/media_1.jpg",
        "content_type": "image/jpeg",
        "source_url": "https://example.com/media_1.jpg"
      }
    ]
  },
  "render": {
    "ready": true,
    "target_formats": ["vertical_short"],
    "template": "default_news_card",
    "language": "en",
    "notes": []
  },
  "original_index_bundle": {}
}
```

`original_index_bundle` preserves the source index bundle for traceability.

## Summary

The script prints JSON to stdout:

```json
{
  "index_file": "runtime/approved/index.json",
  "output_dir": "runtime/render_inputs",
  "inputs_written": 1,
  "inputs_skipped": 0,
  "skipped_existing": 0,
  "bundles_seen": 1,
  "bundles_included": 1,
  "errors": [],
  "dry_run": false,
  "overwrite": false
}
```

Writes are atomic:

```text
<post_id>.json.tmp -> <post_id>.json
```

Generated render input files under `runtime/render_inputs/` are runtime artifacts and must not be committed.

## Validation

Use a temp directory outside the repository on Windows:

```powershell
python -m compileall app tests scripts
python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="$env:TEMP\economika-pytest-tmp"
python -m pytest -p no:cacheprovider --basetemp="$env:TEMP\economika-pytest-tmp"
git ls-files -- runtime x_headers.json .env .env.* *.db runtime/outputs/ runtime/approved/ runtime/render_inputs/
```
