# Economika Noticias

Local editorial workstation for discovering economic/news candidates, generating reviewed short-form scripts, rendering vertical videos and sending publish intents to CentralPublishingHub.

## Quick Start MVP

1. Double click `EconomikaNoticias.bat`.
2. The launcher checks CentralAIService and CentralPublishingHub.
3. The GUI opens.
4. Use manual URLs for reliable MVP flow.
5. Use X Viral Scout for experimental tweet discovery.

Manual URLs are the minimum reliable MVP path. X Viral Scout is the main product discovery direction, but it depends on X availability, configured accounts, and local cookies. RSS is explicitly secondary fallback discovery. BrowserXSource requires Playwright installed locally and is not required for CI.

### X Source Modes

Default:

```powershell
$env:ECONOMIKA_X_SOURCE="twikit"
```

Browser mode:

```powershell
$env:ECONOMIKA_X_SOURCE="browser"
```

Auto mode:

```powershell
$env:ECONOMIKA_X_SOURCE="auto"
```

### Services

CentralAIService:

```text
D:\Scripts\CentralAIService
```

CentralPublishingHub:

```text
D:\Scripts\CentralPublishingHub
```

## MVP Direction

EconomikaNoticias is responsible for:

- discovery/scouting through manual links, RSS/news fallback and optional X/Twikit enrichment
- editorial review in the local GUI
- local render
- sending publish intent payloads to CentralPublishingHub

CentralAIService owns AI generation. CentralPublishingHub owns temporary hosting and platform publishing.

## Roadmap

The active cleanup and MVP execution plan lives in:

- [MVP definition](docs/roadmap/00_mvp_definition.md)
- [Current state](docs/roadmap/01_current_state.md)
- [Target architecture](docs/roadmap/02_target_architecture.md)
- [Execution plan](docs/roadmap/03_execution_plan.md)
- [Open risks](docs/roadmap/04_open_risks.md)
- [Manual E2E checklist](docs/roadmap/05_manual_e2e_checklist.md)
- [Implementation tickets](docs/roadmap/tickets/)

## Current Entry Points

- `main.py`: current Tkinter GUI and local orchestration.
- `server.py`: legacy/Render FastAPI service for scan/queue behavior.
- `core/viral_scout.py`: current discovery/scouting implementation.
- `core/generator.py`: local video render implementation.
- `core/ai_handler.py`: current CentralAIService compatibility adapter.
- `core/publisher.py`: current CentralPublishingHub publishing adapter.
- `services/central_ai_client.py`: CentralAIService client.
- `services/publishing_hub_client.py`: CentralPublishingHub client.

## Quick Validation

```bash
pytest -q
```

