# Economica News

Economica News is a local-first rebuild of the EconomikaNews repository: a small product for discovering high-signal economic and political stories, scoring them, generating short-form media candidates, reviewing them, queueing approved posts, and handing publication to the central publishing service.

## Current Status

Post-wipe clean rebuild.

## MVP Flow

discover -> score -> generate -> review -> queue -> publish

## Technical Risk

The biggest technical risk is X ingestion.

## Ingestion Direction

Economica News core code uses an ingestion provider abstraction. Dashboard, scoring, rendering, review, queueing, and publishing code should depend on normalized ingestion models rather than X-specific or vendor-specific payloads.

The first real provider candidate is EN-021: a free experimental X internal API research spike. This path may use unofficial/internal X APIs and should be treated as unstable until proven otherwise.

Playwright/browser login is diagnostic and fallback tooling only. It is not the production ingestion path and should not be treated as core architecture.

## Architecture Rule

Publishing belongs to CentralPublishingHub, not Economica News. This repository may prepare and queue publishing requests, but platform publishing logic must live in the central service.

## First Phases

- Phase 0: skeleton
- Phase 1: ingestion provider abstraction
- Phase 2: EN-021 X internal API research spike

## Local Commands

```bash
python -m pytest
python -m compileall app tests
```

## Commit Hygiene

Do not commit `runtime/`, `.env`, browser profiles, tokens, cookies, outputs, or other local artifacts.
