# Target Architecture

## Direction

EconomikaNoticias should become a local editorial app. It discovers candidates, helps an editor review them, renders video locally, and sends a publish intent to CentralPublishingHub.

CentralAIService owns AI generation. CentralPublishingHub owns temporary hosting and platform publication.

## Proposed Package Shape

```text
EconomikaNoticias/
  app/
    gui/
    discovery/
    render/
    review/
    orchestration/
  core/                  # legacy during transition
  services/
    central_ai_client.py
    publishing_hub_client.py
  storage/
    sqlite_store.py
  config/
    settings.py
    news_sources.json
  docs/roadmap/tickets/
```

## Module Responsibilities

### `app/discovery`

- Convert manual links and feed entries into normalized `Candidate` objects.
- Run reliable sources first.
- Treat Twikit/Nitter as optional enrichers.
- Keep scoring separate from source scanning.

### `app/orchestration`

- Coordinate candidate -> AI draft -> render artifact -> review -> publish intent.
- Own use-case level workflows that the GUI can call.
- Hide legacy function shapes from UI panels.

### `app/render`

- Wrap current `core.generator` behavior behind a stable contract.
- Return explicit artifact metadata, including `video_path`, duration, format and generated caption/title fields.

### `app/review`

- Represent human approval/rejection and edits.
- Keep review decisions independent from render mechanics and publishing mechanics.

### `services`

- Keep thin, testable clients for CentralAIService and CentralPublishingHub.
- Normalize URLs and auth headers in one place.
- Expose health checks used by run scripts and GUI preflight.

### `storage`

- Start with a SQLite store for candidates, decisions, renders and publish attempts.
- Keep JSON import/migration out of the critical path until the MVP works.

## Transition Rules

- No big bang rewrite.
- Keep `main.py` operational throughout the transition.
- Extract by small tickets with tests.
- Each extraction should leave a compatibility wrapper for current GUI callers.
- Prefer stable contracts before moving large code blocks.
- Do not make Twikit or Nitter a hard dependency for MVP success.

## Target Flow

1. Source produces `Candidate` objects.
2. Orchestrator asks CentralAIService for draft content.
3. Renderer creates local artifact and returns `RenderArtifact`.
4. GUI review accepts, edits or rejects.
5. Publisher sends one payload to CentralPublishingHub.
6. Hub uploads/hosts media and publishes to targets.

