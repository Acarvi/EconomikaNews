# EN-021c Finalize X internal spike cleanup

## Goal

Bring the safe remaining EN-021 helper, docs, and test improvements into `main` without widening scope into EN-022.

## In scope

- Local helper for creating `runtime/secrets/x_headers.json`.
- Local PowerShell probe helper with placeholders only.
- Concise headers-file workflow documentation.
- `INVALID_CONFIG` error-kind cleanup.
- No-network tests for helper importability, secret-safe helper contents, headers-file config behavior, and tracked runtime files.

## Out of scope

- Handle to `userId` resolution.
- Dynamic timeline URL generation.
- Multi-account scanning.
- Scheduler, SQLite, dashboard, rendering, or publishing.
- Browser automation.
- Paid providers.
