# EN-025 X multi-account fetch probe

## Objective

Add a small config-driven multi-account X ingestion probe that sequentially fetches configured accounts using the validated `XInternalApiProvider` flow, deduplicates posts, scores them by engagement, and outputs a JSON candidate list.

## Scope

- Add PyYAML dependency explicitly to `pyproject.toml`.
- Add YAML configuration example `config/accounts.example.yaml`.
- Add sequential fetching script `scripts/x_fetch_accounts_probe.py` with engagement scoring, deduplication, sorting, and optional media inclusion.
- Implement `--output-json` CLI parameter support (with optional path, defaulting to `runtime/outputs/x_candidates.json` if flag is passed without argument).
- Add no-network tests using pure mocks/fakes in `tests/test_x_fetch_accounts_probe.py`.
- Update documentation in `docs/ingestion/x_internal_api_research.md`.

## Out of scope

- Scheduler.
- SQLite or other persistence storage.
- Dashboard, rendering, or publishing.
- Parallelism or concurrency.
- Media downloads (handled in EN-024).
- Browser automation.
- Committed secrets or runtime files.

## Acceptance criteria

- PyYAML dependency is present in `pyproject.toml`.
- Configuration loads successfully from YAML file.
- Script fetches multiple accounts sequentially and collects posts and errors.
- Posts are deduplicated by `post_id` (preferring the copy with the higher engagement score).
- Scores are calculated via:
  `score = (views + likes*1 + reposts*3 + replies*2) * weight`
- Output candidates are sorted descending by score.
- Output JSON summary follows the exact structure specified in the requirements.
- Tests verify YAML loading, scoring, deduplication, sorting, and optional media and JSON file saving behaviors.
- No network calls are made during tests.
- Secret safety and git-ignore rules are preserved (no runtime/secret/env files committed).

## Validation commands

- `python -m compileall app tests scripts`
- `python -m pytest`
- `git status --short`
- `git ls-files runtime "*/x_headers.json" x_headers.json .env ".env.*"`
