# MVP-006 - Local SQLite State

## Goal

Store local draft, render, and hub job state in SQLite.

## Current State

EconomikaNoticias uses JSON files for processed history, rejected history, pending cloud data, and failed posts. Draft/render state is not modeled as a durable relational workflow.

## Proposed Change

Add SQLite tables for `posts` and `publish_jobs`.

## Files Likely Affected

- `state/` or `storage/`
- `main.py`
- `core/publisher.py`
- `.gitignore`
- tests for persistence

## Implementation Steps

1. Add SQLite connection helper.
2. Add schema initialization.
3. Add CRUD helpers for draft creation, render updates, and publish job updates.
4. Store raw hub response JSON.
5. Ignore local database files in git.

## Acceptance Criteria

Minimum tables:

```sql
posts(
  id TEXT PRIMARY KEY,
  source_url TEXT,
  media_path TEXT,
  rendered_video_path TEXT,
  headline TEXT,
  caption TEXT,
  youtube_title TEXT,
  source TEXT,
  status TEXT,
  created_at TEXT,
  updated_at TEXT
);

publish_jobs(
  id TEXT PRIMARY KEY,
  post_id TEXT,
  hub_job_id TEXT,
  status TEXT,
  raw_response_json TEXT,
  created_at TEXT,
  updated_at TEXT
);
```

## Manual Test Plan

Create a draft, update rendered path, submit a mocked hub response, restart the app, and verify state is still available.

## Risks

Concurrent writes from GUI threads need simple locking or short-lived connections.

## Out of Scope

Multi-user database, hosted database, or migration framework.

