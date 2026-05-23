# Ticket Template

## Objective

Describe the intended outcome in one or two concrete sentences.

## Scope

- Itemize what this ticket will change.

## Out of scope

- Itemize what this ticket will not change.

## Regression tests

- List tests to add or update for behavior protection.
- Include critical happy path and at least one edge/failure case.

## CI/CD checks

- `python -m compileall app tests scripts`
- `python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=<threshold> -p no:cacheprovider --basetemp=runtime/pytest-tmp`
- `python -m pytest -q tests`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- List local/manual checks (if any).

## Senior review notes

- Risk assessment:
- Regression confidence:
- Follow-ups:

## Rollback notes

- Revert strategy:
- Data/runtime impact:
