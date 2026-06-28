# EN-048: X to Reel MVP

## Objective
Build a working MVP command that generates real preview reels from selected X/Twitter accounts to make the app visibly useful.

## Scope
- `make_reels_from_x.py` CLI script
- Manual JSON fallback provider
- Pillow-based text card rendering (ECONOMIKA / ÚLTIMA HORA style)
- MP4 generation using `imageio`/`ffmpeg`
- Caption, metadata, and preview report generation
- Output preview directly using `--open`

## Out of scope
- TikTok/Instagram/YouTube publishing APIs
- OAuth publishing
- Browser automation publishing
- Captcha bypass
- Paywall bypass
- Credential scraping
- LLM rewriting
- Audio/music/voiceover
- Fully polished motion graphics
- Committed runtime files

## Regression tests
No-network tests verify that parsing, ranking, rendering, and file generation work without hitting X APIs.

## CI/CD checks
`py -m pytest --cov=app --cov=scripts` should pass.

## Manual validation
Run `py scripts\make_reels_from_x.py --input-json samples\x_posts_sample.json --top 2 --overwrite --open` and verify watchable MP4.

## Senior review notes
First priority is visible output. Providers are best-effort.

## Rollback notes
Standard git revert, no DB changes required.
