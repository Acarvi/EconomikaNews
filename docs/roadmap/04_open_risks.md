# Open Risks

## X/Twikit May Remain Broken

Twikit depends on private X behavior and cookies. Errors such as `Couldn't get KEY_BYTE indices`, `urls`, lookup failures, 403 and 404 can return at any time. X discovery must be optional for MVP.

## Nitter Is Not Reliable

Nitter instances often fail with no entries, 403, DNS problems or stale feeds. Nitter should be treated as a best-effort enrich path, not a required fallback.

## Meta API Constraints

Instagram Reel, Story and Feed behavior depends on Meta Graph API permissions, account type, media processing state, token freshness and format rules. Feed/Post support may remain `NOT_IMPLEMENTED` until the Hub proves the target.

## Local `video_path` Assumption

Passing `video_path` works only if CentralPublishingHub can access that path. If the Hub runs on another machine or container, Hub must either receive an upload or own a shared-volume/public-hosting strategy.

## YouTube OAuth And Tokens

YouTube Shorts publishing requires OAuth credentials and token persistence. Token storage must be audited and kept out of git.

## GUI Legacy Coupling

`main.py` currently couples widgets, long-running threads, discovery, render, AI and publishing behavior. Small compatibility wrappers are safer than direct rewrites.

## Secrets And Cookies

Tracked or local cookie/token material is a security risk. Observed items include `config/x.com_cookies.json`, `config/x.com_cookies.txt`, browser profile data under `user_data_scraper/`, and token-related utility scripts.

## Generated Files In Git

Tracked `__pycache__` files and mojibake paths increase repo noise and can hide real changes. Cleanup should be handled in a separate PR to avoid mixing docs, security and behavior changes.

## Warning Noise

High warning volume can obscure meaningful regressions. CI hardening should reduce warning noise after the MVP path is stable.

