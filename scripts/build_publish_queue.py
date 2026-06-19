from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ALLOWED_PLATFORMS = ("tiktok", "instagram_reels", "youtube_shorts")
DEFAULT_HASHTAGS = "#Economika #Economia #Politica #Shorts"


def path_for_json(path: Path) -> str:
    return path.as_posix()


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_video_manifest(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"Video manifest missing: {path}") from exc
    except Exception as exc:
        raise ValueError(f"Failed to read video manifest {path}: {exc}") from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid video manifest JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid video manifest: top-level must be a JSON object")

    videos = payload.get("videos")
    if not isinstance(videos, list):
        raise ValueError("Invalid video manifest: 'videos' must be a list")

    return payload


def iter_queueable_videos(manifest: dict, include_not_ready: bool = False) -> list[dict]:
    videos = manifest.get("videos", [])
    if not isinstance(videos, list):
        return []
    return [
        video
        for video in videos
        if isinstance(video, dict) and (include_not_ready or video.get("ready_for_upload") is True)
    ]


def normalize_platforms(raw: list[str] | None) -> list[str]:
    if not raw:
        return list(ALLOWED_PLATFORMS)

    platforms: list[str] = []
    for item in raw:
        for value in str(item).split(","):
            platform = value.strip()
            if not platform:
                continue
            if platform not in ALLOWED_PLATFORMS:
                allowed = ", ".join(ALLOWED_PLATFORMS)
                raise ValueError(f"Invalid platform: {platform}. Allowed values: {allowed}")
            if platform not in platforms:
                platforms.append(platform)

    return platforms or list(ALLOWED_PLATFORMS)


def _clean_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return " ".join(text.split()) or fallback


def _source_manifest(video_entry: dict) -> dict:
    source = video_entry.get("source_manifest_entry")
    if isinstance(source, dict):
        return source
    source = video_entry.get("source_video_manifest_entry")
    if isinstance(source, dict):
        return source
    return {}


def _source_label(video_entry: dict) -> str:
    source = _source_manifest(video_entry)
    for key in ("account_handle", "source_handle", "handle"):
        handle = _clean_text(source.get(key) or video_entry.get(key))
        if handle:
            return f"@{handle.lstrip('@')}"
    return "desconocida"


def build_caption(video_entry: dict) -> str:
    post_id = _clean_text(video_entry.get("post_id"), "desconocido")
    source = _source_manifest(video_entry)
    url = _clean_text(source.get("url") or video_entry.get("url"))
    lines = [
        "ECONOMIKA - senal detectada.",
        "",
        f"Fuente: {_source_label(video_entry)}",
        f"Post ID: {post_id}",
    ]
    if url:
        lines.append(f"Fuente original: {url}")
    lines.extend(
        [
            "",
            "Video generado automaticamente desde una senal aprobada para revision editorial.",
            "",
            DEFAULT_HASHTAGS,
        ]
    )
    caption = "\n".join(lines)
    if len(caption) <= 500:
        return caption
    without_url = [line for line in lines if not line.startswith("Fuente original: ")]
    caption = "\n".join(without_url)
    return caption[:500].rstrip()


