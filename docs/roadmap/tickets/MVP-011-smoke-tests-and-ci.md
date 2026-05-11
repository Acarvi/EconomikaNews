# MVP-011 - Smoke Tests And CI

## Goal

Add minimal tests to protect the ecosystem MVP boundaries.

## Current State

The repo has pytest tests, but central service clients, Sentinel optional behavior, and target contract parsing need focused coverage.

## Proposed Change

Add smoke tests for imports, clients, parsing, payload construction, SQLite state, and secret hygiene.

## Files Likely Affected

- `tests/`
- `services/`
- state/storage modules
- CI config if present

## Implementation Steps

1. Test imports without SentinelAPI.
2. Mock CentralAIService health and draft responses.
3. Mock CentralPublishingHub health and publish responses.
4. Test platform normalization.
5. Test draft response parsing.
6. Test publish payload construction.
7. Test SQLite store creation and update.
8. Add no-secrets tracked-file check.

## Acceptance Criteria

- Tests cover:
  - importing modules without SentinelAPI
  - health check clients mocked
  - platform normalization
  - draft response parsing
  - publish payload construction
  - SQLite store
  - no secrets in tracked files
- CI can run without sibling repos.

## Manual Test Plan

Run `python -m pytest` from a clean checkout without CentralAIService, CentralPublishingHub, or SentinelAPI checked out as siblings.

## Implementation Notes

- Added focused regression tests for Sentinel-free imports, platform normalization, server datetime parsing, and publisher payload construction.
- Publisher payload tests mock hub health, Catbox upload, and `requests.post`, so they do not call external services.
- Added GitHub Actions CI on Python 3.11 with server requirements, `py_compile`, and `pytest -q`.
- CI is designed to run without `GEMINI_API_KEY`, publishing credentials, sibling service checkouts, or SentinelAPI.
- `pytest.ini` now focuses collection on the MVP regression tests added here; existing legacy tests need separate cleanup before re-enabling.

## Risks

Existing tests may assume local files/cookies/secrets.

## Out of Scope

Full E2E tests against live Instagram or YouTube.
