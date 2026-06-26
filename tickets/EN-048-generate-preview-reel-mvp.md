# EN-048 Generate Preview Reel MVP

## Objective

Create a one-command preview reel workflow that lets an operator immediately watch a usable vertical MP4 from an existing ready publish packet.

## Scope

- Add `scripts/generate_preview_reel.py`.
- Run the existing local pipeline before selecting a publish packet.
- Select a requested `--post-id` or the first ready packet from `runtime/publish_queue/manifest.json`.
- Copy `reel.mp4`, `caption.txt`, `metadata.json`, and `card.png` when available into `runtime/preview_reels/<post_id>/`.
- Generate `preview_report.md` with source attribution, upload readiness, caption text, and a manual upload checklist.
- Support `--overwrite`, `--open`, `--no-open-video`, `--no-open-folder`, `--summary-json`, `--python-executable`, `--continue-on-error`, and `--duration-seconds`.
- Add docs and no-network regression tests.

## Out of scope

- TikTok, Instagram, or YouTube APIs.
- OAuth.
- Browser automation publishing.
- Scheduling.
- AI caption generation or LLM rewriting.
- Audio, music, voiceover, or subtitles.
- Dashboard changes.
- Database changes.
- Cloud storage.
- Committed runtime files.

## Regression tests

- Creates the preview directory and copies the video to `reel.mp4`.
- Copies caption, metadata, and card preview when available.
- Works without a card path and emits a warning.
- Selects the first ready packet when `--post-id` is omitted.
- Selects the requested ready packet when `--post-id` is provided.
- Fails clearly when the requested post is not found or no ready packets exist.
- Preserves existing preview files unless `--overwrite` is provided.
- Generates a report with source handle, source URL, caption, and checklist.
- Opens video and folder when requested, with suppression flags for each.
- Converts open failures into warnings.
- Writes and prints the expected JSON summary paths.
- Forwards `--duration-seconds` only to the video export stage.

## CI/CD checks

- `py -m compileall app tests scripts`
- `py -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- `py -m pytest -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- `py scripts\generate_preview_reel.py --overwrite`
- `py scripts\generate_preview_reel.py --overwrite --open`
- `Get-ChildItem runtime\preview_reels -Recurse`
- Watch `runtime/preview_reels/<post_id>/reel.mp4`.

## Senior review notes

- Risk assessment: Low-to-medium. The feature is copy/report/open orchestration on top of existing local artifacts, with no platform publishing or external API writes.
- Regression confidence: Covered by no-network unit tests for selection, copying, overwrite behavior, open behavior, and summary output.
- Follow-ups: Add audio, subtitles, richer reel templates, or platform upload flows only in separate tickets.

## Rollback notes

- Revert the preview script, docs, tests, and runner duration passthrough.
- Data/runtime impact: Delete local `runtime/preview_reels/` folders if desired. No persisted remote state is created.
