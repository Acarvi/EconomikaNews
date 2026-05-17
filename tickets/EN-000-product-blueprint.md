# EN-000 Product Blueprint

## Objective

Commit `PRODUCT_BLUEPRINT.md` as the source of truth for product direction and architecture.

## Scope

- Add `PRODUCT_BLUEPRINT.md` to the repository.
- Treat it as the canonical reference for the clean rebuild.
- Keep the blueprint separate from implementation tickets and code.

## Out of Scope

- Implementing scraping or ingestion.
- Implementing Playwright workflows.
- Implementing dashboard, rendering, AI, SQLite, or publishing logic.
- Moving archived code back into the active product.

## Acceptance Criteria

- `PRODUCT_BLUEPRINT.md` exists at the repository root.
- The README points to the clean rebuild status and product intent.
- No runtime artifacts or secrets are introduced.

## Validation Commands

```bash
python -m compileall app tests
python -m pytest
```
