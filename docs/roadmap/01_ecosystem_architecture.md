# Ecosystem Architecture

## Target Shape

```txt
EconomikaNoticias
  -> CentralAIService
  -> CentralPublishingHub

CentralPublishingHub
  -> Instagram Graph API
  -> YouTube API
```

Communication between repos must be explicit HTTP, configured through environment variables:

```txt
CENTRAL_AI_SERVICE_URL=http://localhost:8080
CENTRAL_PUBLISHING_HUB_URL=http://localhost:8000
ECONOMIKA_ADMIN_API_KEY=...
ECONOMIKA_ACCOUNT_ID=economika
```

Legacy aliases such as `CENTRAL_AI_URL` can remain temporarily for compatibility, but new code should standardize on `CENTRAL_AI_SERVICE_URL`.

## EconomikaNoticias Responsibilities

- Product workflow and operator UI.
- Candidate discovery or candidate intake.
- Media download and selection.
- Local 1080x1920 render pipeline.
- Manual review and editing of headline/caption/title.
- Local draft/render state.
- HTTP clients for CentralAIService and CentralPublishingHub.
- Normalizing Economika-specific draft data into central service payloads.

## Logic That Should Not Live In EconomikaNoticias

- Final reusable AI provider logic, prompt retry strategy, provider failover, and model-level logging.
- Instagram Graph API publishing implementation.
- YouTube OAuth/token handling and upload implementation.
- Central publishing queue, retry policy, and scheduling state.
- Multi-brand credential storage.
- SentinelAPI bootstrap as a hard requirement.

EconomikaNoticias may keep temporary fallback code during migration, but the default path should be central services.

## CentralAIService Responsibilities

- Gemini/OpenRouter/other AI provider integration.
- Prompts and response parsing for reusable AI flows.
- Retries, provider errors, and redacted logs.
- Stable HTTP contracts for draft/refine/generic generation.
- Returning structured content suitable for product apps.

## CentralPublishingHub Responsibilities

- Multi-brand account configuration.
- Instagram Reels, Stories, and Feed/Post publication.
- YouTube Shorts publication.
- Scheduling, queue, retries, and result state.
- Temporary public media hosting when a platform requires a URL.
- Platform-specific validation and error mapping.

## Local Development Mode

Local development should use three independently runnable processes:

```txt
CentralAIService       http://localhost:8080
CentralPublishingHub  http://localhost:8000
EconomikaNoticias     local GUI/CLI/server as needed
```

EconomikaNoticias should fail with a clear health-check error when a required hub is down. It should not import from `../CentralAIService`, `../CentralPublishingHub`, or `../SentinelAPI`.

Auto-start can be kept behind an explicit developer flag, for example `ENABLE_HUB_AUTOSTART=false`, but must not be the default production path.

## Future Production Mode

In production, EconomikaNoticias can run as a product app or local workstation pipeline, while CentralAIService and CentralPublishingHub run as hosted services. The same client code should work by changing URLs and API keys.

