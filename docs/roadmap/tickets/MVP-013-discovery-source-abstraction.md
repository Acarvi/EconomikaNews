# MVP-013 Discovery Source Abstraction

## Goal

Introduce a small discovery source contract so manual links and RSS are reliable MVP inputs, while Twikit and Nitter become optional enrichers.

## Why

`ViralScout` currently mixes source scanning, scoring, fallback behavior, history and logging. This makes X/Twikit failures feel like product failures even when manual/RSS discovery could keep the MVP moving.

## Scope

- Define `Candidate`, `DiscoveryContext` and `DiscoverySource`.
- Add this interface:

```python
class DiscoverySource:
    async def scan(self, context) -> list[Candidate]:
        ...
```

- Implement source classes:
  - `ManualLinkSource`
  - `NewsRSSSource`
  - `TwikitSource`
  - `NitterSource`
- Source priority:
  - Manual + RSS = reliable MVP.
  - Twikit/Nitter = optional enrichers.
- Keep a compatibility adapter for current `ViralScout.scan(...)` callers.

## Non-goals

- Perfect X scraping.
- Removing `ViralScout` in one PR.
- GUI redesign.
- SQLite persistence.

## Implementation Steps

1. Add discovery contract module with dataclasses/protocols.
2. Implement `ManualLinkSource` with deterministic candidate ids.
3. Implement `NewsRSSSource` using `config/news_sources.json`.
4. Wrap existing Twikit/Nitter behavior behind source classes without changing behavior deeply.
5. Add an orchestrator that runs sources in priority order.
6. Update `ViralScout.scan(...)` to delegate where possible while preserving current return dicts.
7. Add tests for source ordering, no-cookie RSS fallback and manual link candidates.

## Acceptance Criteria

- Manual link discovery works without X cookies.
- RSS discovery works without Twikit.
- Twikit/Nitter errors are captured as source warnings, not global failures.
- Existing GUI entry points still work.

## Validation Commands

```bash
pytest -q tests/test_viral_scout_resilience.py tests/test_fallback.py
pytest -q
```

