# Text Card Renderer

The text-card renderer is the first local rendering step. It reads render input JSON files and creates one static PNG news card for each ready post.

```text
runtime/render_inputs/<post_id>.json
  -> scripts/render_text_cards.py
  -> runtime/renders/<post_id>/card.png
```

## Usage

Default command:

```powershell
python scripts\render_text_cards.py
```

Input:

```text
runtime/render_inputs/<post_id>.json
```

Output:

```text
runtime/renders/<post_id>/card.png
```

CLI options:

- `--input-dir`: render input directory. Default: `runtime/render_inputs`.
- `--output-dir`: render output directory. Default: `runtime/renders`.
- `--overwrite`: replace existing `card.png` files with atomic PNG swaps.
- `--dry-run`: print the summary without creating directories or writing files.
- `--width`: output width. Default: `1080`.
- `--height`: output height. Default: `1920`.
- `--background`: fixed internal background style. Default: `dark`.
- `--limit`: render at most this many input files.

Missing input directories exit successfully with a zero summary. Invalid individual JSON files are recorded in `errors` and do not stop later files from rendering.

## Scope

This step produces static PNG cards only. It uses deterministic local layout, local render input JSON, and Pillow. It does not make network calls.

The card includes:

- Source or account label.
- Headline.
- Body text when it differs from the headline.
- Engagement metrics when available.
- URL or post ID footer.
- A simple `Media attached: N` label when media is present.

## Out Of Scope

- Video rendering.
- ffmpeg or moviepy.
- Text-to-speech.
- AI generation.
- Publishing.
- Scheduling.
- Dashboard changes.
- Media compositing.
- Custom committed fonts.

## Limitations

The layout is intentionally basic. It does not composite attached images or videos yet, and it uses Pillow's available font fallback rather than committed font files. Generated files under `runtime/renders/` are runtime artifacts and must not be committed.
