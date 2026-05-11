# MVP-016 Central AI E2E Contract

## Goal

Make CentralAIService the stable AI contract for draft generation and refinement.

## Why

The project already has `services/central_ai_client.py`, but `core/ai_handler.py` still calls endpoints directly and returns a fragile tuple shape to GUI callers.

## Scope

- Define one internal draft object.
- Use `CentralAIClient` from the compatibility adapter.
- Keep current GUI call sites working.
- Document expected CentralAIService endpoints.

## Non-goals

- Prompt rewrite.
- Adding a second AI provider.
- Changing CentralAIService implementation.

## Implementation Steps

1. Define draft response fields: headline, caption, slug, shorts_title, caption_b, source, suggested_location_query, best_segment_start, best_segment_end.
2. Update `core.ai_handler` to call `CentralAIClient`.
3. Return a compatibility tuple only at the outer adapter boundary.
4. Add parsing tests for complete and partial service responses.
5. Add failure tests for service unavailable/rate limited behavior.

## Acceptance Criteria

- GUI callers receive the same data they expect.
- Internal code has a named draft shape.
- CentralAIService URL configuration is read from one settings path.

## Validation Commands

```bash
pytest -q tests/test_settings_and_service_clients.py tests/test_funcionalidades_core.py
pytest -q
```

