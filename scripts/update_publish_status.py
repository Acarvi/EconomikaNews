from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ALLOWED_PLATFORMS = ("tiktok", "instagram_reels", "youtube_shorts")
ALLOWED_STATUSES = ("pending", "drafted", "uploaded", "published", "skipped", "failed")
DEFAULT_STATUS_FILE = Path("runtime/publish_status/status.json")
DEFAULT_MANIFEST = Path("runtime/publish_queue/manifest.json")


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def normalize_now(value: str | None) -> str:
    if value is None:
        return utc_now_iso()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def normalize_platform(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    if normalized not in ALLOWED_PLATFORMS:
        raise ValueError(
            f"invalid platform '{value}'; expected one of: {', '.join(ALLOWED_PLATFORMS)}"
        )
    return normalized


def normalize_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in ALLOWED_STATUSES:
        raise ValueError(
            f"invalid status '{value}'; expected one of: {', '.join(ALLOWED_STATUSES)}"
        )
    return normalized


def _empty_payload() -> dict[str, Any]:
    return {"version": 1, "updated_at": None, "entries": []}


def load_status_file(path: Path) -> dict:
    if not path.exists():
        return _empty_payload()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid status JSON in {path}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"failed to read status file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid status JSON in {path}: top-level value must be an object")
    if not isinstance(payload.get("entries"), list):
        raise ValueError(f"invalid status JSON in {path}: entries must be a list")
    payload.setdefault("version", 1)
    payload.setdefault("updated_at", None)
    return payload


