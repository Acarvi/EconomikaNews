# MVP-017 Render Contract And Artifacts

## Goal

Define a stable render contract around local video artifacts.

## Why

The renderer works, but its output contract is implicit. Publishing and review need predictable artifact metadata, especially `video_path`.

## Scope

- Define `RenderRequest` and `RenderArtifact`.
- Wrap current `core.generator` functions.
- Include path, duration if available, source media, headline position, subtitle position and generated title/caption references.
- Keep output directory behavior compatible.

## Non-goals

- Rewriting MoviePy rendering.
- Visual redesign of reels.
- Changing FFmpeg acceleration logic.

## Implementation Steps

1. Create a small render adapter module.
2. Map image and video rendering to one request/response shape.
3. Ensure generated files are checked before returning success.
4. Add tests around adapter behavior with mocked generator calls.
5. Document artifact fields in roadmap/contracts.

## Acceptance Criteria

- Review and publishing code can use `RenderArtifact.video_path`.
- Missing output files are reported as render failures.
- Current renderer remains usable from GUI.

## Validation Commands

```bash
pytest -q tests/test_funcionalidades_core.py
pytest -q
```

