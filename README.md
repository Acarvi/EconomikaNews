# Economica News

Economica News is a local-first rebuild of the EconomikaNews repository: a small product for discovering high-signal economic and political stories, scoring them, generating short-form media candidates, reviewing them, queueing approved posts, and handing publication to the central publishing service.

## Current Status

Post-wipe clean rebuild.

## MVP Flow

discover -> score -> generate -> review -> queue -> publish

## Technical Risk

The biggest technical risk is X ingestion.

## Architecture Rule

Publishing belongs to CentralPublishingHub, not Economica News. This repository may prepare and queue publishing requests, but platform publishing logic must live in the central service.

## First Phases

- Phase 0: skeleton
- Phase 1: X ingestion POC

## Local Commands

```bash
python -m pytest
python -m compileall app tests
```

## Manual X Login

Install Playwright browsers once in your local environment:

```bash
python -m playwright install chromium
```

Diagnostic / fallback-only Playwright Chromium login helper:

```bash
python -m app.discovery.x_browser_source --login
```

Installed Chrome with the isolated runtime profile:

```bash
python -m app.discovery.x_browser_source --login --browser-channel chrome
```

Comet executable with an existing real profile:

```bash
python -m app.discovery.x_browser_source --login --executable-path "C:\Path\To\comet.exe" --user-data-dir "C:\Path\To\User Data" --i-understand-profile-risk
```

By default, this creates ignored local directories under `runtime/browser_profile` and `runtime/debug`. The browser profile may contain login state, so it must stay out of git.

The Playwright login helper is useful for diagnostics and fallback validation, but it is not the primary strategy if it requires closing the user's normal browser first. The intended primary ingestion path will likely use an active-browser extension or local bridge so Comet can stay open.

Using a real browser profile is allowed only for local manual POC. It must never be used in CI or committed. Do not run high-volume automation against a personal X account.

## Commit Hygiene

Do not commit `runtime/`, `.env`, browser profiles, tokens, cookies, outputs, or other local artifacts.
