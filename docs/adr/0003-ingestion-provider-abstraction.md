# ADR 0003: Ingestion provider abstraction

## Status

Accepted

## Context

X ingestion is the highest product risk for EconomikaNews. Access patterns, unofficial endpoints, browser behavior, account limits, pricing, and terms can all change independently of the rest of the product.

Browser automation is useful for diagnostics and emergency fallback validation, but it is not the core architecture. Treating browser login or Playwright automation as the primary ingestion path would make the product too fragile and too coupled to local browser state.

## Decision

EconomikaNews core code must depend on normalized ingestion models, not vendor-specific payloads. Ingestion providers are responsible for converting source-specific responses into shared models before downstream dashboard, scoring, rendering, review, queueing, or publishing code sees them.

The provider boundary will support multiple strategies:

- A fake provider for tests and local development.
- A free experimental provider that may use unofficial/internal X APIs later and may be unstable.
- Paid providers or an official API provider later if they become the better tradeoff.
- A Playwright or browser diagnostic provider only if it is needed as fallback tooling.

## Consequences

Provider implementations can change without forcing dashboard, scoring, rendering, or publishing changes. This protects the product from X ingestion volatility and lets the team evaluate free, paid, official, unofficial, and diagnostic strategies behind one stable contract.

The first real provider candidate after this abstraction is a free experimental X internal API research spike.
