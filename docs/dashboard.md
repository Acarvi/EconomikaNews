# Local Candidate Dashboard

The local dashboard is a read-only HTML view over the candidate JSON written by
the X accounts probe. It does not read runtime secrets, headers, config files, or
database tables.

## Usage

1. Generate candidates:

   ```bash
   python scripts\x_fetch_accounts_probe.py --config runtime\config\x_internal.local.yaml --resolve-user-id --include-media --output-json
   ```

2. Start the dashboard:

   ```bash
   python scripts\run_dashboard.py
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

Available filters are `account`, `only_media=true`, `only_new=true`, and
`min_score`.
