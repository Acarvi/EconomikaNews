from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from PIL import Image


VideoWriter = Callable[[Path, Path, float, int], None]


def path_for_json(path: Path) -> str:
    return path.as_posix()


def load_render_manifest(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"Manifest file missing: {path}") from exc
    except Exception as exc:
        raise ValueError(f"Failed to read manifest {path}: {exc}") from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid manifest JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid manifest: top-level must be a JSON object")

    renders = payload.get("renders")
    if not isinstance(renders, list):
        raise ValueError("Invalid manifest: 'renders' must be a list")

    return payload


def iter_publishable_renders(manifest: dict, include_not_ready: bool = False) -> list[dict]:
    renders = manifest.get("renders", [])
    if not isinstance(renders, list):
        return []
    return [
        render
        for render in renders
        if isinstance(render, dict) and (include_not_ready or render.get("ready_for_publish") is True)
    ]


def _read_card_frame(card_path: Path) -> tuple[Any, int, int]:
    try:
        with Image.open(card_path) as image:
            frame = image.convert("RGB")
            width, height = frame.size
            frame.load()
    except Exception as exc:
        raise ValueError(f"Failed to read card PNG {card_path}: {exc}") from exc

    if width <= 0 or height <= 0:
        raise ValueError("Card PNG dimensions must be greater than zero")
    return frame, width, height


def _default_video_writer(card_path: Path, output_path: Path, duration_seconds: float, fps: int) -> None:
    import imageio.v2 as imageio

    frame_data = imageio.imread(card_path)
    frame_count = max(1, int(round(duration_seconds * fps)))
    with imageio.get_writer(output_path, fps=fps, codec="libx264", macro_block_size=None) as video:
        for _index in range(frame_count):
            video.append_data(frame_data)


def export_static_card_video(
    card_path: Path,
    output_path: Path,
    duration_seconds: float,
    fps: int,
    writer: VideoWriter | None = None,
) -> dict:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be greater than zero")
    if fps <= 0:
        raise ValueError("fps must be greater than zero")

    _frame, width, height = _read_card_frame(card_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name("video.tmp.mp4")
    if tmp_path.exists():
        tmp_path.unlink()

    active_writer = writer or _default_video_writer
    try:
        active_writer(card_path, tmp_path, duration_seconds, fps)
        os.replace(str(tmp_path), str(output_path))
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    return {
        "width": width,
        "height": height,
        "video_path": path_for_json(output_path),
    }


def write_video_metadata_atomically(metadata: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(str(tmp_path), str(path))


def _render_error(post_id: str, message: str) -> str:
    return f"{post_id}: {message}" if post_id else message


def _clean_provenance(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def export_video_for_render(
    render: dict,
    output_dir: Path,
    overwrite: bool = False,
    dry_run: bool = False,
    duration_seconds: float = 6,
    fps: int = 30,
    writer: VideoWriter | None = None,
) -> dict:
    result = {
        "post_id": "",
        "video_path": "",
        "metadata_path": "",
        "written": False,
        "skipped": False,
        "skipped_existing": False,
        "video_ready": False,
        "error": "",
        "dry_run": dry_run,
    }

    if not isinstance(render, dict):
        result["skipped"] = True
        result["error"] = "Invalid render entry: must be a JSON object"
        return result

    post_id = str(render.get("post_id") or "").strip()
    result["post_id"] = post_id
    if not post_id:
        result["skipped"] = True
        result["error"] = "Invalid render entry: missing post_id"
        return result

    card_value = str(render.get("card_path") or "").strip()
    if not card_value:
        result["skipped"] = True
        result["error"] = _render_error(post_id, "missing card_path")
        return result

    card_path = Path(card_value)
    if not card_path.exists() or not card_path.is_file():
        result["skipped"] = True
        result["error"] = _render_error(post_id, f"card_path missing or not a file: {card_path}")
        return result

    video_path = output_dir / post_id / "video.mp4"
    metadata_path = output_dir / post_id / "video_metadata.json"
    result["video_path"] = path_for_json(video_path)
    result["metadata_path"] = path_for_json(metadata_path)

    if video_path.exists() and not overwrite:
        result["skipped"] = True
        result["skipped_existing"] = True
        return result

    ready_for_upload = render.get("ready_for_publish") is True
    if dry_run:
        result["video_ready"] = ready_for_upload
        return result

    try:
        video_info = export_static_card_video(
            card_path,
            video_path,
            duration_seconds=duration_seconds,
            fps=fps,
            writer=writer,
        )
        metadata = {
            "post_id": post_id,
            "source_card_path": path_for_json(card_path),
            "source_account_handle": _clean_provenance(render.get("account_handle")),
            "source_url": _clean_provenance(render.get("url")),
            "source_manifest_entry": render,
            "video_path": path_for_json(video_path),
            "duration_seconds": duration_seconds,
            "fps": fps,
            "width": video_info["width"],
            "height": video_info["height"],
            "ready_for_upload": ready_for_upload,
            "video_errors": [],
        }
        write_video_metadata_atomically(metadata, metadata_path)
    except Exception as exc:
        result["skipped"] = True
        result["error"] = _render_error(post_id, f"video export failed: {exc}")
        return result

    result["written"] = True
    result["video_ready"] = ready_for_upload
    return result


def export_all_videos(
    manifest_file: Path,
    output_dir: Path,
    duration_seconds: float = 6,
    fps: int = 30,
    include_not_ready: bool = False,
    overwrite: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
    writer: VideoWriter | None = None,
) -> dict:
    manifest = load_render_manifest(manifest_file)
    renders = iter_publishable_renders(manifest, include_not_ready=include_not_ready)
    if limit is not None:
        renders = renders[:limit]

    summary = {
        "manifest_file": path_for_json(manifest_file),
        "output_dir": path_for_json(output_dir),
        "renders_seen": len(renders),
        "videos_written": 0,
        "videos_skipped": 0,
        "skipped_existing": 0,
        "errors": [],
        "dry_run": dry_run,
        "overwrite": overwrite,
        "duration_seconds": duration_seconds,
        "fps": fps,
        "items": [],
    }

    for render in renders:
        result = export_video_for_render(
            render,
            output_dir,
            overwrite=overwrite,
            dry_run=dry_run,
            duration_seconds=duration_seconds,
            fps=fps,
            writer=writer,
        )
        summary["items"].append(result)
        if result["written"]:
            summary["videos_written"] += 1
        if result["skipped"]:
            summary["videos_skipped"] += 1
        if result["skipped_existing"]:
            summary["skipped_existing"] += 1
        if result["error"]:
            summary["errors"].append(result["error"])

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Export simple static MP4 videos from rendered card PNGs.")
    parser.add_argument("--manifest-file", default="runtime/renders/manifest.json")
    parser.add_argument("--output-dir", default="runtime/videos")
    parser.add_argument("--duration-seconds", type=float, default=6)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--include-not-ready", action="store_true", default=False)
    parser.add_argument("--overwrite", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    try:
        summary = export_all_videos(
            Path(args.manifest_file),
            Path(args.output_dir),
            duration_seconds=args.duration_seconds,
            fps=args.fps,
            include_not_ready=args.include_not_ready,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
