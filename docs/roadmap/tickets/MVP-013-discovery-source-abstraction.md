# MVP-013 Discovery Source Abstraction

## Goal

Introduce a small discovery source contract so X/Twitter viral tweet scouting remains the primary MVP discovery path, while manual links and RSS/news are explicit secondary inputs.

## Why

`ViralScout` currently mixes source scanning, scoring, fallback behavior, history and logging. The product still centers on viral tweets from configured X accounts, but failures should be clear and bounded instead of silently replacing X with unrelated RSS/news candidates.

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
  - X/Twitter viral tweets from configured accounts = primary MVP discovery.
  - Manual URLs = user-provided explicit inputs.
  - RSS/news = explicit secondary mode for backup/content research.
  - Mixed mode = X first, RSS/news only if X returns no candidates.
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

- Default discovery mode runs X/Twitter Viral Scout.
- Manual link discovery works without X cookies when selected.
- RSS discovery works without Twikit when selected explicitly.
- Twikit/Nitter errors are captured as source warnings, not global failures.
- Existing GUI entry points still work.

## Validation Commands

```bash
pytest -q tests/test_viral_scout_resilience.py tests/test_fallback.py
pytest -q
```

## Implementation Notes

- Primary MVP discovery source: X/Twitter viral tweets from configured accounts.
- RSS/news: explicit secondary mode, useful for backup/content research, not default.
- Mixed mode: optional fallback where X runs first and RSS/news runs only if X returns no candidates.
- Nitter is best-effort within the X discovery path.
- Circuit breaker avoids wasting time when X schema is broken.
- Defaults: `ECONOMIKA_DISCOVERY_MODE=x` and `ECONOMIKA_ENABLE_X_SCOUT=true`.
- To run RSS manually, set `ECONOMIKA_DISCOVERY_MODE=rss`.

