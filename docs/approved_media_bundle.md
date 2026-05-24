# Approved Media Bundle

The approved media bundle step materializes reviewed candidates into stable local folders:

```text
runtime/outputs/approved_candidates.json
  -> scripts/build_approved_media_bundle.py
  -> runtime/approved/<post_id>/metadata.json
  -> runtime/approved/<post_id>/media_1.jpg
  -> runtime/approved/<post_id>/media_2.mp4
```

This prepares approved posts for later rendering and publishing while keeping those later stages out of scope.

## Usage

Export approved candidates from the review database:

```powershell
python scripts\export_approved_candidates.py --db-path runtime\economika_news.db
```

Build approved media bundles:

```powershell
python scripts\build_approved_media_bundle.py
```

The script reads `runtime/outputs/approved_candidates.json` by default and writes bundles under `runtime/approved/<post_id>/`.

Build the approved bundle index:

```powershell
python scripts\build_approved_bundle_index.py
```

The index script scans `runtime/approved/<post_id>/metadata.json` bundle folders and writes `runtime/approved/index.json` for later render or publishing stages to consume without re-scanning bundle directories ad hoc.

## CLI Options

- `--approved-file`: approved candidates JSON path. Default: `runtime/outputs/approved_candidates.json`.
- `--output-dir`: bundle output directory. Default: `runtime/approved`.
- `--overwrite`: replace existing media files with atomic tmp-file swaps.
- `--dry-run`: print the summary without creating directories or writing files.
- `--timeout-seconds`: download timeout per media URL. Default: `30`.

## Candidate Handling

The input file must be a JSON object with a `candidates` list. Invalid top-level JSON exits with code `1`. Invalid individual candidates are skipped, recorded in the summary `errors`, and do not stop valid candidates from being bundled.

Each valid candidate must include `post_id`. Candidates without media still get a `metadata.json` file with `local_media: []`.

## Media URL Rules

Candidate-level `url` and `expanded_url` are preserved only in metadata and are never treated as media.

Candidate-level media keys:

- `media_url`
- `media_url_https`
- `video_url`
- `preview_image_url`

Inside `candidate["media"]` list or dict entries, these keys are inspected:

- `url`
- `media_url`
- `media_url_https`
- `video_url`
- `preview_image_url`
- `expanded_url`

Only direct `http://` and `https://` URLs are downloadable. The script skips `t.co`, `file:`, `javascript:`, `data:`, relative URLs, and `x.com` or `twitter.com` status URLs.

## File Writes

Metadata is always rewritten unless `--dry-run` is set:

```text
metadata.json.tmp -> metadata.json
```

Media files are deterministic and written atomically:

```text
media_1.tmp -> media_1.<ext>
media_2.tmp -> media_2.<ext>
media_3.tmp -> media_3.<ext>
```

If a matching `media_<index>.*` file already exists and `--overwrite` is not set, the script skips that media item, counts `media_skipped`, and still rewrites metadata. With `--overwrite`, existing media is replaced through the same tmp-file swap.

## Extension Inference

The extension priority is:

1. HTTP `Content-Type`
2. URL path suffix
3. `.bin`

Supported content types:

- `image/jpeg` -> `.jpg`
- `image/png` -> `.png`
- `image/webp` -> `.webp`
- `image/gif` -> `.gif`
- `video/mp4` -> `.mp4`
- `video/webm` -> `.webm`
- `application/octet-stream` -> `.bin`

Query parameters are ignored. For example, `https://example.com/media?id=123&format=jpg` resolves to `.bin` unless the response content type gives a supported extension.

## Metadata Shape

`metadata.json` includes:

- `post_id`
- `account_handle`
- `url`
- `text_prefix`
- `score`
- `metrics`
- `media_count`
- `source`
- `is_new` when present
- `review_status`
- `reviewed_at`
- `review_note`
- `review_updated_at`
- `original_candidate`
- `local_media`
- `bundle_errors`

Each `local_media` entry includes:

- `index`
- `source_url`
- `local_path`
- `filename`
- `content_type`
- `status`: `downloaded`, `skipped_existing`, `failed`, or `skipped_unsupported_url`
- `error` when the status is `failed`

## Summary

The script prints JSON to stdout:

```json
{
  "approved_count": 1,
  "bundled_count": 1,
  "media_downloaded": 1,
  "media_skipped": 0,
  "media_failed": 0,
  "errors": [],
  "output_dir": "runtime/approved",
  "dry_run": false,
  "overwrite": false
}
```

Missing files and invalid top-level JSON return exit code `1` with a clear stderr message. Failed individual media downloads are recorded in metadata and summary errors, but a valid approved file still exits `0`.

## Approved Bundle Index

`scripts/build_approved_bundle_index.py` creates a stable JSON index from approved media bundle metadata:

```text
runtime/approved/<post_id>/metadata.json
  -> scripts/build_approved_bundle_index.py
  -> runtime/approved/index.json
```

Default command:

```powershell
python scripts\build_approved_bundle_index.py
```

CLI options:

- `--bundles-dir`: approved bundle directory. Default: `runtime/approved`.
- `--output-json`: index output path. Default: `runtime/approved/index.json`.
- `--include-invalid`: include invalid bundle details in `invalid_bundles`.
- `--pretty`: accepted for compatibility; output is formatted with two-space indentation.

The script scans only direct child directories under `runtime/approved`. Files directly inside that directory, including `index.json`, are ignored as bundle candidates.

Each valid bundle entry includes `post_id`, `account_handle`, `url`, `text_prefix`, `score`, `metrics`, review fields, metadata paths, normalized `media_files`, `bundle_errors`, and `ready_for_render`.

`ready_for_render` is `true` when metadata is structurally valid, `review_status` is `approved`, `post_id` is present, and `bundle_errors` is empty. Metadata with `review_status` other than `approved` is treated as invalid and excluded from `bundles`. Metadata with download or bundle errors stays in `bundles` but has `ready_for_render: false`.

`invalid_bundles` reports bundle folders with missing metadata, invalid JSON, missing `post_id`, non-approved `review_status`, or invalid `local_media` / `bundle_errors` shapes. By default the index records `invalid_bundle_count` but leaves `invalid_bundles` empty; pass `--include-invalid` to include those details in `runtime/approved/index.json`. The CLI summary always prints error messages to stdout.

Valid bundles are sorted deterministically by score descending, `reviewed_at` descending, and `post_id` ascending. The index write is atomic:

```text
index.json.tmp -> index.json
```

If `runtime/approved` does not exist, the script creates an empty index with `bundle_count: 0` and exits `0`.

## Validation

Use a temp directory outside the repository on Windows:

```powershell
python -m compileall app tests scripts
python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="$env:TEMP\economika-pytest-tmp"
python -m pytest -p no:cacheprovider --basetemp="$env:TEMP\economika-pytest-tmp"
git ls-files -- runtime x_headers.json .env .env.* *.db runtime/outputs/ runtime/approved/
```

The repository must not commit runtime media, runtime outputs, generated indexes, local databases, or secret files.
