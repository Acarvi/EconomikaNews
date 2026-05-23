# EN-027 Runtime Local Config Loader

## Objective

Remove repeated giant environment variable setup for local X internal ingestion scripts by adding an ignored runtime YAML config and loader.

## Scope

- Add a placeholder-only committed example config.
- Add runtime config dataclasses, YAML loading, and env application helpers.
- Add an interactive helper that creates `runtime/config/x_internal.local.yaml`.
- Add `--config` support to the X internal probe scripts.
- Let the multi-account probe resolve accounts, database, and optional output paths from runtime config while preserving CLI and environment precedence.
- Add tests for config safety, loader behavior, and script argument integration.

## Out of Scope

- Dashboard
- Scheduler
- Rendering or publishing
- AI captions or generation
- Queue integration
- Provider behavior changes
- Committed runtime config
- Committed secrets

## Acceptance Criteria

- `config/x_internal.example.yaml` exists and contains placeholders only.
- `runtime/config/x_internal.local.yaml`, `runtime/secrets`, `.env`, and database files are not tracked.
- `load_runtime_config()` raises clear errors for missing, invalid, or non-dict YAML files.
- Unknown config keys are tolerated.
- Missing `x_internal` and `paths` sections are tolerated.
- `apply_runtime_config_to_env()` only sets missing X internal env vars and does not overwrite existing env vars.
- `X_INTERNAL_USER_ID` is set only when config `user_id` is non-empty.
- `scripts/x_fetch_accounts_probe.py`, `scripts/x_internal_probe.py`, and `scripts/x_download_media_probe.py` accept `--config`.
- `scripts/x_fetch_accounts_probe.py` preserves CLI explicit argument priority, env `ECONOMIKA_DB_PATH` priority, and no-file behavior when `--output-json` is omitted.

## Validation Commands

```powershell
python -m compileall app tests scripts
python -m pytest -p no:cacheprovider --basetemp=runtime/pytest-tmp
git status --short
git ls-files runtime "*/x_headers.json" x_headers.json .env ".env.*" "*.db"
```
