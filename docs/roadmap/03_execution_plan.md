# Execution Plan

## Phase A - Stabilize Current MVP

Goal: make the smallest reliable manual/RSS -> AI -> render -> review -> Hub path explicit.

Scope:
- Document and validate health checks for CentralAIService and CentralPublishingHub.
- Keep current GUI running.
- Use manual links and RSS as primary MVP inputs.

Non-goals:
- Moving modules into `app/`.
- Fixing every X/Twikit issue.
- Reworking Tkinter layout.

Acceptance criteria:
- Manual links and RSS are documented as reliable paths.
- X/Twikit and Nitter failures do not block MVP definition.
- The next coding PR is small and testable.

## Phase B - Discovery Cleanup

Goal: separate discovery sources from scoring, fallback and logging.

Scope:
- Introduce `DiscoverySource.scan(context)`.
- Implement ManualLinkSource and NewsRSSSource first.
- Treat TwikitSource and NitterSource as optional enrichers.
- Keep current `ViralScout.scan(...)` wrapper available.

Non-goals:
- Perfect X scraping.
- Replacing all GUI discovery calls at once.

Acceptance criteria:
- Manual/RSS scan works without cookies.
- Twikit failure produces concise warnings and does not prevent RSS candidates.
- Tests cover source ordering and fallback.

## Phase C - AI Contract Cleanup

Goal: route AI generation through a stable CentralAIService client contract.

Scope:
- Make `core.ai_handler` a compatibility adapter.
- Use `services.central_ai_client.CentralAIClient` internally.
- Define one draft response shape for GUI callers.

Non-goals:
- Prompt redesign.
- New AI provider support.

Acceptance criteria:
- GUI no longer depends on fragile tuple unpacking internally.
- Existing tests cover draft parsing and failure fallback.

## Phase D - Publishing E2E

Goal: validate EconomikaNoticias -> CentralPublishingHub publish intent using `video_path`.

Scope:
- Confirm `/api/v1/publish` payload shape.
- Normalize targets in one place.
- Remove local temporary-host assumptions from the active path.

Non-goals:
- Direct platform API publishing inside EconomikaNoticias.
- Universal scheduling.

Acceptance criteria:
- One approved item sends one Hub payload.
- Payload includes `account_id`, `video_path`, `caption`, `title`, `targets`, `publish_mode`.
- Hub owns public media hosting.

## Phase E - Local State/Persistence

Goal: replace scattered JSON state with a small SQLite store.

Scope:
- Track candidates, review decisions, render artifacts and publish attempts.
- Keep import from current JSON as optional migration.

Non-goals:
- Multi-user database.
- Cloud persistence.

Acceptance criteria:
- Restarting the GUI preserves candidate/review/publish status.
- JSON history remains readable until migration is complete.

## Phase F - GUI Thinning

Goal: reduce `main.py` by moving workflow logic behind stable wrappers.

Scope:
- Move orchestration into app modules after contracts are stable.
- Keep Tkinter widgets mostly unchanged.
- Replace direct legacy calls panel by panel.

Non-goals:
- Major visual redesign.
- Framework migration.

Acceptance criteria:
- `main.py` mostly wires UI events to orchestration calls.
- Existing GUI workflows still run.

## Phase G - CI/Tests Hardening

Goal: make regressions cheap to catch.

Scope:
- Add focused tests around discovery, AI contract, render contract and Hub payloads.
- Reduce noisy warnings where practical.
- Keep CI install clear and minimal.

Non-goals:
- Full GUI automation.
- Live API tests in default CI.

Acceptance criteria:
- `pytest -q` passes locally and in CI.
- Warning count is documented or reduced.

## Phase H - Packaging/Run Scripts

Goal: one documented command per service and clear preflight checks before GUI work.

Scope:
- Add scripts or documented commands for CentralAIService, CentralPublishingHub and EconomikaNoticias.
- Add health-check command(s).
- Remove hidden Sentinel/bootstrap assumptions from docs and runtime expectations.

Non-goals:
- Installer packaging.
- Cloud deployment migration.

Acceptance criteria:
- A new developer can start all required services from docs.
- GUI preflight reports missing CentralAIService or CentralPublishingHub clearly.

## Recommended Next Coding PR

Recommended next PR: `feat/discovery-source-abstraction`.

Reason: discovery is the smallest blocker before the reliable MVP path. Manual links and RSS can be made first-class without touching render, CentralAIService, Hub publishing or the GUI layout. This PR should introduce `Candidate`, `DiscoveryContext`, `DiscoverySource`, `ManualLinkSource` and `NewsRSSSource`, then adapt `ViralScout` behind a compatibility wrapper.