def write_status_file_atomically(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(str(tmp_path), str(path))


def load_publish_queue_manifest(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid publish queue manifest JSON in {path}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"failed to read publish queue manifest {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError(f"invalid publish queue manifest in {path}: top-level value must be an object")
    return manifest


def build_queue_platform_index(manifest: dict | None) -> dict[tuple[str, str], dict]:
    index: dict[tuple[str, str], dict] = {}
    if manifest is None:
        return index
    packets = manifest.get("packets", [])
    if not isinstance(packets, list):
        return index
    for packet in packets:
        if not isinstance(packet, dict):
            continue
        post_id = str(packet.get("post_id", "")).strip()
        platforms = packet.get("platforms", [])
        if not post_id or not isinstance(platforms, list):
            continue
        for value in platforms:
            try:
                platform = normalize_platform(str(value))
            except ValueError:
                continue
            index[(post_id, platform)] = packet
    return index


def find_entry(payload: dict, post_id: str, platform: str) -> dict | None:
    for entry in payload.get("entries", []):
        if (
            isinstance(entry, dict)
            and str(entry.get("post_id")) == post_id
            and entry.get("platform") == platform
        ):
            return entry
    return None


def _manifest_warning(
    manifest: dict | None,
    index: dict[tuple[str, str], dict],
    post_id: str,
    platform: str,
) -> str | None:
    if manifest is None or (post_id, platform) in index:
        return None
    known_posts = {key[0] for key in index}
    if post_id not in known_posts:
        return f"post_id '{post_id}' is not in the publish queue manifest"
    return f"platform '{platform}' is not listed for post_id '{post_id}' in the publish queue manifest"


def _manifest_filter_warning(
    manifest: dict | None,
    index: dict[tuple[str, str], dict],
    post_id: str | None,
    platform: str | None,
) -> str | None:
    if manifest is None:
        return None
    if post_id is not None and platform is not None:
        return _manifest_warning(manifest, index, post_id, platform)
    if post_id is not None and post_id not in {key[0] for key in index}:
        return f"post_id '{post_id}' is not in the publish queue manifest"
    if platform is not None and platform not in {key[1] for key in index}:
        return f"platform '{platform}' is not in the publish queue manifest"
    return None


def mark_status(
    payload: dict,
    *,
    post_id: str,
    platform: str,
    status: str,
    external_url: str | None = None,
    notes: str | None = None,
    now: str | None = None,
) -> dict:
    post_id = str(post_id).strip()
    if not post_id:
        raise ValueError("post_id must not be empty")
    platform = normalize_platform(platform)
    status = normalize_status(status)
    timestamp = normalize_now(now)
    entry = find_entry(payload, post_id, platform)
    if entry is None:
        entry = {
            "post_id": post_id,
            "platform": platform,
            "status": status,
            "external_url": external_url,
            "notes": notes,
            "created_at": timestamp,
            "updated_at": timestamp,
            "published_at": timestamp if status == "published" else None,
            "history": [],
        }
        payload["entries"].append(entry)
    else:
        entry["status"] = status
        entry["updated_at"] = timestamp
        if external_url is not None:
            entry["external_url"] = external_url
        if notes is not None:
            entry["notes"] = notes
        entry.setdefault("external_url", None)
        entry.setdefault("notes", None)
        entry.setdefault("created_at", timestamp)
        entry.setdefault("published_at", None)
        entry.setdefault("history", [])
        if status == "published" and not entry.get("published_at"):
            entry["published_at"] = timestamp

    history_item = {
        "status": status,
        "external_url": entry.get("external_url"),
        "notes": entry.get("notes"),
        "at": timestamp,
    }
    entry["history"].append(history_item)
    payload["version"] = 1
    payload["updated_at"] = timestamp
    return entry


def _pending_entry(post_id: str, platform: str) -> dict:
    return {
        "post_id": post_id,
        "platform": platform,
        "status": "pending",
        "external_url": None,
        "notes": None,
        "created_at": None,
        "updated_at": None,
        "published_at": None,
        "history": [],
    }


def list_statuses(
    payload: dict,
    manifest: dict | None = None,
    *,
    post_id: str | None = None,
    platform: str | None = None,
) -> list[dict]:
    normalized_platform = normalize_platform(platform) if platform is not None else None
    combined: dict[tuple[str, str], dict] = {}
    for key in build_queue_platform_index(manifest):
        combined[key] = _pending_entry(*key)
    for entry in payload.get("entries", []):
        if not isinstance(entry, dict):
            continue
        entry_post_id = str(entry.get("post_id", ""))
        try:
            entry_platform = normalize_platform(str(entry.get("platform", "")))
        except ValueError:
            continue
        combined[(entry_post_id, entry_platform)] = entry
    result = [
        entry
        for (entry_post_id, entry_platform), entry in combined.items()
        if (post_id is None or entry_post_id == post_id)
        and (normalized_platform is None or entry_platform == normalized_platform)
    ]
    return sorted(result, key=lambda item: (str(item.get("post_id")), str(item.get("platform"))))


def summarize_statuses(payload: dict, manifest: dict | None = None) -> dict:
    entries = list_statuses(payload, manifest)
    by_status = {status: 0 for status in ALLOWED_STATUSES}
    by_platform = {
        platform: {status: 0 for status in ALLOWED_STATUSES} for platform in ALLOWED_PLATFORMS
    }
    for entry in entries:
        status = normalize_status(str(entry.get("status", "pending")))
        platform = normalize_platform(str(entry.get("platform")))
        by_status[status] += 1
        by_platform[platform][status] += 1
    return {
        "total": len(entries),
        "total_queueable": len(build_queue_platform_index(manifest)) if manifest is not None else None,
        "by_status": by_status,
        "by_platform": by_platform,
    }


def _warn_or_raise(message: str | None, strict: bool) -> None:
    if message is None:
        return
    if strict:
        raise ValueError(message)
    print(f"Warning: {message}", file=sys.stderr)


def _validate_list_strict(
    entries: list[dict], manifest: dict | None, index: dict[tuple[str, str], dict], strict: bool
) -> None:
    if not strict or manifest is None:
        return
    for entry in entries:
        post_id = str(entry.get("post_id", ""))
        platform = normalize_platform(str(entry.get("platform", "")))
        _warn_or_raise(_manifest_warning(manifest, index, post_id, platform), True)


def _print_statuses_text(entries: list[dict]) -> None:
    print(f"{'POST ID':<24} {'PLATFORM':<18} {'STATUS':<10} UPDATED AT")
    for entry in entries:
        print(
            f"{str(entry.get('post_id', '')):<24} "
            f"{str(entry.get('platform', '')):<18} "
            f"{str(entry.get('status', '')):<10} "
            f"{entry.get('updated_at') or '-'}"
        )


def _print_summary_text(summary: dict) -> None:
    queueable = summary["total_queueable"]
    print(f"Total tracked/queueable combinations: {summary['total']}")
    print(f"Queueable combinations from manifest: {queueable if queueable is not None else '-'}")
    print(f"{'PLATFORM':<18} " + " ".join(f"{status.upper():>9}" for status in ALLOWED_STATUSES))
    for platform in ALLOWED_PLATFORMS:
        counts = summary["by_platform"][platform]
        print(f"{platform:<18} " + " ".join(f"{counts[status]:>9}" for status in ALLOWED_STATUSES))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track local manual publish outcomes.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    mark = subparsers.add_parser("mark", help="Create or update one post/platform status.")
    mark.add_argument("--post-id", required=True)
    mark.add_argument("--platform", required=True)
    mark.add_argument("--status", required=True)
    mark.add_argument("--external-url")
    mark.add_argument("--notes")
    mark.add_argument("--status-file", default=str(DEFAULT_STATUS_FILE))
    mark.add_argument("--publish-queue-manifest", default=str(DEFAULT_MANIFEST))
    mark.add_argument("--now")
    mark.add_argument("--strict", action="store_true")

    listing = subparsers.add_parser("list", help="List recorded and pending queue statuses.")
    listing.add_argument("--status-file", default=str(DEFAULT_STATUS_FILE))
    listing.add_argument("--publish-queue-manifest", default=str(DEFAULT_MANIFEST))
    listing.add_argument("--post-id")
    listing.add_argument("--platform")
    listing.add_argument("--format", choices=("json", "text"), default="json")
    listing.add_argument("--strict", action="store_true")

    summary = subparsers.add_parser("summary", help="Summarize statuses by platform and outcome.")
    summary.add_argument("--status-file", default=str(DEFAULT_STATUS_FILE))
    summary.add_argument("--publish-queue-manifest", default=str(DEFAULT_MANIFEST))
    summary.add_argument("--format", choices=("json", "text"), default="json")
    summary.add_argument("--strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        status_file = Path(args.status_file)
        manifest = load_publish_queue_manifest(Path(args.publish_queue_manifest))
        payload = load_status_file(status_file)
        index = build_queue_platform_index(manifest)

        if args.command == "mark":
            platform = normalize_platform(args.platform)
            _warn_or_raise(_manifest_warning(manifest, index, args.post_id, platform), args.strict)
            entry = mark_status(
                payload,
                post_id=args.post_id,
                platform=platform,
                status=args.status,
                external_url=args.external_url,
                notes=args.notes,
                now=args.now,
            )
            write_status_file_atomically(payload, status_file)
            print(json.dumps(entry, indent=2, sort_keys=True))
            return 0

        if args.command == "list":
            platform = normalize_platform(args.platform) if args.platform is not None else None
            _warn_or_raise(
                _manifest_filter_warning(manifest, index, args.post_id, platform), args.strict
            )
            entries = list_statuses(payload, manifest, post_id=args.post_id, platform=platform)
            _validate_list_strict(entries, manifest, index, args.strict)
            if args.format == "text":
                _print_statuses_text(entries)
            else:
                print(json.dumps(entries, indent=2, sort_keys=True))
            return 0

        entries = list_statuses(payload, manifest)
        _validate_list_strict(entries, manifest, index, args.strict)
        summary = summarize_statuses(payload, manifest)
        if args.format == "text":
            _print_summary_text(summary)
        else:
            print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
