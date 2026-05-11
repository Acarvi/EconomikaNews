# MVP-012 - End-To-End Checklist

## Goal

Create a manual checklist for proving the ecosystem MVP.

## Current State

The flow exists in pieces, but there is no single operator checklist that validates EconomikaNoticias plus the two central hubs.

## Proposed Change

Use this checklist as the manual MVP gate.

## Files Likely Affected

- `docs/roadmap/`
- `docs/DEVELOPER.md`

## Implementation Steps

1. Keep checklist in docs.
2. Update it as tickets are implemented.
3. Use it before tagging MVP builds.

## Acceptance Criteria

Checklist:

- [ ] Levantar CentralAIService
- [ ] Levantar CentralPublishingHub
- [ ] Configurar `.env` de EconomikaNoticias
- [ ] Crear draft desde media local
- [ ] Generar IA via CentralAIService
- [ ] Renderizar video
- [ ] Revisar texto
- [ ] Publicar Instagram Reel
- [ ] Publicar Instagram Story
- [ ] Publicar Instagram Feed/Post si aplica
- [ ] Publicar YouTube Shorts
- [ ] Ver estado en EconomikaNoticias
- [ ] Ver job/resultados en CentralPublishingHub

## Manual Test Plan

Run the checklist exactly once with mocked publishing, then once with real platform credentials when ready.

## Risks

Live platform tests may fail because of credentials, quotas, media rules, or temporary hosting availability.

## Out of Scope

Automating all external platform tests in CI.

