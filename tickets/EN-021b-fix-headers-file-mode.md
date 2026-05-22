# EN-021b Fix X internal headers-file mode

## Objective

Bring the validated X internal API headers-file mode fix into `main` so local probes can use a full DevTools headers JSON file from ignored runtime secrets without requiring separate `X_AUTH_TOKEN` and `X_CT0` environment variables.

## Scope

- Allow `X_INTERNAL_HEADERS_FILE` to supply request headers from a readable JSON object.
- Require `X_INTERNAL_TIMELINE_URL` in both headers-file mode and minimal-env mode.
- Keep minimal-env mode requiring `X_AUTH_TOKEN` and `X_CT0`.
- Validate the headers file without crashing on missing files, invalid JSON, non-object JSON, or non-string keys/values.
- Preserve environment overrides for authorization, CSRF token, user agent, and cookie.
- Add regression tests using an injected opener so tests do not make network calls.
- Document the local validation result without secrets or raw output.

## Out of scope

- Multi-account scanning.
- Handle to `userId` resolution.
- Scheduler integration.
- SQLite storage.
- Dashboard work.
- Render or publishing integration.
- Browser automation or Playwright.
- Committing cookies, tokens, headers, `.env` files, or runtime secrets.

## Acceptance criteria

- When `X_INTERNAL_HEADERS_FILE` is set, the provider requires `X_INTERNAL_TIMELINE_URL` but does not require `X_AUTH_TOKEN` or `X_CT0`.
- When `X_INTERNAL_HEADERS_FILE` is not set, the provider requires `X_AUTH_TOKEN`, `X_CT0`, and `X_INTERNAL_TIMELINE_URL`.
- Invalid headers-file inputs return an `invalid_config` error result instead of raising.
- Header values from the file are used for the request.
- `X_BEARER_TOKEN`, `X_CT0`, `X_USER_AGENT`, and `X_COOKIE_STRING` override file/default headers.
- Tests do not make real network calls.
- No runtime secrets or environment files are tracked.

## Validation commands

```powershell
python -m compileall app tests scripts
python -m pytest
git status --short
```

## Manual validation summary

Local validation of full headers-file mode succeeded using `runtime/secrets/x_headers.json`. The probe returned 21 posts for one account with no errors, including text, post ids, urls, media counts, likes, replies, reposts, and views.

No Playwright or browser automation was used. Secrets remained in ignored runtime files and must not be committed.
