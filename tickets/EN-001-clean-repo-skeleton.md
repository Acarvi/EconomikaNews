# EN-001 Clean Repo Skeleton

## Objective

Create a minimal repo skeleton, config examples, tests, and CI for the clean rebuild.

## Scope

- Add a minimal standard-library Python app entry point.
- Add example configuration files with non-secret local defaults.
- Add a smoke test for the skeleton and required files.
- Add CI for compile and pytest validation.
- Add gitignore rules for local runtime artifacts and development caches.

## Out of Scope

- X ingestion implementation.
- Playwright installation or automation.
- FastAPI or dashboard implementation.
- SQLite schema or persistence logic.
- Rendering, AI metadata generation, or publishing integration.

## Acceptance Criteria

- `app/main.py` defines a callable `main()` function.
- `config/accounts.example.yaml` and `config/settings.example.yaml` exist and contain only examples/defaults.
- `tests/test_skeleton.py` verifies the skeleton files.
- `.github/workflows/ci.yml` runs compile and pytest on Python 3.11.
- `.gitignore` excludes `.env`, `runtime/`, local databases, caches, virtualenvs, build outputs, and OS metadata.

## Validation Commands

```bash
python -m compileall app tests
python -m pytest
```
