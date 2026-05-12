# MVP-015 Browser X Source Extraction

## Goal

Make `ECONOMIKA_X_SOURCE=browser` and `ECONOMIKA_X_SOURCE=auto` useful in practice by extracting recent X profile tweets from browser-rendered profile pages.

## Why

Twikit remains fragile and often breaks on schema changes such as `KEY_BYTE` and `urls`. A browser-backed X source gives us a second implementation path for the same product: discover viral tweets from configured X accounts.

## Scope

- Use Playwright or an existing browser/session path to open `https://x.com/{screen_name}`.
- Reuse local cookies or profile data when available.
- Extract tweet/status URLs, visible text, metrics and timestamps when visible.
- Normalize extracted rows into `DiscoveryCandidate`.
- Keep browser source bounded with timeouts, per-account limits and total limits.
- Make `auto` switch from Twikit to browser after circuit-breaker degradation.

## Non-goals

- Replacing Twikit immediately.
- Making browser scraping perfect or exhaustive.
- Running real browser sessions in CI.

## Implementation Notes

- `BrowserXSource` is experimental but now performs real profile extraction instead of only parsing fake HTML in tests.
- Playwright is imported lazily.
- Existing cookies from `config/x.com_cookies.txt`, `config/x.com_cookies.json` or a local `user_data_scraper/` profile can be reused when available.
- Browser candidates without metrics still return with a low score and `score_source=browser_no_metrics`.

## Validation Commands

```bash
python -m py_compile server.py main.py core/viral_scout.py core/publisher.py services/discovery/x_sources.py
pytest -q
```
