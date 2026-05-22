$env:X_INTERNAL_HEADERS_FILE = "runtime/secrets/x_headers.json"
$env:X_INTERNAL_TIMELINE_URL = Read-Host "Paste X_INTERNAL_TIMELINE_URL from DevTools Network"

python scripts\x_internal_probe.py --handle wallstwolverine --lookback-hours 24 --print-json
