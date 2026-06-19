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


def load_packet_metadata(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to read packet metadata: {exc}") from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid packet metadata JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid packet metadata: top-level must be a JSON object")

    return payload


def normalize_caption_preview(text: str, max_chars: int = 140) -> str:
    preview = " ".join(text.split())
    if len(preview) <= max_chars:
        return preview
    return preview[:max_chars].rstrip()


def read_caption_info(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return {
        "caption_length": len(text),
        "caption_preview": normalize_caption_preview(text),
    }


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def summarize_packet(packet_dir: Path) -> tuple[dict | None, dict | None]:
    post_id = packet_dir.name
    video_path = packet_dir / "video.mp4"
    caption_path = packet_dir / "caption.txt"
    metadata_path = packet_dir / "metadata.json"
    invalid = {
        "packet_dir": path_for_json(packet_dir),
        "video_path": path_for_json(video_path),
        "caption_path": path_for_json(caption_path),
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

    packet_errors: list[str] = []
    caption_info = {
        "caption_length": 0,
        "caption_preview": "",
    }
    if caption_path.exists() and caption_path.is_file():
        try:
            caption_info = read_caption_info(caption_path)
        except Exception as exc:
            packet_errors.append(f"Failed to read caption: {exc}")
    else:
        packet_errors.append("Caption missing")

    metadata: dict[str, Any] = {}
    metadata_valid = False
    if metadata_path.exists() and metadata_path.is_file():
        try:
            metadata = load_packet_metadata(metadata_path)
            metadata_valid = True
        except ValueError as exc:
            packet_errors.append(str(exc))
    else:
        packet_errors.append("Metadata missing")

    metadata_post_id = metadata.get("post_id")
    metadata_video_path = metadata.get("video_path")
    metadata_caption_path = metadata.get("caption_path")
    metadata_errors = metadata.get("packet_errors", [])
    if not isinstance(metadata_errors, list):
        metadata_errors = ["packet_errors must be a list"]
    packet_errors.extend(str(error) for error in metadata_errors if str(error))

    if metadata_valid and metadata_post_id != post_id:
        packet_errors.append(f"Packet metadata post_id mismatch: expected {post_id}, got {metadata_post_id}")

    if metadata_valid and Path(str(metadata_video_path or "")) != video_path:
        packet_errors.append(
            f"Packet metadata video_path mismatch: expected {path_for_json(video_path)}, got {metadata_video_path}"
        )

    if metadata_valid and Path(str(metadata_caption_path or "")) != caption_path:
        packet_errors.append(
            f"Packet metadata caption_path mismatch: expected {path_for_json(caption_path)}, got {metadata_caption_path}"
        )

    if metadata_valid and metadata.get("packet_ready") is not True:
        packet_errors.append("Packet metadata packet_ready is not true")

    if metadata_valid and metadata.get("manual_upload") is not True:
        packet_errors.append("Packet metadata manual_upload is not true")

    platforms = metadata.get("platforms", [])
    if not isinstance(platforms, list):
        platforms = []
    platforms = [str(platform) for platform in platforms if str(platform)]
    if metadata_valid and not platforms:
        packet_errors.append("Packet metadata platforms must be a non-empty list")

    packet_ready = (
        file_size_bytes > 0
        and caption_path.exists()
        and caption_path.is_file()
        and metadata_valid
        and metadata_post_id == post_id
        and Path(str(metadata_video_path or "")) == video_path
        and Path(str(metadata_caption_path or "")) == caption_path
        and metadata.get("packet_ready") is True
        and metadata.get("manual_upload") is True
        and bool(platforms)
        and not packet_errors
    )

    packet = {
        "post_id": post_id,
        "packet_dir": path_for_json(packet_dir),
        "video_path": path_for_json(video_path),
        "caption_path": path_for_json(caption_path),
        "metadata_path": path_for_json(metadata_path),
        "file_size_bytes": file_size_bytes,
        "created_at": _clean_text(metadata.get("created_at")) or mtime_utc_iso(video_path),
        "caption_length": caption_info["caption_length"],
        "caption_preview": caption_info["caption_preview"],
        "source_account_handle": _clean_text(metadata.get("source_account_handle")),
        "source_url": _clean_text(metadata.get("source_url")),
        "platforms": platforms,
        "manual_upload": metadata.get("manual_upload") is True,
        "packet_ready": packet_ready,
        "packet_errors": packet_errors,
    }
    return packet, None


def build_publish_queue_manifest(queue_dir: Path, include_invalid: bool = False) -> dict:
    packets = []
    invalid_packets = []

    if queue_dir.exists() and queue_dir.is_dir():
        for packet_dir in sorted(path for path in queue_dir.iterdir() if path.is_dir()):
            packet, invalid = summarize_packet(packet_dir)
            if packet is not None:
                packets.append(packet)
            if invalid is not None:
                invalid_packets.append(invalid)

    packets = sorted(
        packets,
        key=lambda item: (
            -datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")).timestamp(),
            item["post_id"],
        ),
    )

    return {
        "generated_at": utc_now_iso(),
        "queue_dir": path_for_json(queue_dir),
        "packet_count": len(packets),
        "invalid_packet_count": len(invalid_packets),
        "packets": packets,
        "invalid_packets": invalid_packets if include_invalid else [],
    }


def collect_manifest_errors(manifest: dict) -> list[str]:
    errors = []

    invalid_packets = manifest.get("invalid_packets", [])
    if isinstance(invalid_packets, list):
        for invalid in invalid_packets:
            if not isinstance(invalid, dict):
                continue
            packet_dir = invalid.get("packet_dir") or ""
            error = invalid.get("error") or "Invalid packet"
            errors.append(f"{packet_dir}: {error}" if packet_dir else str(error))

    packets = manifest.get("packets", [])
    if isinstance(packets, list):
        for packet in packets:
            if not isinstance(packet, dict) or packet.get("packet_ready") is True:
                continue
            post_id = packet.get("post_id") or ""
            packet_errors = packet.get("packet_errors", [])
            if not isinstance(packet_errors, list):
                continue
            for error in packet_errors:
                errors.append(f"{post_id}: {error}" if post_id else str(error))

    return errors


def write_manifest_atomically(payload: dict, output_json: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_json.with_name(f"{output_json.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(str(tmp_path), str(output_json))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a manifest of local publish queue packets.")
    parser.add_argument("--queue-dir", default="runtime/publish_queue")
    parser.add_argument("--output-json", default="runtime/publish_queue/manifest.json")
    parser.add_argument("--include-invalid", action="store_true", default=False)
    parser.add_argument("--pretty", action="store_true", default=False)
    args = parser.parse_args()

    queue_dir = Path(args.queue_dir)
    output_json = Path(args.output_json)
    manifest = build_publish_queue_manifest(queue_dir, include_invalid=True)
    errors = collect_manifest_errors(manifest)
    if not args.include_invalid:
        manifest["invalid_packets"] = []

    summary = {
        "queue_dir": path_for_json(queue_dir),
        "output_json": path_for_json(output_json),
        "packet_count": manifest["packet_count"],
        "invalid_packet_count": manifest["invalid_packet_count"],
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
