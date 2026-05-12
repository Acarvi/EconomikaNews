# Current State

This document records the observed repository state before the MVP cleanup work. It is intentionally descriptive: no code cleanup is part of this docs PR.

## Files Inspected

- `main.py`
- `server.py`
- `core/viral_scout.py`
- `core/publisher.py`
- `core/generator.py`
- `core/ai_handler.py`
- `services/central_ai_client.py`
- `services/publishing_hub_client.py`
- `config/settings.py`
- `config/news_sources.json`
- `docs/roadmap/*`
- `tests/*`
- `.github/workflows/*`
- `requirements*.txt`

## Discovery

- `core/viral_scout.py` mixes discovery, scoring, fallback handling, history persistence, cookie handling, media extraction and logging.
- Twikit/X is brittle and has explicit recovery paths for errors such as `KeyError`, `urls`, `key_byte`, `indices`, 403, 404 and lookup failures.
- Nitter is implemented as RSS instance rotation, but expected failure modes include no entries, 403 and DNS/network failures.
- RSS/news fallback exists and is viable for MVP. It reads `config/news_sources.json`, creates stable `news-*` ids and computes a recency score.
- Discovery logs are still noisy and include low-level retry/debug messages.
- The GUI invokes `ViralScout.scan(...)` directly and caches rich results in `main.py`.
- Manual links already exist as an input path in `main.py`, but they are still framed around tweet processing and X history checks.

## AI

- `core/ai_handler.py` calls CentralAIService directly through `requests`.
- `services/central_ai_client.py` exists and provides a cleaner wrapper for health, draft and refine endpoints.
- The current GUI expects the legacy tuple shape returned by `generate_content_ai`.
- `main.py` has at least one call path that appears out of sync with the current 9-value tuple contract.
- CentralAIService should remain the only AI generation service for MVP.

## Publishing

- `services/publishing_hub_client.py` exists and normalizes `/api/v1` base URLs.
- `core/publisher.py` builds publish payloads with `video_path`, `caption`, `title`, `targets`, `publish_mode`, and transitional compatibility fields.
- GUI publish actions already delegate through `core.publisher` toward CentralPublishingHub.
- `core.publisher.upload_to_temporary_host` still exists as a legacy Catbox fallback helper.
- EconomikaNoticias should not own Catbox, Gofile or Uguu uploads in the target design. Hub owns temporary hosting.
- `server.py` still contains a Render/FastAPI backend with viral scan and queue behavior. For the target MVP, this is legacy/local-adjacent until clarified against CentralPublishingHub.

## GUI

- `main.py` is too large and owns GUI, orchestration, preflight checks, rendering callbacks, cloud sync, discovery and publish actions.
- Panels still call legacy functions directly.
- Stable wrappers are needed before thinning the GUI.
- The current GUI should remain operational while extraction happens ticket by ticket.

## Render

- `core/generator.py` renders local vertical video artifacts with MoviePy/Pillow and FFmpeg.
- It writes to `core/output` via `OUTPUT_DIR`.
- Render accepts image or video inputs and exposes practical knobs such as subtitle/headline position and trim times.
- The contract for produced artifacts is implicit and should be documented before moving code.

## Persistence

- Current persistence is JSON/local state:
  - processed/rejected history under `data/`
  - pending tweets / queue in `server.py`
  - failed posts in `data/failed_posts.json`
- SQLite is planned, but not required before the first reliable MVP E2E.

## Testing And CI

- CI exists in `.github/workflows/ci.yml`.
- CI installs `requirements-server.txt`, compiles `server.py` and `core/publisher.py`, then runs `pytest -q`.
- Tests cover imports, security, settings/service clients, publisher payloads, platform normalization, server datetime handling and ViralScout resilience.
- Warnings are high in local runs and should be cleaned after the core MVP flow is stable.

## Repository Hygiene Findings

- `SentinelAPI`, `activate_security` and `bootstrap` were not found in tracked source during this inspection.
- `debug_x_response.txt` exists as an untracked local file and should not be committed.
- `config/x.com_cookies.json` is tracked and appears to contain X cookie material. It should be removed from git history or rotated as a separate security task.
- A mojibake-looking tracked path exists: `config/accounts.json...` with extra non-ASCII suffix bytes.
- Several `__pycache__/*.pyc` files are tracked.
- Local generated files/directories are present: `logs/`, `services/logs/`, `user_data_scraper/`, `__pycache__/`, `.pytest_cache/`.
- `.pytest_cache/` produced permission warnings during local inspection.
- `tools/test_token.py` exists and should be audited for token handling.

