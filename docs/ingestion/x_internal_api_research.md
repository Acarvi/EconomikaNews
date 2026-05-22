# X internal API research

## Purpose

Prototype a free backend-style X ingestion provider that can fetch one account through X internal web API requests using manually supplied local session credentials. This is a research spike, not production ingestion code.

## Why this is experimental/free

X web traffic uses internal GraphQL/API endpoints that can change without notice. Query IDs, document IDs, variables, feature flags, response schemas, rate limits, and account protections may shift independently of EconomikaNews. The upside is that this path may avoid paid provider costs during early research; the downside is instability.

## Required env vars

- `X_AUTH_TOKEN`: local `auth_token` cookie value.
- `X_CT0`: local `ct0` cookie value used as CSRF token.
- `X_INTERNAL_TIMELINE_URL`: copied X timeline endpoint URL from DevTools Network.

Optional env vars:

- `X_BEARER_TOKEN`: bearer token copied from a legitimate web request, if required by the endpoint.
- `X_COOKIE_STRING`: full cookie header. If omitted, the provider constructs a minimal cookie from `X_AUTH_TOKEN` and `X_CT0`.
- `X_USER_AGENT`: browser user agent. If omitted, a conservative browser user agent is used.
- `X_INTERNAL_TIMELINE_VARIABLES`: GraphQL `variables` query value if it is not already present in the copied URL.
- `X_INTERNAL_TIMELINE_FEATURES`: GraphQL `features` query value if it is not already present in the copied URL.

Never commit cookies, tokens, bearer values, auth headers, or raw debug payloads.

## Capturing endpoint details from DevTools Network

1. Open X while logged in.
2. Open DevTools Network.
3. Visit a profile timeline.
4. Find a `GraphQL/UserTweets` or similar timeline request.
5. Copy the request URL and relevant `variables`/`features` query params.
6. Copy only the local cookie values `auth_token` and `ct0` into local environment variables, never into the repo.

If endpoint/query params are unknown, capture:

- Full request URL path including query ID or document ID.
- Query params named `variables`, `features`, and any field toggles.
- Request method.
- Non-secret headers needed for the request to succeed.
- Response status and a redacted structural summary, not the raw payload.

## Known failure modes

- `401`: missing, expired, or invalid credentials.
- `403`: forbidden request, bad CSRF token, or blocked endpoint.
- `429`: rate limited.
- Expired cookies.
- Challenge or login verification response.
- Changed `queryId` or `docId`.
- Changed JSON schema.
- Cloud IP blocking.

## Validated local result

Full headers-file mode was validated locally with secrets kept in `runtime/secrets/x_headers.json`, which must remain ignored. The probe returned 21 posts for one account, including text, post ids, urls, media counts, and engagement metrics. No browser automation or Playwright was used.

This validates feasibility, not production robustness.

Remaining risks:

- `queryId`/`docId` may change.
- Cookies may expire.
- Request is currently tied to captured `userId`/timeline URL.
- Multi-account scanning is not implemented.
- Cloud IP behavior is untested.

## Safety

Use low volume, read-only probing only. Do not take actions from this provider. Do not bypass captchas, challenges, account locks, login verification, rate limits, or other protections. This spike is for one-account research, not 500-account scanning.

## Next decision

If the probe can fetch one account reliably, the next PR should extract a stable parser from observed redacted schemas. If it cannot fetch reliably, choose the browser extension path or a paid provider instead.
