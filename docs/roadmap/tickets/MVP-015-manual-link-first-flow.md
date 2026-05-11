# MVP-015 Manual Link First Flow

## Goal

Make manual pasted links the guaranteed MVP path.

## Why

Manual links allow editorial work to continue even when X account scanning, Twikit cookies or Nitter feeds fail.

## Scope

- Treat manual links as first-class candidates.
- Avoid requiring X account scan metadata for manual flow.
- Support news links and X links in the same input box.
- Preserve history/reprocess controls where applicable.

## Non-goals

- Full article scraping.
- Full UI redesign.
- Replacing render or publish logic.

## Implementation Steps

1. Normalize pasted lines into candidate records.
2. Use URL hash ids for non-X links.
3. Use tweet id extraction only when the URL is actually an X/Twitter URL.
4. Ensure manual candidates can reach AI generation with description/title fallback.
5. Add tests for manual news URL and manual X URL behavior.

## Acceptance Criteria

- A pasted news URL can proceed to AI generation without X cookies.
- A pasted X URL can proceed even if account scanning fails.
- Empty/invalid lines are skipped with clear feedback.

## Validation Commands

```bash
pytest -q tests/test_fallback.py tests/test_funcionalidades_core.py
pytest -q
```

