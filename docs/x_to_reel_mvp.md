# X to Reel MVP

This script is the fastest way to generate preview reels from X accounts without the full pipeline overhead. It serves as an MVP for immediate visual output.

## Providers and Ingestion

The X-to-Reel pipeline now uses a dedicated ingestion adapter to fetch data from real accounts.

To fetch real accounts and generate reels, use the two-step process:

```powershell
py scripts\fetch_x_posts.py --accounts juanrallo --max-posts-per-account 20 --output-json runtime\x_posts\latest_posts.json
py scripts\make_reels_from_x.py --input-json runtime\x_posts\latest_posts.json --top 3 --overwrite --open
```

See [x_ingestion_adapter.md](x_ingestion_adapter.md) for details on setting up providers like `gallery-dl` and `x-api`.

## Command Examples

### Manual JSON Mode (Fallback)

```powershell
py scripts\make_reels_from_x.py --input-json samples\x_posts_sample.json --top 3 --overwrite --open
```

### Fast Generation Pipeline

```powershell
py scripts\fetch_x_posts.py --accounts juanrallo --max-posts-per-account 20 --output-json runtime\x_posts\latest_posts.json
py scripts\make_reels_from_x.py --input-json runtime\x_posts\latest_posts.json --top 3 --overwrite --open
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
