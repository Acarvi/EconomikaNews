# Text Card Renderer

The text-card renderer is the first local rendering step. It reads render input JSON files and creates one static PNG vertical news card for each ready post.

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

This step produces static PNG cards only. It uses deterministic local layout, local render input JSON, and Pillow. It does not make network calls or change the render input contract.

The visual v2 layout uses a dark premium news-card style for the default `1080x1920` output. The card includes:

- Clear `ECONOMIKA` branding at the top.
- Source or account label as secondary context.
- A deterministic badge: `BREAKING` when the headline/body contains that word, `X SIGNAL` for X-sourced posts, otherwise `NEWS`.
- A dominant wrapped headline with safe truncation for long text.
- Smaller body excerpt text when the body differs from the headline.
- Engagement metrics rendered as separate chips for views, likes, reposts, and replies.
- Compact metric formatting such as `999`, `1.0K`, `8.5K`, and `2.5M`.
- A small score chip when `engagement.score` is present.
- A clean footer containing `post_id` plus the source domain or account handle, avoiding long raw URLs.
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
- Media downloading.
- Custom committed fonts.

## Limitations

The layout is still a local static PNG renderer. It does not composite attached images or videos, generate AI imagery, rewrite text, publish posts, or invoke video tooling such as ffmpeg/moviepy. It uses Pillow's available default/system font fallback rather than committed font files. Generated files under `runtime/renders/` are runtime artifacts and must not be committed.
