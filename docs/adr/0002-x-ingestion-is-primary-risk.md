# ADR 0002: X Ingestion Is Primary Risk

## Status

Accepted

## Context

The MVP depends on discovering high-signal posts from X, but the available ingestion options are unstable or operationally fragile.

## Decision

X ingestion is the primary MVP risk. Twikit, Nitter, and snscrape will not be treated as a stable foundation. The planned proof of concept is Playwright sync with a persistent browser profile, manual login, and visible DOM extraction.

## Consequences

- The first implementation phase after the skeleton should validate X ingestion before broadening the product.
- The repository must not add Playwright or browser automation in the skeleton PR.
- Browser profiles, cookies, tokens, and debug output must remain local and ignored.
