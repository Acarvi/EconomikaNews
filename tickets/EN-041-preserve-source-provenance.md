# EN-041 Preserve Source Provenance

## Objective

Preserve source account handle and source URL from render provenance through video metadata, video manifest entries, and local publish queue packets. Captions should use real source provenance when available instead of falling back to `Fuente: desconocida`.

## Scope

- Add `source_account_handle` and `source_url` to `runtime/videos/<post_id>/video_metadata.json`.
- Preserve `source_account_handle` and `source_url` in `runtime/videos/manifest.json`.
- Support fallback from older metadata via `source_manifest_entry.account_handle` and `source_manifest_entry.url`.
- Update publish queue captions to use `Fuente: @handle` and an `URL:` line when provenance exists.
- Include `source_account_handle` and `source_url` in publish queue packet metadata.
- Add and update no-network tests.
- Update provenance documentation.

## Out of scope

- TikTok, Instagram, or YouTube APIs.
- OAuth.
- Browser automation.
- Scheduling.
- AI caption generation or text rewriting via LLM.
- Audio, subtitles, or animations.
- Dashboard changes.
- Database changes.
- Cloud storage.
- Committed runtime files.

## Regression tests

- Video metadata includes source account handle and URL from render manifest entries.
- Missing provenance writes stable empty values and does not crash.
- Video manifest entries preserve top-level provenance.
- Video manifest entries fall back to nested render manifest provenance.
- Older video metadata without provenance still works.
- Publish queue captions use `Fuente: @handle` when source provenance exists.
- Publish queue captions include `URL:` when source URL exists and omit it when missing.
- Publish queue metadata includes source account handle and URL.
- Missing handle still uses `Fuente: desconocida`.

## CI/CD checks

- `python -m compileall app tests scripts`
- `python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75 -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- `python -m pytest -p no:cacheprovider --basetemp="%TEMP%\economika-pytest-tmp"`
- Confirm tracked secret/runtime artifact scan is clean.

## Manual validation

- `python scripts\export_card_videos.py --overwrite`
- `python scripts\build_video_manifest.py`
- `python scripts\build_publish_queue.py --overwrite`
- `Get-Content runtime\publish_queue\2057499359705813029\caption.txt`
- `Get-Content runtime\publish_queue\2057499359705813029\metadata.json -TotalCount 160`

## Senior review notes

- Risk assessment: low, because this only adds provenance fields and fallback logic to local artifact metadata.
- Regression confidence: high for provenance behavior because tests cover new metadata, fallback metadata, captions, and packet metadata.
- Follow-ups: platform upload integrations can consume the preserved provenance in a later ticket.

## Rollback notes

- Revert strategy: remove the provenance field additions, fallback logic, tests, docs, and ticket.
- Data/runtime impact: runtime artifacts generated before this ticket remain readable; regenerated artifacts will include provenance fields.