def write_text_atomically(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(str(tmp_path), str(path))


def write_json_atomically(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(str(tmp_path), str(path))


def copy_file_atomically(source_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name("video.tmp.mp4")
    if tmp_path.exists():
        tmp_path.unlink()
    try:
        shutil.copyfile(source_path, tmp_path)
        os.replace(str(tmp_path), str(output_path))
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def build_packet_metadata(
    video_entry: dict,
    packet_dir: Path,
    source_video_path: Path,
    video_path: Path,
    caption_path: Path,
    platforms: list[str],
    packet_ready: bool,
    packet_errors: list[str],
) -> dict:
    post_id = str(video_entry.get("post_id") or "").strip()
    return {
        "post_id": post_id,
        "created_at": utc_now_iso(),
        "packet_dir": path_for_json(packet_dir),
        "video_path": path_for_json(video_path),
        "caption_path": path_for_json(caption_path),
        "source_video_path": path_for_json(source_video_path),
        "source_video_manifest_entry": video_entry,
        "platforms": platforms,
        "packet_ready": packet_ready,
        "packet_errors": packet_errors,
        "manual_upload": True,
    }


def build_publish_packet_for_video(
    video_entry: dict,
    output_dir: Path,
    platforms: list[str],
    include_not_ready: bool = False,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict:
    result = {
        "post_id": "",
        "packet_dir": "",
        "written": False,
        "skipped": False,
        "skipped_existing": False,
        "packet_ready": False,
        "error": "",
        "dry_run": dry_run,
    }

    if not isinstance(video_entry, dict):
        result["skipped"] = True
        result["error"] = "Invalid video entry: must be a JSON object"
        return result

    post_id = str(video_entry.get("post_id") or "").strip()
    result["post_id"] = post_id
    if not post_id:
        result["skipped"] = True
        result["error"] = "Invalid video entry: missing post_id"
        return result

    video_value = str(video_entry.get("video_path") or "").strip()
    if not video_value:
        result["skipped"] = True
        result["error"] = f"{post_id}: missing video_path"
        return result

    source_video_path = Path(video_value)
    if not source_video_path.exists() or not source_video_path.is_file():
        result["skipped"] = True
        result["error"] = f"{post_id}: video_path missing or not a file: {source_video_path}"
        return result

    packet_dir = output_dir / post_id
    packet_video_path = packet_dir / "video.mp4"
    caption_path = packet_dir / "caption.txt"
    metadata_path = packet_dir / "metadata.json"
    result["packet_dir"] = path_for_json(packet_dir)

    if packet_dir.exists() and not overwrite:
        result["skipped"] = True
        result["skipped_existing"] = True
        return result

    packet_errors: list[str] = []
    source_ready = video_entry.get("ready_for_upload") is True
    if not source_ready:
        packet_errors.append("Source video ready_for_upload is not true")

    if dry_run:
        result["packet_ready"] = source_ready or (include_not_ready and not packet_errors)
        return result

    try:
        copy_file_atomically(source_video_path, packet_video_path)
        write_text_atomically(build_caption(video_entry), caption_path)
        packet_ready = (
            packet_video_path.exists()
            and caption_path.exists()
            and source_ready
            and not packet_errors
        )
        metadata = build_packet_metadata(
            video_entry,
            packet_dir,
            source_video_path,
            packet_video_path,
            caption_path,
            platforms,
            packet_ready=False,
            packet_errors=packet_errors,
        )
        write_json_atomically(metadata, metadata_path)
        packet_ready = packet_ready and metadata_path.exists()
        if packet_ready:
            metadata["packet_ready"] = True
            write_json_atomically(metadata, metadata_path)
    except Exception as exc:
        result["skipped"] = True
        result["error"] = f"{post_id}: failed to build publish packet: {exc}"
        return result

    result["written"] = True
    result["packet_ready"] = packet_ready
    return result


def build_publish_queue(
    video_manifest: Path,
    output_dir: Path,
    platforms: list[str],
    include_not_ready: bool = False,
    overwrite: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict:
    manifest = load_video_manifest(video_manifest)
    videos = iter_queueable_videos(manifest, include_not_ready=include_not_ready)
    if limit is not None:
        videos = videos[:limit]

    summary = {
        "video_manifest": path_for_json(video_manifest),
        "output_dir": path_for_json(output_dir),
        "videos_seen": len(videos),
        "packets_written": 0,
        "packets_skipped": 0,
        "skipped_existing": 0,
        "errors": [],
        "dry_run": dry_run,
        "overwrite": overwrite,
        "platforms": platforms,
        "items": [],
    }

    for video in videos:
        result = build_publish_packet_for_video(
            video,
            output_dir,
            platforms,
            include_not_ready=include_not_ready,
            overwrite=overwrite,
            dry_run=dry_run,
        )
        summary["items"].append(result)
        if result["written"]:
            summary["packets_written"] += 1
        if result["skipped"]:
            summary["packets_skipped"] += 1
        if result["skipped_existing"]:
            summary["skipped_existing"] += 1
        if result["error"]:
            summary["errors"].append(result["error"])

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local manual-upload publish queue packets.")
    parser.add_argument("--video-manifest", default="runtime/videos/manifest.json")
    parser.add_argument("--output-dir", default="runtime/publish_queue")
    parser.add_argument("--include-not-ready", action="store_true", default=False)
    parser.add_argument("--overwrite", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--platform", action="append", default=None)
    args = parser.parse_args()

    try:
        platforms = normalize_platforms(args.platform)
        summary = build_publish_queue(
            Path(args.video_manifest),
            Path(args.output_dir),
            platforms,
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
