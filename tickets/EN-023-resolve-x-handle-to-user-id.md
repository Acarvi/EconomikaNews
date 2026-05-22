# EN-023 Resolve X handle to userId

## Objective

Resolve one X handle to a numeric user id through a captured internal `UserByScreenName` GraphQL URL template.

## Scope

- Parse and rebuild `UserByScreenName` URL templates.
- Replace `variables.screen_name` or `variables.screenName` from the requested handle.
- Extract user ids from defensive response shapes.
- Let the X internal provider resolve one handle before building a `UserTweets` template URL.
- Add a probe flag for the one-handle resolver flow.
- Add no-network tests and documentation.

## Out of scope

- Multi-account scanning.
- Scheduler, SQLite, dashboard, rendering, or publishing.
- Browser automation.
- Paid providers.
- Committed secrets or runtime files.
- Captcha, challenge, lock, or rate-limit bypass.

## Acceptance criteria

- Existing manual `X_INTERNAL_USER_ID` mode still works.
- Resolver mode works with `X_INTERNAL_USER_LOOKUP_TEMPLATE_URL` and `X_INTERNAL_TIMELINE_TEMPLATE_URL`.
- Missing lookup/template config returns clear `missing_config` errors.
- User lookup JSON parsing supports `rest_id`, `id`, `legacy.id_str`, and `legacy.user_id_str`.
- Tests do not make network calls.

## Validation commands

- `python -m compileall app tests scripts`
- `python -m pytest`
- `git status --short`
- `git ls-files runtime "*/x_headers.json" x_headers.json .env ".env.*"`
