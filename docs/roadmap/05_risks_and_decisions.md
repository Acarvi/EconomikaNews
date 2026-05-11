# Risks And Decisions

## Decisions

- CentralAIService is a strategic dependency and is the primary AI path.
- CentralPublishingHub is a strategic dependency and is the primary publishing path.
- SentinelAPI is not part of the MVP dependency chain.
- Cloud rendering is not required for MVP.
- EconomikaNoticias keeps local render ownership.
- Real publishing should live preferably in CentralPublishingHub.
- EconomikaNoticias may keep direct publishing fallback temporarily, but it must not be the main path.
- Catbox/Gofile/Uguu-style temporary hosting is provisional and belongs in CentralPublishingHub when Meta requires public URLs.
- EconomikaNoticias uses SQLite for local draft/render state.
- CentralPublishingHub owns publishing queue, retries, scheduling state, and platform result state.

## Current Contradictions

- `docs/DEVELOPER.md` currently describes `server.py` as the cloud publishing queue, while the corrected architecture says CentralPublishingHub owns publishing queue and retries.
- `utils/network.py` auto-starts sibling repos through relative paths, while the target architecture requires explicit HTTP dependencies.
- `main.py` and `server.py` import Sentinel bootstrap from a sibling repo, while SentinelAPI must not block MVP execution.
- `core/publisher.py` already calls CentralPublishingHub but also contains direct Instagram Graph API code.
- `core/youtube_uploader.py` duplicates a responsibility that exists in CentralPublishingHub.
- CentralAIService current `/v1/analyzer/draft` contract is video-centric, while the target contract is product-level and supports tweet/media metadata.
- CentralPublishingHub current payload uses `platforms`/`shorts_title`; target payload uses `targets`/`title`.

## Risks

- Contract drift between EconomikaNoticias and central services can break the MVP even when each repo works alone.
- Local filesystem paths work only when services share a machine; hosted services need public/signed media URLs.
- Temporary hosting providers can be unreliable or unsuitable for production.
- Instagram Feed/Post has different format rules than Reels and Stories.
- YouTube Shorts classification depends on duration, aspect ratio, and metadata; uploads can succeed but not classify as Shorts.
- Direct fallback paths can hide hub bugs and prolong duplicated logic.
- Current JSON state files can become inconsistent under concurrent server operations.
- Secrets could leak if new config files are tracked without `.gitignore` updates.

## Open Decisions

- Whether CentralAIService should add a new product-level `/v1/analyzer/draft` schema or version it as `/v1/projects/economika/draft`.
- Whether CentralPublishingHub should accept local `media_path` in local dev or require `video_url` always.
- Whether EconomikaNoticias should keep `server.py` after MVP as candidate intake only.
- Whether `CENTRAL_AI_URL` remains as a permanent alias or is deprecated after clients are introduced.

