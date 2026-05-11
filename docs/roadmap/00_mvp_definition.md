# Economika Ecosystem MVP Definition

## MVP Goal

The MVP is a functional ecosystem flow where EconomikaNoticias remains the product app for news discovery, local rendering, manual review, and local draft state, while CentralAIService and CentralPublishingHub provide reusable central capabilities over explicit HTTP APIs.

The MVP must prove this end-to-end path:

1. EconomikaNoticias detects or receives a news candidate.
2. EconomikaNoticias downloads or selects media.
3. EconomikaNoticias calls CentralAIService to generate:
   - headline
   - Instagram caption
   - YouTube Shorts title
   - source/fuente
   - suggested segment timestamps when applicable
4. EconomikaNoticias renders a local vertical video at 1080x1920.
5. EconomikaNoticias allows manual review before publishing.
6. EconomikaNoticias sends video, caption, title, account, and targets to CentralPublishingHub.
7. CentralPublishingHub publishes or schedules to:
   - Instagram Reels
   - Instagram Stories
   - Instagram Feed/Post when the media format is valid
   - YouTube Shorts
8. EconomikaNoticias stores local workflow state for drafts and renders.
9. CentralPublishingHub stores publishing and scheduling state.

## Definition of Done

The MVP is done when a local operator can create one reviewed post from a candidate/media item, render the final video locally, submit it to CentralPublishingHub, and see both local draft status and hub publishing status without requiring SentinelAPI or relative imports into sibling repositories.

## Required Architecture Properties

- CentralAIService is the primary AI path.
- CentralPublishingHub is the primary publishing path.
- EconomikaNoticias calls both services over HTTP using explicit environment variables.
- Sibling repository paths are not required for imports, tests, pushes, or normal execution.
- Auto-start of central services is optional developer convenience, not a runtime requirement.
- Secrets stay in environment variables or ignored local files.

## MVP Targets

- `instagram_reel`
- `instagram_story`
- `instagram_feed`
- `youtube_shorts`

## Out Of Scope

- Facebook publishing.
- TikTok publishing.
- Mandatory cloud rendering.
- SentinelAPI as a required dependency.
- Multi-user web app.
- Large visual/UI redesign.
- Massive module moves such as moving `main.py`.
- Rebuilding CentralAIService or CentralPublishingHub from inside EconomikaNoticias.

