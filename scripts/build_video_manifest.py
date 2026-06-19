from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def path_for_json(path: Path) -> str:
    return path.as_posix()


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def mtime_utc_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat().replace("+00:00", "Z")


def load_video_metadata(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to read video metadata: {exc}") from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid video metadata JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid video metadata: top-level must be a JSON object")

    return payload


def _positive_number(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _positive_int(value: Any) -> bool:
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def summarize_video(video_dir: Path) -> tuple[dict | None, dict | None]:
    post_id = video_dir.name
    video_path = video_dir / "video.mp4"
    metadata_path = video_dir / "video_metadata.json"
    invalid = {
        "video_dir": path_for_json(video_dir),
        "video_path": path_for_json(video_path),
        "metadata_path": path_for_json(metadata_path),
        "error": "",
    }

    if not video_path.exists():
        invalid["error"] = "video.mp4 missing"
        return None, invalid
    if not video_path.is_file():
        invalid["error"] = "video.mp4 is not a file"
        return None, invalid

    file_size_bytes = video_path.stat().st_size
    if file_size_bytes <= 0:
        invalid["error"] = "video.mp4 is empty"
        return None, invalid

    video_errors: list[str] = []
    metadata: dict[str, Any] = {}
    metadata_valid = False
    if metadata_path.exists():
        try:
            metadata = load_video_metadata(metadata_path)
            metadata_valid = True
        except ValueError as exc:
            video_errors.append(str(exc))
    else:
        video_errors.append("Video metadata missing")

    metadata_post_id = metadata.get("post_id")
    metadata_video_path = metadata.get("video_path")
    metadata_errors = metadata.get("video_errors", [])
    if not isinstance(metadata_errors, list):
        metadata_errors = ["video_errors must be a list"]
    video_errors.extend(str(error) for error in metadata_errors if str(error))

    if metadata_valid and metadata_post_id != post_id:
        video_errors.append(f"Video metadata post_id mismatch: expected {post_id}, got {metadata_post_id}")

    if metadata_valid and Path(str(metadata_video_path or "")) != video_path:
        video_errors.append(f"Video metadata video_path mismatch: expected {path_for_json(video_path)}, got {metadata_video_path}")

    if metadata_valid and metadata.get("ready_for_upload") is not True:
        video_errors.append("Video metadata ready_for_upload is not true")

    duration_seconds = metadata.get("duration_seconds")
    fps = metadata.get("fps")
    width = metadata.get("width")
    height = metadata.get("height")
    if metadata_valid and not _positive_number(duration_seconds):
        video_errors.append("Video metadata duration_seconds must be greater than zero")
    if metadata_valid and not _positive_int(fps):
        video_errors.append("Video metadata fps must be greater than zero")
    if metadata_valid and not _positive_int(width):
        video_errors.append("Video metadata width must be greater than zero")
    if metadata_valid and not _positive_int(height):
        video_errors.append("Video metadata height must be greater than zero")

    ready_for_upload = (
        file_size_bytes > 0
        and metadata_valid
        and metadata_post_id == post_id
        and Path(str(metadata_video_path or "")) == video_path
        and metadata.get("ready_for_upload") is True
        and _positive_int(width)
        and _positive_int(height)
        and _positive_number(duration_seconds)
        and _positive_int(fps)
        and not video_errors
    )

    video = {
        "post_id": post_id,
        "video_path": path_for_json(video_path),
        "metadata_path": path_for_json(metadata_path),
        "file_size_bytes": file_size_bytes,
        "created_at": mtime_utc_iso(video_path),
        "duration_seconds": duration_seconds,
        "fps": fps,
        "width": width,
        "height": height,
        "source_card_path": metadata.get("source_card_path"),
        "ready_for_upload": ready_for_upload,
        "video_errors": video_errors,
    }
    return video, None


def build_video_manifest(videos_dir: Path, include_invalid: bool = False) -> dict:
    videos = []
    invalid_videos = []

    if videos_dir.exists() and videos_dir.is_dir():
        for video_dir in sorted(path for path in videos_dir.iterdir() if path.is_dir()):
            video, invalid = summarize_video(video_dir)
            if video is not None:
                videos.append(video)
            if invalid is not None:
                invalid_videos.append(invalid)

    videos = sorted(
        videos,
        key=lambda item: (
            -datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")).timestamp(),
            item["post_id"],
        ),
    )

    return {
        "generated_at": utc_now_iso(),
        "videos_dir": path_for_json(videos_dir),
        "video_count": len(videos),
        "invalid_video_count": len(invalid_videos),
        "videos": videos,
        "invalid_videos": invalid_videos if include_invalid else [],
    }


def collect_manifest_errors(manifest: dict) -> list[str]:
    errors = []

    invalid_videos = manifest.get("invalid_videos", [])
    if isinstance(invalid_videos, list):
        for invalid in invalid_videos:
            if not isinstance(invalid, dict):
                continue
            video_dir = invalid.get("video_dir") or ""
            error = invalid.get("error") or "Invalid video"
            errors.append(f"{video_dir}: {error}" if video_dir else str(error))

    videos = manifest.get("videos", [])
    if isinstance(videos, list):
        for video in videos:
            if not isinstance(video, dict) or video.get("ready_for_upload") is True:
                continue
            post_id = video.get("post_id") or ""
            video_errors = video.get("video_errors", [])
            if not isinstance(video_errors, list):
                continue
            for error in video_errors:
                errors.append(f"{post_id}: {error}" if post_id else str(error))

    return errors


def write_manifest_atomically(payload: dict, output_json: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_json.with_name(f"{output_json.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(str(tmp_path), str(output_json))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a manifest of local video artifacts.")
    parser.add_argument("--videos-dir", default="runtime/videos")
    parser.add_argument("--output-json", default="runtime/videos/manifest.json")
    parser.add_argument("--include-invalid", action="store_true", default=False)
    parser.add_argument("--pretty", action="store_true", default=False)
    args = parser.parse_args()

    videos_dir = Path(args.videos_dir)
    output_json = Path(args.output_json)
    manifest = build_video_manifest(videos_dir, include_invalid=True)
    errors = collect_manifest_errors(manifest)
    if not args.include_invalid:
        manifest["invalid_videos"] = []

    summary = {
        "videos_dir": path_for_json(videos_dir),
        "output_json": path_for_json(output_json),
        "video_count": manifest["video_count"],
        "invalid_video_count": manifest["invalid_video_count"],
        "errors": errors,
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
