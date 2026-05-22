# EN-022 Parameterize X internal timeline URLs

## Objective

Allow a captured X internal `UserTweets` DevTools URL to be reused with a manually supplied numeric X user id.

## Scope

- Parse captured `UserTweets` timeline URLs into a reusable template.
- Replace `variables.userId` dynamically from `X_INTERNAL_USER_ID`.
- Preserve existing full `X_INTERNAL_TIMELINE_URL` fallback behavior.
- Add no-network tests for parsing, rebuilding, provider integration, and secret-file hygiene.
- Document the manual userId workflow.

## Out of scope

- Handle to `userId` resolution.
- Multi-account scanning.
- Scheduler, SQLite, dashboard, rendering, or publishing.
- Browser automation.
- Paid providers.
- Committed secrets or runtime files.

## Acceptance criteria

- Template mode uses `X_INTERNAL_TIMELINE_TEMPLATE_URL` plus `X_INTERNAL_USER_ID`.
- Full URL mode still works unchanged.
- Invalid template JSON returns a clear `invalid_config` provider error.
- Tests perform no network requests.
- No runtime/secrets files are tracked.

## Validation commands

- `python -m compileall app tests scripts`
- `python -m pytest`
- `git status --short`
- `git ls-files runtime "*/x_headers.json" x_headers.json .env ".env.*"`
