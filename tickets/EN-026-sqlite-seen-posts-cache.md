# EN-026 SQLite seen-posts cache

## Objective

Add a minimal SQLite seen-post cache for X candidates so repeated multi-account fetches can identify new vs already-seen posts.

## Scope

- Add a local SQLite storage module `app/storage/sqlite_seen_posts.py` with standard functions to initialize the database, query seen status, and conflict-safe upsert post metadata.
- Default database path is `runtime/economika_news.db`, with overrides supported via `ECONOMIKA_DB_PATH` environment variable or `--db-path` CLI option.
- Integrate with `scripts/x_fetch_accounts_probe.py` by adding `--db-path`, `--no-cache`, and `--only-new` CLI arguments.
- Mark candidates with `"is_new": true/false` when caching is active.
- Support `--only-new` to output only unseen candidates.
- Add flag compatibility checking: return exit code 1 if both `--no-cache` and `--only-new` are passed.
- Output JSON summary includes cache fields `cache_enabled`, `db_path`, `new_candidates`, and `already_seen_candidates`.
- Create new test file `tests/test_sqlite_seen_posts.py` and extend `tests/test_x_fetch_accounts_probe.py` using non-network, isolated, temporary databases.
- Ensure runtime database is ignored under Git.

## Out of scope

- Scheduler.
- Dashboard.
- Rendering or publishing.
- AI captioning.
- Media downloading.
- Parallelism.
- Cloud DB.
- Migrations framework beyond minimal init.
- Committed runtime DB/secrets.

## Acceptance criteria

- `app/storage/sqlite_seen_posts.py` successfully creates `source_posts_seen` table if missing.
- `upsert_seen_posts` uses `ON CONFLICT` update to retain `first_seen_at` while updating score, media count, last seen time, text prefix, and URL.
- `--no-cache --only-new` exits with code 1 and error `"Error: --only-new requires cache enabled"`.
- When cache is active, all deduplicated candidates are upserted to the DB, even if `--only-new` filters output.
- When `--no-cache` is passed, no database file is created or written, candidates omit `is_new`, and top-level JSON fields are `null`.
- Tests run purely with isolated temporary SQLite instances and never create or touch files in `runtime/economika_news.db`.
- No network calls are made during tests.
- All code complies with type check/compilation and all pytest checks pass.

## Validation commands

- `python -m compileall app tests scripts`
- `python -m pytest -p no:cacheprovider --basetemp=runtime/pytest-tmp`
- `git status --short`
- `git ls-files runtime "*/x_headers.json" x_headers.json .env ".env.*" "*.db"`
