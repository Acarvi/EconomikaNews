# MVP-023 Run Scripts And Healthchecks

## Goal

Provide one command per service and clear health checks before the GUI starts.

## Why

MVP execution needs a predictable local runbook. Hidden service assumptions make debugging slow.

## Scope

- Document or add one command for CentralAIService.
- Document or add one command for CentralPublishingHub.
- Document or add one command for EconomikaNoticias GUI.
- Add explicit health checks before expensive GUI processing.
- No Sentinel.
- No hidden required services except documented ones.

## Non-goals

- Installer packaging.
- Cloud deployment automation.
- Replacing service implementations.

## Implementation Steps

1. Identify actual service startup commands.
2. Add lightweight scripts if missing.
3. Add health-check command(s) for AI and Hub.
4. Ensure GUI preflight checks both required services before processing/publishing.
5. Update README/run docs.

## Acceptance Criteria

- A developer can start each service with one documented command.
- Health check failure is clear and actionable.
- GUI does not imply Sentinel/bootstrap is required.

## Validation Commands

```bash
pytest -q tests/test_settings_and_service_clients.py
pytest -q
```

