from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_MEDIA_STATUSES = {"downloaded", "skipped_existing"}


def path_for_json(path: Path) -> str:
    return path.as_posix()


def load_bundle_metadata(metadata_path: Path) -> dict:
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    try:
        content = metadata_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to read metadata {metadata_path}: {exc}") from exc

    try:
        metadata = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {metadata_path}: {exc}") from exc

    if not isinstance(metadata, dict):
        raise ValueError(f"Invalid metadata in {metadata_path}: top-level must be a JSON object")

    return metadata


def _coerce_score(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_media_files(local_media: list) -> list[dict]:
    media_files = []
    for entry in local_media:
        if not isinstance(entry, dict):
            continue

        if entry.get("status") not in VALID_MEDIA_STATUSES:
            continue

        local_path = entry.get("local_path") or ""
        filename = entry.get("filename") or ""
        if not local_path and not filename:
            continue

        media_files.append({
            "index": entry.get("index"),
            "filename": filename,
            "local_path": local_path,
            "content_type": entry.get("content_type"),
            "source_url": entry.get("source_url"),
        })
    return media_files


def summarize_bundle(bundle_dir: Path) -> tuple[dict | None, dict | None]:
    metadata_path = bundle_dir / "metadata.json"
    invalid = {
        "bundle_dir": path_for_json(bundle_dir),
        "metadata_path": path_for_json(metadata_path),
        "error": "",
    }

    try:
        metadata = load_bundle_metadata(metadata_path)
    except Exception as exc:
        invalid["error"] = str(exc)
        return None, invalid

    post_id = metadata.get("post_id")
    if not post_id:
        invalid["error"] = "Metadata is missing required 'post_id'"
        return None, invalid

    review_status = metadata.get("review_status")
    if review_status != "approved":
        invalid["error"] = "Metadata review_status must be 'approved'"
        return None, invalid

    local_media = metadata.get("local_media", [])
    if not isinstance(local_media, list):
        invalid["error"] = "Metadata 'local_media' must be a list"
        return None, invalid

    bundle_errors = metadata.get("bundle_errors", [])
    if not isinstance(bundle_errors, list):
        invalid["error"] = "Metadata 'bundle_errors' must be a list"
        return None, invalid

    metrics = metadata.get("metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}

    media_files = _normalize_media_files(local_media)
    ready_for_render = bool(
        post_id
        and review_status == "approved"
        and not bundle_errors
    )

    bundle = {
        "post_id": str(post_id),
        "account_handle": metadata.get("account_handle"),
        "url": metadata.get("url"),
        "text_prefix": metadata.get("text_prefix"),
        "score": _coerce_score(metadata.get("score")),
        "metrics": metrics,
        "review_status": review_status,
        "reviewed_at": metadata.get("reviewed_at"),
        "metadata_path": path_for_json(metadata_path),
        "bundle_dir": path_for_json(bundle_dir),
        "local_media_count": len(media_files),
        "has_media": len(media_files) > 0,
        "media_files": media_files,
        "bundle_errors": bundle_errors,
        "ready_for_render": ready_for_render,
    }
    return bundle, None


def build_bundle_index(bundles_dir: Path, include_invalid: bool = False) -> dict:
    bundles = []
    invalid_bundles = []

    if bundles_dir.exists():
        for child in bundles_dir.iterdir():
            if not child.is_dir():
                continue

            bundle, invalid = summarize_bundle(child)
            if bundle is not None:
                bundles.append(bundle)
            elif invalid is not None:
                invalid_bundles.append(invalid)

    bundles.sort(key=lambda item: str(item.get("post_id") or ""))
    bundles.sort(key=lambda item: str(item.get("reviewed_at") or ""), reverse=True)
    bundles.sort(key=lambda item: _coerce_score(item.get("score")), reverse=True)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "bundles_dir": path_for_json(bundles_dir),
        "bundle_count": len(bundles),
        "invalid_bundle_count": len(invalid_bundles),
        "bundles": bundles,
        "invalid_bundles": invalid_bundles if include_invalid else [],
    }


def write_index_atomically(index_payload: dict, output_json: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_json.with_name(f"{output_json.name}.tmp")
    tmp_path.write_text(json.dumps(index_payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(str(tmp_path), str(output_json))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an approved bundle index.")
    parser.add_argument("--bundles-dir", default="runtime/approved")
    parser.add_argument("--output-json", default="runtime/approved/index.json")
    parser.add_argument("--include-invalid", action="store_true", default=False)
    parser.add_argument("--pretty", action="store_true", default=True)
    args = parser.parse_args()

    bundles_dir = Path(args.bundles_dir)
    output_json = Path(args.output_json)
    index_payload = build_bundle_index(bundles_dir, include_invalid=args.include_invalid)

    try:
        write_index_atomically(index_payload, output_json)
    except Exception as exc:
        print(f"Error: failed to write approved bundle index to {output_json}: {exc}", file=sys.stderr)
        return 1

    invalid_bundles = index_payload["invalid_bundles"]
    if not args.include_invalid and index_payload["invalid_bundle_count"]:
        invalid_bundles = [
            invalid
            for child in bundles_dir.iterdir()
            if child.is_dir()
            for _bundle, invalid in [summarize_bundle(child)]
            if invalid is not None
        ] if bundles_dir.exists() else []

    summary = {
        "bundles_dir": path_for_json(bundles_dir),
        "output_json": path_for_json(output_json),
        "valid_bundle_count": index_payload["bundle_count"],
        "invalid_bundle_count": index_payload["invalid_bundle_count"],
        "errors": [item["error"] for item in invalid_bundles],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
