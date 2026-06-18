from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image


def path_for_json(path: Path) -> str:
    return path.as_posix()


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def mtime_utc_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat().replace("+00:00", "Z")


def load_render_input_metadata(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to read render input: {exc}") from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid render input JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid render input: top-level must be a JSON object")

    render = payload.get("render", {})
    if render is None:
        render = {}
    if not isinstance(render, dict):
        raise ValueError("Invalid render input: 'render' must be a JSON object")

    target_formats = render.get("target_formats", [])
    if not isinstance(target_formats, list):
        target_formats = []

    return {
        "post_id": payload.get("post_id"),
        "url": payload.get("url"),
        "account_handle": payload.get("account_handle"),
        "template": render.get("template"),
        "target_formats": target_formats,
        "render_ready": render.get("ready") is True,
    }


def read_png_info(card_path: Path) -> dict:
    try:
        with Image.open(card_path) as image:
            width, height = image.size
            image.verify()
    except Exception as exc:
        raise ValueError(f"Unreadable PNG: {exc}") from exc

    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions must be greater than zero")

    return {
        "width": width,
        "height": height,
        "file_size_bytes": card_path.stat().st_size,
    }


def summarize_render(render_dir: Path, render_inputs_dir: Path) -> tuple[dict | None, dict | None]:
    post_id = render_dir.name
    card_path = render_dir / "card.png"
    invalid = {
        "render_dir": path_for_json(render_dir),
        "card_path": path_for_json(card_path),
        "error": "",
    }

    if not card_path.exists():
        invalid["error"] = "card.png missing"
        return None, invalid
    if not card_path.is_file():
        invalid["error"] = "card.png is not a file"
        return None, invalid

    try:
        png_info = read_png_info(card_path)
    except ValueError as exc:
        invalid["error"] = str(exc)
        return None, invalid

    render_input_path = render_inputs_dir / f"{post_id}.json"
    render_errors: list[str] = []
    metadata: dict[str, Any] = {
        "post_id": None,
        "url": None,
        "account_handle": None,
        "template": None,
        "target_formats": [],
        "render_ready": False,
    }

    if render_input_path.exists():
        try:
            metadata = load_render_input_metadata(render_input_path)
        except ValueError as exc:
            render_errors.append(str(exc))
    else:
        render_errors.append("Render input missing")

    if render_input_path.exists() and metadata.get("post_id") != post_id:
        render_errors.append(f"Render input post_id mismatch: expected {post_id}, got {metadata.get('post_id')}")

    if render_input_path.exists() and metadata.get("render_ready") is not True:
        render_errors.append("Render input render.ready is not true")

    ready_for_publish = (
        png_info["width"] > 0
        and png_info["height"] > 0
        and render_input_path.exists()
        and metadata.get("post_id") == post_id
        and metadata.get("render_ready") is True
        and not render_errors
    )

    render = {
        "post_id": post_id,
        "card_path": path_for_json(card_path),
        "render_input_path": path_for_json(render_input_path),
        "width": png_info["width"],
        "height": png_info["height"],
        "file_size_bytes": png_info["file_size_bytes"],
        "created_at": mtime_utc_iso(card_path),
        "account_handle": metadata.get("account_handle"),
        "url": metadata.get("url"),
        "template": metadata.get("template"),
        "target_formats": metadata.get("target_formats"),
        "ready_for_publish": ready_for_publish,
        "render_errors": render_errors,
    }
    return render, None


def build_render_manifest(renders_dir: Path, render_inputs_dir: Path, include_invalid: bool = False) -> dict:
    renders = []
    invalid_renders = []

    if renders_dir.exists() and renders_dir.is_dir():
        for render_dir in sorted(path for path in renders_dir.iterdir() if path.is_dir()):
            render, invalid = summarize_render(render_dir, render_inputs_dir)
            if render is not None:
                renders.append(render)
            if invalid is not None:
                invalid_renders.append(invalid)

    renders = sorted(
        renders,
        key=lambda item: (
            -datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")).timestamp(),
            item["post_id"],
        ),
    )

    return {
        "generated_at": utc_now_iso(),
        "renders_dir": path_for_json(renders_dir),
        "render_inputs_dir": path_for_json(render_inputs_dir),
        "render_count": len(renders),
        "invalid_render_count": len(invalid_renders),
        "renders": renders,
        "invalid_renders": invalid_renders if include_invalid else [],
    }


def write_manifest_atomically(payload: dict, output_json: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_json.with_name(f"{output_json.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(str(tmp_path), str(output_json))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a manifest of local render artifacts.")
    parser.add_argument("--renders-dir", default="runtime/renders")
    parser.add_argument("--render-inputs-dir", default="runtime/render_inputs")
    parser.add_argument("--output-json", default="runtime/renders/manifest.json")
    parser.add_argument("--include-invalid", action="store_true", default=False)
    parser.add_argument("--pretty", action="store_true", default=False)
    args = parser.parse_args()

    renders_dir = Path(args.renders_dir)
    render_inputs_dir = Path(args.render_inputs_dir)
    output_json = Path(args.output_json)
    manifest = build_render_manifest(renders_dir, render_inputs_dir, include_invalid=args.include_invalid)

    summary = {
        "renders_dir": path_for_json(renders_dir),
        "render_inputs_dir": path_for_json(render_inputs_dir),
        "output_json": path_for_json(output_json),
        "render_count": manifest["render_count"],
        "invalid_render_count": manifest["invalid_render_count"],
        "errors": [],
    }

    try:
        write_manifest_atomically(manifest, output_json)
    except Exception as exc:
        print(f"Error: failed to write manifest {output_json}: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
