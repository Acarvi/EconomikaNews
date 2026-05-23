from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

DEFAULT_CANDIDATES_FILE = Path("runtime/outputs/x_candidates.json")
GENERATE_COMMAND = (
    "python scripts\\x_fetch_accounts_probe.py --config "
    "runtime\\config\\x_internal.local.yaml --resolve-user-id --include-media --output-json"
)


@dataclass(frozen=True)
class DashboardFilters:
    account: str | None = None
    only_media: bool = False
    only_new: bool = False
    min_score: float | None = None


def parse_filters(query: str) -> DashboardFilters:
    params = parse_qs(query, keep_blank_values=False)
    account = params.get("account", [""])[0].strip() or None
    only_media = params.get("only_media", [""])[0].lower() == "true"
    only_new = params.get("only_new", [""])[0].lower() == "true"

    min_score: float | None = None
    raw_min_score = params.get("min_score", [""])[0].strip()
    if raw_min_score:
        try:
            min_score = float(raw_min_score)
        except ValueError:
            min_score = None

    return DashboardFilters(
        account=account,
        only_media=only_media,
        only_new=only_new,
        min_score=min_score,
    )


def load_candidates_payload(candidates_file: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not candidates_file.exists():
        return None, (
            f"Candidates file not found: {candidates_file}. Generate it with: "
            f"{GENERATE_COMMAND}"
        )

    try:
        payload = json.loads(candidates_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"Candidates file is not valid JSON: {exc}"
    except OSError as exc:
        return None, f"Could not read candidates file: {exc}"

    if not isinstance(payload, dict):
        return None, "Candidates file must contain a JSON object."
    if not isinstance(payload.get("candidates", []), list):
        return None, "Candidates file has an invalid 'candidates' field."
    return payload, None


def filter_candidates(
    candidates: list[dict[str, Any]],
    filters: DashboardFilters,
) -> list[dict[str, Any]]:
    filtered = candidates
    if filters.account:
        account = filters.account.lower()
        filtered = [
            candidate
            for candidate in filtered
            if str(candidate.get("account_handle", "")).lower() == account
        ]
    if filters.only_media:
        filtered = [
            candidate
            for candidate in filtered
            if int(candidate.get("media_count") or len(candidate.get("media") or [])) > 0
        ]
    if filters.only_new:
        filtered = [candidate for candidate in filtered if candidate.get("is_new") is True]
    if filters.min_score is not None:
        filtered = [
            candidate
            for candidate in filtered
            if _as_float(candidate.get("score")) >= filters.min_score
        ]
    return filtered


def render_dashboard(candidates_file: Path, query: str = "") -> str:
    filters = parse_filters(query)
    payload, error = load_candidates_payload(candidates_file)
    if error:
        return _page(
            "Economika Candidates",
            f"""
            <section class="notice">
              <h2>No candidates loaded</h2>
              <p>{html.escape(error)}</p>
              <pre>{html.escape(GENERATE_COMMAND)}</pre>
            </section>
            """,
        )

    assert payload is not None
    candidates = [c for c in payload.get("candidates", []) if isinstance(c, dict)]
    visible_candidates = filter_candidates(candidates, filters)
    accounts = sorted(
        {
            str(candidate.get("account_handle"))
            for candidate in candidates
            if candidate.get("account_handle")
        }
    )

    summary = _render_summary(payload, candidates)
    controls = _render_filters(filters, accounts)
    table = _render_table(visible_candidates)
    return _page(
        "Economika Candidates",
        f"""
        <header>
          <h1>Economika Candidates</h1>
          <p>{html.escape(str(candidates_file))}</p>
        </header>
        {summary}
        {controls}
        <section>
          <h2>Candidates ({len(visible_candidates)})</h2>
          {table}
        </section>
        """,
    )


def run_server(candidates_file: Path, host: str, port: int) -> None:
    handler_cls = make_handler(candidates_file)
    server = ThreadingHTTPServer((host, port), handler_cls)
    print(f"Dashboard running at http://{host}:{port}")
    print(f"Reading candidates from {candidates_file}")
    server.serve_forever()


def make_handler(candidates_file: Path) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib API
            parsed = urlparse(self.path)
            if parsed.path != "/":
                self.send_error(404, "Not found")
                return

            body = render_dashboard(candidates_file, parsed.query).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            print(f"{self.address_string()} - {format % args}")

    return DashboardHandler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local read-only candidates dashboard.")
    parser.add_argument(
        "--candidates-file",
        default=str(DEFAULT_CANDIDATES_FILE),
        help="Path to x_candidates.json.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", type=int, default=8088, help="Port to bind.")
    args = parser.parse_args(argv)

    run_server(Path(args.candidates_file), args.host, args.port)
    return 0


def _render_summary(payload: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    values = {
        "account_count": payload.get("account_count", _account_count(candidates)),
        "total_posts": payload.get("total_posts", len(candidates)),
        "unique_posts": payload.get("unique_posts", len(candidates)),
        "new_candidates": payload.get("new_candidates", _new_count(candidates)),
        "already_seen_candidates": payload.get(
            "already_seen_candidates",
            _already_seen_count(candidates),
        ),
        "errors": len(payload.get("errors") or []),
    }
    cards = "\n".join(
        f"""
        <div class="metric">
          <span>{html.escape(label)}</span>
          <strong>{html.escape(str(value))}</strong>
        </div>
        """
        for label, value in values.items()
    )
    errors = payload.get("errors") or []
    error_block = ""
    if errors:
        error_items = "".join(f"<li>{html.escape(str(error))}</li>" for error in errors)
        error_block = f"<details class=\"errors\"><summary>Errors</summary><ul>{error_items}</ul></details>"
    return f"<section class=\"summary\">{cards}</section>{error_block}"


def _render_filters(filters: DashboardFilters, accounts: list[str]) -> str:
    account_options = ['<option value="">All accounts</option>']
    for account in accounts:
        selected = " selected" if account == filters.account else ""
        escaped = html.escape(account)
        account_options.append(f'<option value="{escaped}"{selected}>{escaped}</option>')

    only_media_checked = " checked" if filters.only_media else ""
    only_new_checked = " checked" if filters.only_new else ""
    min_score = "" if filters.min_score is None else html.escape(str(filters.min_score))
    return f"""
    <form class="filters" method="get" action="/">
      <label>Account
        <select name="account">{''.join(account_options)}</select>
      </label>
      <label class="check"><input type="checkbox" name="only_media" value="true"{only_media_checked}> Media</label>
      <label class="check"><input type="checkbox" name="only_new" value="true"{only_new_checked}> New</label>
      <label>Min score
        <input type="number" step="any" name="min_score" value="{min_score}">
      </label>
      <button type="submit">Apply</button>
      <a href="/">Clear</a>
    </form>
    """


def _render_table(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return '<p class="empty">No candidates match these filters.</p>'

    rows = "\n".join(_render_row(candidate) for candidate in candidates)
    return f"""
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>score</th>
            <th>account_handle</th>
            <th>is_new</th>
            <th>media_count</th>
            <th>views</th>
            <th>likes</th>
            <th>reposts</th>
            <th>replies</th>
            <th>text_prefix</th>
            <th>open tweet</th>
            <th>media</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """


def _render_row(candidate: dict[str, Any]) -> str:
    metrics = candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {}
    url = str(candidate.get("url") or "")
    tweet_link = _external_link(url, "open") if url else ""
    media_html = _render_media(candidate)
    escaped_cells = [
        html.escape(_format_score(candidate.get("score"))),
        html.escape(str(candidate.get("account_handle") or "")),
        html.escape(str(candidate.get("is_new") if "is_new" in candidate else "")),
        html.escape(str(candidate.get("media_count") or len(candidate.get("media") or []))),
        html.escape(str(metrics.get("views") or 0)),
        html.escape(str(metrics.get("likes") or 0)),
        html.escape(str(metrics.get("reposts") or 0)),
        html.escape(str(metrics.get("replies") or 0)),
        html.escape(str(candidate.get("text_prefix") or "")),
        tweet_link,
        media_html,
    ]
    return "<tr>" + "".join(f"<td>{cell}</td>" for cell in escaped_cells) + "</tr>"


def _render_media(candidate: dict[str, Any]) -> str:
    media_items = candidate.get("media") if isinstance(candidate.get("media"), list) else []
    rendered: list[str] = []
    for item in media_items:
        if not isinstance(item, dict):
            continue
        media_type = str(item.get("media_type") or "").lower()
        if media_type == "image":
            url = str(item.get("preview_url") or item.get("url") or "")
        else:
            url = str(item.get("url") or item.get("preview_url") or "")
        if not url:
            continue
        if media_type == "image":
            escaped_url = html.escape(url, quote=True)
            rendered.append(
                f'<a href="{escaped_url}" target="_blank" rel="noopener noreferrer">'
                f'<img src="{escaped_url}" alt="candidate media"></a>'
            )
        else:
            rendered.append(_external_link(url, media_type or "media"))
    return " ".join(rendered)


def _external_link(url: str, label: str) -> str:
    return (
        f'<a href="{html.escape(url, quote=True)}" target="_blank" '
        f'rel="noopener noreferrer">{html.escape(label)}</a>'
    )


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #17202a;
      --muted: #5e6b78;
      --line: #d9dee5;
      --accent: #126a72;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header, section, form {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 16px 20px;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }}
    h1 {{ margin: 0; font-size: 24px; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    p {{ margin: 6px 0 0; color: var(--muted); }}
    a {{ color: var(--accent); }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 10px;
    }}
    .metric, .notice, .errors {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
    }}
    .metric strong {{ display: block; margin-top: 4px; font-size: 22px; }}
    .filters {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: end;
    }}
    label {{ display: grid; gap: 4px; color: var(--muted); }}
    .check {{ display: flex; gap: 6px; align-items: center; color: var(--text); }}
    input, select, button {{
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      color: var(--text);
      padding: 0 10px;
    }}
    button {{
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
      cursor: pointer;
    }}
    .table-wrap {{
      overflow-x: auto;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
    }}
    table {{ width: 100%; border-collapse: collapse; min-width: 1100px; }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-size: 12px;
      background: #eef2f4;
      position: sticky;
      top: 0;
    }}
    td:nth-child(9) {{ min-width: 260px; max-width: 420px; }}
    img {{
      max-width: 92px;
      max-height: 72px;
      object-fit: cover;
      border-radius: 4px;
      border: 1px solid var(--line);
    }}
    pre {{
      white-space: pre-wrap;
      background: #eef2f4;
      border-radius: 6px;
      padding: 10px;
    }}
    .empty {{ color: var(--muted); }}
  </style>
</head>
<body>{body}</body>
</html>"""


def _account_count(candidates: list[dict[str, Any]]) -> int:
    return len({c.get("account_handle") for c in candidates if c.get("account_handle")})


def _new_count(candidates: list[dict[str, Any]]) -> int:
    return sum(1 for c in candidates if c.get("is_new") is True)


def _already_seen_count(candidates: list[dict[str, Any]]) -> int:
    return sum(1 for c in candidates if c.get("is_new") is False)


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _format_score(value: Any) -> str:
    score = _as_float(value)
    if score.is_integer():
        return str(int(score))
    return f"{score:.2f}"
