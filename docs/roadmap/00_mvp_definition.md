# MVP Definition

## Product Goal

EconomikaNoticias MVP is a local editorial workstation that turns a candidate news item into a reviewed short-form video and sends a publishing intent to CentralPublishingHub.

The app should be reliable when X/Twikit and Nitter are broken. The guaranteed MVP path is manual links plus configured RSS/news sources, not automated X scraping.

## In Scope

### Input

- Manual pasted links.
- RSS/news fallback from `config/news_sources.json`.
- Optional X/Twikit discovery when it works.

### Processing

- Extract a news/candidate object from a link or RSS entry.
- Generate a script, headline, caption, source metadata and trim hints through CentralAIService.
- Render a local vertical video artifact.
- Present the candidate, copy and rendered video for human review in the GUI.

### Publishing

- Send a publish intent to CentralPublishingHub.
- CentralPublishingHub owns temporary hosting and platform-specific publishing.
- MVP targets:
  - `youtube_shorts`
  - `instagram_reel`
  - `instagram_story`
  - `instagram_feed` as planned / `NOT_IMPLEMENTED` until the Hub supports it end to end.

## Out Of Scope

- Perfect X scraping.
- Depending on Nitter for the happy path.
- Universal scheduling.
- Direct publication from EconomikaNoticias.
- Moving the whole product to cloud.
- Large Tkinter visual refactors.
- Replacing the current GUI before the MVP path is stable.

## MVP Success Criteria

- A user can start CentralAIService, CentralPublishingHub and EconomikaNoticias locally with documented commands.
- A manual link can be processed into a draft.
- RSS fallback can produce candidates when X/Nitter fail.
- A draft can be reviewed by a human before publishing.
- A local video can be rendered and its path passed to CentralPublishingHub.
- CentralPublishingHub receives one publish payload with normalized targets.
- YouTube Shorts and Instagram Reel/Story are validated either against real APIs or documented dry-run/mock modes.

