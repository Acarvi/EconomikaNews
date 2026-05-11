# MVP-007 - Render Pipeline Contract

## Goal

Expose a clean render contract:

```python
render_post(post_draft) -> rendered_video_path
```

## Current State

Rendering is handled by `core/generator.py` functions and orchestration in `main.py`.

## Proposed Change

Add a wrapper that accepts a structured draft and delegates to the existing image/video render functions.

## Files Likely Affected

- `core/generator.py`
- `main.py`
- tests for render contract with mocks

## Implementation Steps

1. Define expected `post_draft` fields.
2. Implement render wrapper without changing render internals.
3. Map image/video inputs to existing generator functions.
4. Return final path and update local state later.

## Acceptance Criteria

- Existing render functions remain compatible.
- New wrapper has one stable entry point.
- Returned file path is absolute or clearly rooted.
- Video target remains 1080x1920.

## Manual Test Plan

Render one image post and one video post through the wrapper.

## Risks

MoviePy/FFmpeg behavior can be slow and environment-dependent.

## Out of Scope

Visual redesign of reel templates.

