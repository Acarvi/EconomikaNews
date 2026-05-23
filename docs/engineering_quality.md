# Engineering Quality Gate

## Purpose

This repository ships product changes behind lightweight but explicit quality gates so we can move fast without regressions.

## Coverage Policy

- Coverage is enforced in CI with `pytest-cov`.
- Initial threshold is intentionally realistic, not 100%.
- Threshold setting rule:
  - If measured coverage is above 85%, set gate to 85%.
  - If measured coverage is 80-85%, set gate to 80%.
  - If measured coverage is below 80%, set gate to measured coverage rounded down by a few points and document a raise plan.
- Raise threshold incrementally as meaningful tests are added for critical paths.
- Current baseline on this branch was `77.58%` (`app` + `scripts`), so CI is set to `75%` to establish a stable gate before raising.

## PR Checklist

- Scope is aligned to ticket objective and out-of-scope items are not included.
- Regression tests added or updated for behavior changes.
- CI passes (compile, tests, coverage gate, tracked artifact scan).
- No runtime/secrets/local artifacts are committed.
- Docs and ticket notes are updated where behavior/process changed.
- Reviewer can explain rollback impact and risk level from PR description.

## Ticket Checklist

- Objective is explicit and testable.
- Scope and out-of-scope are listed.
- Regression tests are identified before implementation.
- CI/CD checks to run are listed.
- Manual validation steps are listed when applicable.
- Senior review notes and rollback notes are captured before close.

## Regression-Test Expectations

- Every behavior change must include regression coverage at the smallest practical level.
- Prefer deterministic unit/integration tests over brittle end-to-end-only checks.
- Tests should cover happy path plus at least one failure/edge path for new logic.
- Avoid low-value tests that assert implementation details without behavior value.

## CI Checks Required Before Merge

- `python -m compileall app tests scripts`
- `python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=<threshold> -p no:cacheprovider --basetemp=runtime/pytest-tmp`
- `python -m pytest -q tests`
- Tracked runtime/secret artifact scan must be clean.

## Secret and Runtime Artifact Rules

Never commit:

- `runtime/`
- `x_headers.json`
- `.env` and `.env.*`
- `*.db`
- generated outputs under `runtime/outputs/`

CI enforces a tracked-file scan to prevent accidental commits.

## Senior Review Checklist

- Change aligns with ticket objective and does not expand hidden scope.
- Tests are meaningful for regression risk, not just coverage count.
- Coverage trend is healthy and threshold policy is respected.
- CI results are clean and reproducible locally.
- Rollback path is clear if issue appears after merge.

## Branching Guidance

Current practical workflow:

- Create feature branches from `main`.
- Open small PRs back to `main`.
- Require senior engineer review before merge.

`development` branch recommendation:

- A `development` branch can be introduced when a staging/deployment workflow exists.
- Until then, using `main` as integration branch is acceptable for solo/local MVP flow.
- This repository does not force migration to `development` yet.
