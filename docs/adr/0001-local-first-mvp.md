# ADR 0001: Local-First MVP

## Status

Accepted

## Context

The post-wipe rebuild should establish the smallest useful product path without taking on hosting, SaaS, or persistence complexity too early.

## Decision

Economica News will start as a local-first MVP. FastAPI and a simple web UI may be added later. SQLite may be added later. Rendering will run locally. No cloud SaaS is required initially.

## Consequences

- Early development stays easy to run, inspect, and reset.
- Runtime artifacts must stay under ignored local paths.
- Integration points with central services remain explicit instead of being hidden inside platform-specific publishing code.
