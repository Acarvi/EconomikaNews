from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.storage.sqlite_review_state import get_review_states

DEFAULT_CANDIDATES_FILE = Path("runtime/outputs/x_candidates.json")
DEFAULT_DB_PATH = Path("runtime/economika_news.db")
DEFAULT_OUTPUT_JSON = Path("runtime/outputs/approved_candidates.json")


def load_candidates_payload(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Candidates file not found: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid candidates JSON in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid candidates payload in {path}: expected top-level JSON object.")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError(f"Invalid candidates payload in {path}: expected 'candidates' list.")

    return payload


def build_approved_export(payload: dict, db_path: Path, candidates_file: Path) -> dict:
    candidates = payload.get("candidates", [])
    post_ids = [str(c.get("post_id")) for c in candidates if isinstance(c, dict) and c.get("post_id")]
    states = get_review_states(db_path, post_ids)

    approved_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        post_id = candidate.get("post_id")
        if not post_id:
            continue
        state = states.get(str(post_id))
        if not state or state.get("status") != "approved":
            continue

        enriched = dict(candidate)
        enriched["review_status"] = "approved"
        enriched["reviewed_at"] = state.get("reviewed_at")
        enriched["review_note"] = state.get("note")
        enriched["review_updated_at"] = state.get("updated_at")
        approved_candidates.append(enriched)

    return {
        "source_candidates_file": str(candidates_file),
        "db_path": str(db_path),
        "approved_count": len(approved_candidates),
        "candidates": approved_candidates,
    }


def write_approved_export(export_payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(export_payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export dashboard-approved candidates to JSON.")
    parser.add_argument("--candidates-file", default=str(DEFAULT_CANDIDATES_FILE))
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    args = parser.parse_args()

    candidates_file = Path(args.candidates_file)
    db_path = Path(args.db_path)
    output_json = Path(args.output_json)

    summary: dict[str, Any] = {
        "source_candidates_file": str(candidates_file),
        "db_path": str(db_path),
        "output_json": str(output_json),
        "approved_count": 0,
        "errors": [],
    }

    try:
        payload = load_candidates_payload(candidates_file)
        export_payload = build_approved_export(payload, db_path=db_path, candidates_file=candidates_file)
        write_approved_export(export_payload, output_json)
        summary["approved_count"] = export_payload["approved_count"]
    except (FileNotFoundError, ValueError) as exc:
        message = str(exc)
        summary["errors"].append(message)
        print(message, file=sys.stderr)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 1
    except Exception as exc:
        message = f"Unexpected export error: {exc}"
        summary["errors"].append(message)
        print(message, file=sys.stderr)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 1

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
