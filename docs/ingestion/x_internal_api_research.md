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
- `X_INTERNAL_HEADERS_FILE`: path to a local ignored JSON object of DevTools-captured headers.
- `X_INTERNAL_TIMELINE_TEMPLATE_URL`: reusable captured `UserTweets` URL used for userId replacement.
- `X_INTERNAL_USER_ID`: numeric X user id to inject into `X_INTERNAL_TIMELINE_TEMPLATE_URL`.
- `X_INTERNAL_USER_LOOKUP_TEMPLATE_URL`: reusable captured `UserByScreenName` URL used for one-handle userId lookup.
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

## Local workflow

1. Capture a `UserTweets` request in DevTools Network while logged in locally.
2. Create a local headers file with `python scripts/create_x_headers_file.py`.
3. Run the probe with `powershell -ExecutionPolicy Bypass -File scripts/create_x_probe_env.ps1`.
4. If successful, expect `post_count > 0` and `errors []`.

`runtime/secrets/x_headers.json` must never be committed. Keep cookies, tokens, auth headers, and raw debug payloads out of chats, issues, PRs, logs, and committed files.

Known limitation: handle -> userId resolution is not implemented. EN-023 should solve that before broader account coverage.

## Parameterized timeline URL

To reuse a captured `UserTweets` URL for a different X user id, set `X_INTERNAL_TIMELINE_TEMPLATE_URL` to the full DevTools URL and set `X_INTERNAL_USER_ID` to the desired numeric X user id. The provider parses the template URL, replaces `variables.userId`, and re-encodes `variables`, `features`, and `fieldToggles` before sending the request.

```powershell
$env:X_INTERNAL_HEADERS_FILE="runtime/secrets/x_headers.json"
$env:X_INTERNAL_TIMELINE_TEMPLATE_URL="https://x.com/i/api/graphql/<queryId>/UserTweets?variables=..."
$env:X_INTERNAL_USER_ID="123456789"
python scripts\x_internal_probe.py --handle wallstwolverine --lookback-hours 24 --print-json
```

Unknown query parameters from the captured URL are currently ignored during template rebuilding. If not using the lookup flow below, `X_INTERNAL_USER_ID` must be supplied manually.

## Handle to userId lookup

To resolve one handle without manually setting `X_INTERNAL_USER_ID`, capture a `UserByScreenName` request from DevTools. Open the profile, open DevTools Network, filter for `UserByScreenName`, and copy the full request URL.

```powershell
$env:X_INTERNAL_HEADERS_FILE="runtime/secrets/x_headers.json"
$env:X_INTERNAL_USER_LOOKUP_TEMPLATE_URL="https://x.com/i/api/graphql/<queryId>/UserByScreenName?variables=..."
$env:X_INTERNAL_TIMELINE_TEMPLATE_URL="https://x.com/i/api/graphql/<queryId>/UserTweets?variables=..."
python scripts\x_internal_probe.py --handle wallstwolverine --lookback-hours 24 --resolve-user-id --print-json
```

This still resolves one handle only. Multi-account scanning is EN-024.

## Media extraction and download probe

Timeline responses can include image/video media under tweet entities. The provider exposes image URLs and video MP4 URLs when present, and the probe can optionally include media details in JSON output.

Required local env vars are `X_INTERNAL_HEADERS_FILE`, `X_INTERNAL_TIMELINE_TEMPLATE_URL`, and either `X_INTERNAL_USER_LOOKUP_TEMPLATE_URL` or `X_INTERNAL_USER_ID`.

```powershell
python scripts\x_internal_probe.py --handle wallstwolverine --resolve-user-id --print-json --show-media
python scripts\x_download_media_probe.py --handle wallstwolverine --resolve-user-id --limit-posts 3 --dry-run
python scripts\x_download_media_probe.py --handle wallstwolverine --resolve-user-id --limit-posts 3
```

Downloads are written under `runtime/downloads/x` by default. `runtime/` is ignored and downloads must never be committed.

## Multi-account fetch probe

For practical scanning of multiple accounts, a config-driven probe fetches a set of configured handles sequentially, deduplicates posts, and ranks candidates by engagement.

### Config format

Configure accounts in a YAML file (e.g. `config/accounts.example.yaml`):

```yaml
accounts:
  - handle: wallstwolverine
    category: politics
    weight: 1.0
  - handle: example_account
    category: economics
    weight: 1.2
```

### Ingestion execution

Run the multi-account fetch probe with:

```powershell
# Setup headers and templates as environment variables
$env:X_INTERNAL_HEADERS_FILE="runtime/secrets/x_headers.json"
$env:X_INTERNAL_TIMELINE_TEMPLATE_URL="https://x.com/i/api/graphql/.../UserTweets?..."
$env:X_INTERNAL_USER_LOOKUP_TEMPLATE_URL="https://x.com/i/api/graphql/.../UserByScreenName?..."

# Run the sequential scan
python scripts\x_fetch_accounts_probe.py --accounts-file config/accounts.example.yaml --resolve-user-id --include-media --output-json
```

Arguments:
- `--accounts-file`: path to the configuration file (default: `config/accounts.example.yaml`)
- `--lookback-hours`: lookback window in hours (default: `24`)
- `--limit-per-account`: limit of posts to retrieve per account (default: `20`)
- `--resolve-user-id`: enable dynamic username to userId lookup
- `--include-media`: output media URLs/previews
- `--output-json`: path to write JSON candidates list (defaults to `runtime/outputs/x_candidates.json` if flag is passed without argument)

*Note: This is still sequential and not scheduled. EN-026 should add storage or queue.*

## Known failure modes

- `401`: missing, expired, or invalid credentials.
- `403`: forbidden request, bad CSRF token, or blocked endpoint.
- `429`: rate limited.
- Expired cookies.
- Challenge or login verification response.
- Changed `queryId` or `docId`.
- Changed JSON schema.
- Cloud IP blocking.

## Safety

Use low volume, read-only probing only. Do not take actions from this provider. Do not bypass captchas, challenges, account locks, login verification, rate limits, or other protections. This spike is for one-account research, not 500-account scanning.

## Next decision

If the probe can fetch one account reliably, the next PR should extract a stable parser from observed redacted schemas. If it cannot fetch reliably, choose the browser extension path or a paid provider instead.
