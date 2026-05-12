# MVP-011 Smoke Tests and CI

## Goal

Keep the MVP from regressing at import, compile, test and obvious-secret boundaries.

## Why

The previous CI only compiled a small subset of modules and ran tests. EconomikaNoticias has several entry points (`main.py`, `server.py`, core modules and service clients), so CI should catch broken imports and accidental secrets before review.

## Scope

- Compile `server.py`, `main.py`, `core/viral_scout.py` and `core/publisher.py`.
- Run `pytest -q`.
- Add smoke imports for `main`, `server`, `core.viral_scout`, `core.publisher`, `services.publishing_hub_client` and `config.settings`.
- Add a lightweight `git grep` secret scan for obvious API key/token patterns.

## Implementation Notes

- CI now checks imports, compile, tests, and obvious secrets.
- `pytest-asyncio` is installed in CI so async tests run with the same marker support as local validation.
- Dependency split is still debt: `requirements-dev.txt` can later own pytest tooling, while CI temporarily installs pytest packages directly.

## Validation Commands

```bash
python -m py_compile server.py main.py core/viral_scout.py core/publisher.py
pytest -q
```
