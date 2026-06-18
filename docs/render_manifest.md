# Render Manifest

The render manifest step builds a stable JSON index of generated local render artifacts so later publishing or video stages can consume known outputs without scanning `runtime/renders/` ad hoc.

```text
runtime/renders/<post_id>/card.png
runtime/render_inputs/<post_id>.json
  -> scripts/build_render_manifest.py
  -> runtime/renders/manifest.json
```

## Usage

Default command:

```powershell
python scripts\build_render_manifest.py
```

Input:

```text
runtime/renders/<post_id>/card.png
runtime/render_inputs/<post_id>.json
```

Output:

```text
runtime/renders/manifest.json
```

CLI options:

- `--renders-dir`: render output directory. Default: `runtime/renders`.
- `--render-inputs-dir`: render input directory. Default: `runtime/render_inputs`.
- `--output-json`: manifest path. Default: `runtime/renders/manifest.json`.
- `--include-invalid`: include invalid render details in `invalid_renders`.
- `--pretty`: accepted for CLI compatibility; output is written with two-space indentation.

Missing render directories exit successfully and create an empty manifest. Files directly inside `runtime/renders/`, including an existing `manifest.json`, are ignored. Only direct child directories are treated as post render directories.

## Ready For Publish

A render entry has `ready_for_publish: true` only when:

- `card.png` exists.
- Pillow can read the PNG and its dimensions are greater than zero.
- `runtime/render_inputs/<post_id>.json` exists.
- The render input `post_id` matches the render directory name.
- The render input has `render.ready: true`.
- No `render_errors` are recorded.

If the render input is missing, the render is still included with `ready_for_publish: false` and `render_errors: ["Render input missing"]`.

If the render input `post_id` does not match the folder name, the render is still included with `ready_for_publish: false` and a mismatch error.

If `card.png` is missing or unreadable, the render is counted as invalid and excluded from `renders` by default. Use `--include-invalid` to include invalid render details in the manifest.

## Scope

This step reads local PNG metadata and render input JSON only. It does not make network calls.

Publishing is not implemented yet. Video rendering is not implemented yet.

## Manifest Shape

```json
{
  "generated_at": "2026-06-18T10:00:00Z",
  "renders_dir": "runtime/renders",
  "render_inputs_dir": "runtime/render_inputs",
  "render_count": 1,
  "invalid_render_count": 0,
  "renders": [
    {
      "post_id": "post-1",
      "card_path": "runtime/renders/post-1/card.png",
      "render_input_path": "runtime/render_inputs/post-1.json",
      "width": 1080,
      "height": 1920,
      "file_size_bytes": 82444,
      "created_at": "2026-06-18T10:00:00Z",
      "account_handle": "economika",
      "url": "https://x.com/economika/status/1",
      "template": "default_news_card",
      "target_formats": ["vertical_short"],
      "ready_for_publish": true,
      "render_errors": []
    }
  ],
  "invalid_renders": []
}
```

Writes are atomic:

```text
manifest.json.tmp -> manifest.json
```

Generated manifests and render files under `runtime/renders/` are runtime artifacts and must not be committed.
