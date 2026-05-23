# Local Candidate Dashboard

The local dashboard is a simple local HTML view over the candidate JSON written by
the X accounts probe. The candidate source JSON stays read-only. Human review state
is stored separately in SQLite, so approving or rejecting a candidate does not
modify `runtime/outputs/x_candidates.json`.

## Usage

1. Generate candidates:

   ```bash
   python scripts\x_fetch_accounts_probe.py --config runtime\config\x_internal.local.yaml --resolve-user-id --include-media --output-json
   ```

2. Start the dashboard:

   ```bash
   python scripts\run_dashboard.py --db-path runtime\economika_news.db
   ```

3. Open:

   ```text
   http://127.0.0.1:8088
   ```

By default the dashboard reads `runtime/outputs/x_candidates.json`. To inspect a
different file:

```bash
python scripts\run_dashboard.py --candidates-file path\to\x_candidates.json
```

The review database defaults to `runtime/economika_news.db`.

Available filters are `account`, `status=all|pending|approved|rejected`,
`only_media=true`, `only_new=true`, and `min_score`.

Each candidate row includes local review controls:

- `Approve`
- `Reject`
- `Reset`

Review actions write only to SQLite and use a `303` redirect back to the current
dashboard view.

## Export Approved Candidates

After reviewing in the dashboard, export only approved candidates:

```bash
python scripts\export_approved_candidates.py --db-path runtime\economika_news.db
```

This writes:

```text
runtime/outputs/approved_candidates.json
```

Only candidates with stored review status `approved` are exported. Pending
(including implicit pending with no row) and rejected candidates are ignored.
The source candidates JSON remains read-only.
