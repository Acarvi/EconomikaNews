# X to Reel MVP

This script is the fastest way to generate preview reels from X accounts without the full pipeline overhead. It serves as an MVP for immediate visual output.

## Providers

The script uses a provider strategy to fetch posts:
- **Manual JSON**: The guaranteed working provider in this MVP. The MVP acceptance path is `--input-json`.
- **X API, gallery-dl, and browser cookies**: Best-effort/planned stubs in this MVP and may fail clearly if credentials or dependencies are missing.

## Command Examples

### Manual JSON Mode (Fallback)

```powershell
py scripts\make_reels_from_x.py --input-json samples\x_posts_sample.json --top 3 --overwrite --open
```

### Account Mode

```powershell
py scripts\make_reels_from_x.py --accounts juanrallo --max-posts-per-account 20 --top 3 --overwrite --open
```

## Output

Generated outputs are placed in `runtime/x_reels/<date>/<post_id>/`.
Outputs include:
- `reel.mp4`: Vertical 9:16 MP4.
- `card.png`: Generated Pillow visual card.
- `caption.txt`: Caption text.
- `metadata.json`: Parsed metadata.
- `preview_report.md`: Markdown report for the specific reel.
- `manifest.json`: Global run manifest.
