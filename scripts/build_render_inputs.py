from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def path_for_json(path: Path) -> str:
    return path.as_posix()


def load_bundle_index(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Bundle index file not found: {path}")

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to read bundle index {path}: {exc}") from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid bundle index in {path}: top-level must be a JSON object")

    bundles = payload.get("bundles")
    if bundles is None:
        raise ValueError(f"Invalid bundle index in {path}: missing 'bundles' key")
    if not isinstance(bundles, list):
        raise ValueError(f"Invalid bundle index in {path}: 'bundles' must be a list")

    return payload


def _coerce_score(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _headline_from_text(text_prefix: Any) -> str:
    if not isinstance(text_prefix, str):
        return "Untitled"

    headline = text_prefix.strip()[:100].strip()
    return headline or "Untitled"


def _body_from_text(text_prefix: Any) -> str:
    if not isinstance(text_prefix, str):
        return ""
    return text_prefix


def _normalize_media_files(media_files: Any) -> list[dict]:
    if not isinstance(media_files, list):
        return []

    normalized = []
    for item in media_files:
        if not isinstance(item, dict):
            continue
        normalized.append({
            "index": item.get("index"),
            "filename": item.get("filename") or "",
            "local_path": item.get("local_path") or "",
            "content_type": item.get("content_type"),
            "source_url": item.get("source_url"),
        })
    return normalized


def _normalize_bundle_errors(bundle_errors: Any) -> list:
    if isinstance(bundle_errors, list):
        return bundle_errors
    return []


def build_render_input(bundle: dict) -> dict:
    if not isinstance(bundle, dict):
        raise ValueError("Bundle must be a JSON object")

    post_id = bundle.get("post_id")
    if not post_id:
        raise ValueError("Bundle is missing required 'post_id'")

    text_prefix = bundle.get("text_prefix")
    media_files = _normalize_media_files(bundle.get("media_files", []))
    bundle_errors = _normalize_bundle_errors(bundle.get("bundle_errors", []))
    review_status = bundle.get("review_status")
    ready_for_render = bundle.get("ready_for_render") is True
    render_ready = bool(ready_for_render and review_status == "approved" and post_id)
    notes = []

    if not ready_for_render:
        notes.append("Bundle index ready_for_render is false")
    if review_status != "approved":
        notes.append("Bundle review_status is not approved")
    if bundle_errors:
        notes.append("Bundle has recorded errors")

    return {
        "schema_version": 1,
        "post_id": str(post_id),
        "source": bundle.get("source") or "x",
        "account_handle": bundle.get("account_handle"),
        "url": bundle.get("url"),
        "text": {
            "headline": _headline_from_text(text_prefix),
            "body": _body_from_text(text_prefix),
            "source_text_prefix": text_prefix if isinstance(text_prefix, str) else "",
        },
        "engagement": {
            "score": _coerce_score(bundle.get("score")),
            "metrics": bundle.get("metrics") if isinstance(bundle.get("metrics"), dict) else {},
        },
        "review": {
            "status": review_status,
            "reviewed_at": bundle.get("reviewed_at"),
            "review_note": bundle.get("review_note"),
        },
        "bundle": {
            "bundle_dir": bundle.get("bundle_dir"),
            "metadata_path": bundle.get("metadata_path"),
            "bundle_errors": bundle_errors,
        },
        "media": {
            "has_media": bool(bundle.get("has_media")) or bool(media_files),
            "files": media_files,
        },
        "render": {
            "ready": render_ready,
            "target_formats": ["vertical_short"],
            "template": "default_news_card",
            "language": "en",
            "notes": notes,
        },
        "original_index_bundle": bundle,
    }


def write_render_input_atomically(render_input: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(f"{output_path.name}.tmp")
    tmp_path.write_text(json.dumps(render_input, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(str(tmp_path), str(output_path))


def build_render_inputs(
    index_payload: dict,
    output_dir: Path,
    include_not_ready: bool = False,
    overwrite: bool = False,
    dry_run: bool = False,
    index_file: Path | None = None,
) -> dict:
    bundles = index_payload.get("bundles", [])
    if not isinstance(bundles, list):
        raise ValueError("'bundles' must be a list")

    summary = {
        "index_file": path_for_json(index_file) if index_file is not None else "",
        "output_dir": path_for_json(output_dir),
        "inputs_written": 0,
        "inputs_skipped": 0,
        "skipped_existing": 0,
        "bundles_seen": len(bundles),
        "bundles_included": 0,
        "errors": [],
        "dry_run": dry_run,
        "overwrite": overwrite,
    }

    for position, bundle in enumerate(bundles):
        if not isinstance(bundle, dict):
            summary["errors"].append(f"Bundle at index {position} must be a JSON object")
            continue

        if bundle.get("ready_for_render") is not True and not include_not_ready:
            summary["inputs_skipped"] += 1
            continue

        try:
            render_input = build_render_input(bundle)
        except ValueError as exc:
            summary["errors"].append(f"Bundle at index {position}: {exc}")
            summary["inputs_skipped"] += 1
            continue

        summary["bundles_included"] += 1
        output_path = output_dir / f"{render_input['post_id']}.json"
        if output_path.exists() and not overwrite:
            summary["inputs_skipped"] += 1
            summary["skipped_existing"] += 1
            continue

        if not dry_run:
            try:
                write_render_input_atomically(render_input, output_path)
            except Exception as exc:
                summary["errors"].append(f"Failed to write {output_path}: {exc}")
                summary["inputs_skipped"] += 1
                continue

            summary["inputs_written"] += 1

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build renderer input JSON files from an approved bundle index.")
    parser.add_argument("--index-file", default="runtime/approved/index.json")
    parser.add_argument("--output-dir", default="runtime/render_inputs")
    parser.add_argument("--include-not-ready", action="store_true", default=False)
    parser.add_argument("--overwrite", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args()

    index_file = Path(args.index_file)
    output_dir = Path(args.output_dir)

    try:
        index_payload = load_bundle_index(index_file)
        summary = build_render_inputs(
            index_payload,
            output_dir,
            include_not_ready=args.include_not_ready,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            index_file=index_file,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
