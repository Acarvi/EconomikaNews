# Branch Cleanup Recommendation

Generated during MVP stabilization. Do not delete remote branches automatically unless their PR status is known and agreed.

## Safe To Delete Remote Branch: PR Merged

- `feat/mvp-013-stable-discovery-sources`
- `feat/mvp-014-robust-x-discovery-and-ci`
- `feat/mvp-015-browser-x-source-extraction`
- `fix/restore-x-viral-tweet-discovery`

## Keep: Open PR

- `fix/browser-x-source-windows-event-loop` - keep unless PR #12 is confirmed merged.
- `chore/mvp-operational-cleanup` - current MVP stabilization PR branch.

## Keep: Development Unless Explicitly Retired

- `development`

## Investigate: Branches Without Confirmed PR State

- `docs/ecosystem-mvp-roadmap`
- `docs/mvp-cleanup-roadmap`
- `feat/mvp-002-settings-and-service-clients`
- `feat/mvp-005-economika-publishing-hub-contract`
- `feat/news-rss-fallback-for-viral-scout`
- `fix/04-scraper-investigation-and-fallback`
- `fix/phase-0-1-security-and-runtime`
- `fix/remove-sentinel-and-add-regression-ci`
- `fix/remove-sentinel-gui-bootstrap`
- `fix/viral-scout-twikit-fallback-errors`

