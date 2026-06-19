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


def load_json_file(path: Path) -> tuple[dict | None, str | None]:
    if not path.exists():
        return None, f"Missing file: {path_for_json(path)}"
    if not path.is_file():
        return None, f"Path is not a file: {path_for_json(path)}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"Invalid JSON file {path_for_json(path)}: {exc}"
    if not isinstance(payload, dict):
        return None, f"Invalid JSON file {path_for_json(path)}: top-level must be an object"
    return payload, None


def _list_of_dicts(payload: dict | None, key: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
        return []
    return [item for item in payload[key] if isinstance(item, dict)]


def _count(payload: dict | None, key: str, fallback: int) -> int:
    value = payload.get(key) if isinstance(payload, dict) else None
    return value if isinstance(value, int) and value >= 0 else fallback


def _item_errors(items: list[dict[str, Any]], error_key: str, id_key: str = "post_id") -> list[str]:
    errors: list[str] = []
    for item in items:
        item_errors = item.get(error_key, [])
        if not isinstance(item_errors, list):
            continue
        item_id = str(item.get(id_key) or "").strip()
        for error in item_errors:
            if str(error).strip():
                errors.append(f"{item_id}: {error}" if item_id else str(error))
    return errors


def _invalid_errors(items: list[dict[str, Any]], path_key: str) -> list[str]:
    errors: list[str] = []
    for item in items:
        error = str(item.get("error") or "Invalid artifact").strip()
        artifact_path = str(item.get(path_key) or "").strip()
        errors.append(f"{artifact_path}: {error}" if artifact_path else error)
    return errors


def _manifest_errors(payload: dict | None) -> list[str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("errors"), list):
        return []
    return [str(error) for error in payload["errors"] if str(error).strip()]


def summarize_render_manifest(payload: dict | None) -> dict[str, Any]:
    renders = _list_of_dicts(payload, "renders")
    invalid_renders = _list_of_dicts(payload, "invalid_renders")
    invalid = _count(payload, "invalid_render_count", len(invalid_renders))
    issues = _manifest_errors(payload)
    issues.extend(_invalid_errors(invalid_renders, "render_dir"))
    issues.extend(_item_errors(renders, "render_errors"))
    return {
        "total": _count(payload, "render_count", len(renders)),
        "invalid": invalid,
        "ready": sum(render.get("ready_for_publish") is True for render in renders),
        "issues": issues,
    }


def summarize_video_manifest(payload: dict | None) -> dict[str, Any]:
    videos = _list_of_dicts(payload, "videos")
    invalid_videos = _list_of_dicts(payload, "invalid_videos")
    invalid = _count(payload, "invalid_video_count", len(invalid_videos))
    issues = _manifest_errors(payload)
    issues.extend(_invalid_errors(invalid_videos, "video_dir"))
    issues.extend(_item_errors(videos, "video_errors"))
    return {
        "total": _count(payload, "video_count", len(videos)),
        "invalid": invalid,
        "ready": sum(video.get("ready_for_upload") is True for video in videos),
        "issues": issues,
    }


def summarize_publish_queue_manifest(payload: dict | None) -> dict[str, Any]:
    packets = _list_of_dicts(payload, "packets")
    invalid_packets = _list_of_dicts(payload, "invalid_packets")
    invalid = _count(payload, "invalid_packet_count", len(invalid_packets))
    issues = _manifest_errors(payload)
    issues.extend(_invalid_errors(invalid_packets, "packet_dir"))
    issues.extend(_item_errors(packets, "packet_errors"))
    ready_packets = [packet for packet in packets if packet.get("packet_ready") is True]
    return {
        "total": _count(payload, "packet_count", len(packets)),
        "invalid": invalid,
        "ready": len(ready_packets),
        "issues": issues,
        "packets": packets,
        "ready_packets": ready_packets,
    }


def summarize_pipeline_runner(payload: dict | None) -> dict[str, Any]:
    if payload is None:
        return {
            "provided": False,
            "success": None,
            "duration_seconds": None,
            "dry_run": None,
            "overwrite": None,
            "stage_count": 0,
            "failed_stages": [],
            "skipped_stages": [],
            "errors": [],
        }

    stages = _list_of_dicts(payload, "stages")
    failed_stages = []
    skipped_stages = []
    for stage in stages:
        name = str(stage.get("name") or "unknown")
        if stage.get("skipped") is True:
            reason = str(stage.get("skip_reason") or "unspecified")
            skipped_stages.append(f"{name} ({reason})")
        elif stage.get("returncode") not in (None, 0) or stage.get("error"):
            detail = str(stage.get("error") or f'return code {stage.get("returncode")}')
            failed_stages.append(f"{name}: {detail}")

    errors = _manifest_errors(payload)
    errors.extend(failed_stages)
    if payload.get("success") is False and not errors:
        errors.append("Pipeline summary reports failure")
    return {
        "provided": True,
        "success": payload.get("success"),
        "duration_seconds": payload.get("duration_seconds"),
        "dry_run": payload.get("dry_run"),
        "overwrite": payload.get("overwrite"),
        "stage_count": len(stages),
        "failed_stages": failed_stages,
        "skipped_stages": skipped_stages,
        "errors": errors,
    }


def _ready_packet_summary(packet: dict[str, Any]) -> dict[str, Any]:
    platforms = packet.get("platforms", [])
    if not isinstance(platforms, list):
        platforms = []
    return {
        "post_id": str(packet.get("post_id") or ""),
        "source_account_handle": str(packet.get("source_account_handle") or ""),
        "source_url": str(packet.get("source_url") or ""),
        "platforms": [str(platform) for platform in platforms],
        "video_path": str(packet.get("video_path") or ""),
        "caption_path": str(packet.get("caption_path") or ""),
        "metadata_path": str(packet.get("metadata_path") or ""),
    }


def _source_status(path: Path, payload: dict | None) -> str:
    if payload is not None:
        return "loaded"
    return "invalid" if path.exists() else "missing"


def build_report_summary(
    *,
    render_payload: dict | None,
    video_payload: dict | None,
    publish_payload: dict | None,
    pipeline_payload: dict | None,
    render_manifest: Path,
    video_manifest: Path,
    publish_queue_manifest: Path,
    pipeline_summary: Path | None,
    output_md: Path,
    output_json: Path | None,
    load_errors: dict[str, str | None],
) -> dict[str, Any]:
    renders = summarize_render_manifest(render_payload)
    videos = summarize_video_manifest(video_payload)
    publish_packets = summarize_publish_queue_manifest(publish_payload)
    pipeline = summarize_pipeline_runner(pipeline_payload)
    warnings: list[str] = []
    errors: list[str] = []

    if load_errors.get("render"):
        warnings.append(load_errors["render"] or "Render manifest unavailable")
    if load_errors.get("video"):
        warnings.append(load_errors["video"] or "Video manifest unavailable")
    if load_errors.get("publish"):
        errors.append(load_errors["publish"] or "Publish queue manifest unavailable")
    if pipeline_summary is not None and load_errors.get("pipeline"):
        warnings.append(load_errors["pipeline"] or "Pipeline summary unavailable")

    if render_payload is not None:
        if renders["invalid"]:
            warnings.append(f'{renders["invalid"]} invalid render artifact(s) reported')
        warnings.extend(f"Render: {issue}" for issue in renders["issues"])
    if video_payload is not None:
        if videos["invalid"]:
            warnings.append(f'{videos["invalid"]} invalid video artifact(s) reported')
        warnings.extend(f"Video: {issue}" for issue in videos["issues"])
    if publish_payload is not None:
        if publish_packets["invalid"]:
            errors.append(f'{publish_packets["invalid"]} invalid publish packet(s) reported')
        errors.extend(f"Publish packet: {issue}" for issue in publish_packets["issues"])
        if publish_packets["ready"] == 0:
            errors.append("No publish packets are ready for manual upload")
    errors.extend(f"Pipeline: {error}" for error in pipeline["errors"])

    ready_packets = [_ready_packet_summary(packet) for packet in publish_packets["ready_packets"]]
    overall_ready = publish_payload is not None and bool(ready_packets) and not errors
    return {
        "generated_at": utc_now_iso(),
        "output_md": path_for_json(output_md),
        "output_json": path_for_json(output_json) if output_json else None,
        "render_manifest_found": render_manifest.is_file(),
        "video_manifest_found": video_manifest.is_file(),
        "publish_queue_manifest_found": publish_queue_manifest.is_file(),
        "pipeline_summary_found": pipeline_summary.is_file() if pipeline_summary else False,
        "overall_ready": overall_ready,
        "publish_ready_count": len(ready_packets),
        "warnings": warnings,
        "errors": errors,
        "counts": {
            "renders": {key: renders[key] for key in ("total", "invalid", "ready")},
            "videos": {key: videos[key] for key in ("total", "invalid", "ready")},
            "publish_packets": {key: publish_packets[key] for key in ("total", "invalid", "ready")},
        },
        "source_status": {
            "render_manifest": _source_status(render_manifest, render_payload),
            "video_manifest": _source_status(video_manifest, video_payload),
            "publish_queue_manifest": _source_status(publish_queue_manifest, publish_payload),
            "pipeline_summary": _source_status(pipeline_summary, pipeline_payload) if pipeline_summary else "not-provided",
        },
        "pipeline_summary": pipeline,
        "publish_packets": publish_packets["packets"],
        "ready_packets": ready_packets,
        "paths": {
            "render_manifest": path_for_json(render_manifest),
            "video_manifest": path_for_json(video_manifest),
            "publish_queue_manifest": path_for_json(publish_queue_manifest),
            "pipeline_summary": path_for_json(pipeline_summary) if pipeline_summary else None,
            "report_md": path_for_json(output_md),
        },
    }


def _display(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _inline(value: Any, fallback: str = "unknown") -> str:
    text = " ".join(str(value or "").split()).replace("|", "\\|")
    return text or fallback


def render_markdown_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    pipeline = summary["pipeline_summary"]
    source_status = summary["source_status"]
    lines = [
        "# Economika Local Pipeline Report",
        "",
        "## Status",
        "",
        f'- **Overall ready:** {"yes" if summary["overall_ready"] else "no"}',
        f'- **Generated at:** {summary["generated_at"]}',
        f'- **Warnings:** {len(summary["warnings"])}',
        f'- **Errors:** {len(summary["errors"])}',
        "",
        "## Pipeline Summary",
        "",
    ]
    if not pipeline["provided"]:
        lines.append("No pipeline runner summary provided.")
    else:
        lines.extend(
            [
                f'- Success: {_display(pipeline["success"])}',
                f'- Duration seconds: {_display(pipeline["duration_seconds"])}',
                f'- Dry run: {_display(pipeline["dry_run"])}',
                f'- Overwrite: {_display(pipeline["overwrite"])}',
                f'- Stage count: {pipeline["stage_count"]}',
                f'- Failed stages: {len(pipeline["failed_stages"])}',
                f'- Skipped stages: {len(pipeline["skipped_stages"])}',
            ]
        )
        for failed in pipeline["failed_stages"]:
            lines.append(f"  - Failed: {_inline(failed)}")
        for skipped in pipeline["skipped_stages"]:
            lines.append(f"  - Skipped: {_inline(skipped)}")

    lines.extend(
        [
            "",
            "## Artifact Counts",
            "",
            "| Artifact | Count | Invalid | Ready |",
            "| --- | ---: | ---: | ---: |",
            f'| Render cards | {counts["renders"]["total"]} | {counts["renders"]["invalid"]} | {counts["renders"]["ready"]} |',
            f'| Videos | {counts["videos"]["total"]} | {counts["videos"]["invalid"]} | {counts["videos"]["ready"]} |',
            f'| Publish packets | {counts["publish_packets"]["total"]} | {counts["publish_packets"]["invalid"]} | {counts["publish_packets"]["ready"]} |',
            "",
            f'- Render manifest: {source_status["render_manifest"]}',
            f'- Video manifest: {source_status["video_manifest"]}',
            f'- Publish queue manifest: {source_status["publish_queue_manifest"]}',
            "",
            "## Publish Queue",
            "",
        ]
    )
    packets = summary["publish_packets"]
    if not packets:
        lines.append("No publish packets found.")
    for packet in packets:
        handle = _inline(packet.get("source_account_handle"))
        source = handle if handle == "unknown" or handle.startswith("@") else f"@{handle}"
        platforms = packet.get("platforms", [])
        platform_text = ", ".join(str(platform) for platform in platforms) if isinstance(platforms, list) else "unknown"
        lines.extend(
            [
                f'### {_inline(packet.get("post_id"), "unknown post")}',
                "",
                f"- Source: {source}",
                f'- Source URL: {_inline(packet.get("source_url"))}',
                f"- Platforms: {_inline(platform_text)}",
                f'- Packet ready: {_display(packet.get("packet_ready") is True)}',
                f'- Video path: `{_inline(packet.get("video_path"), "")}`',
                f'- Caption path: `{_inline(packet.get("caption_path"), "")}`',
                f'- Metadata path: `{_inline(packet.get("metadata_path"), "")}`',
                f'- Caption preview: {_inline(packet.get("caption_preview"), "none")}',
                "",
            ]
        )

    lines.extend(["## Errors and Warnings", "", "### Errors", ""])
    lines.extend(f"- {_inline(error)}" for error in summary["errors"])
    if not summary["errors"]:
        lines.append("- None")
    lines.extend(["", "### Warnings", ""])
    lines.extend(f"- {_inline(warning)}" for warning in summary["warnings"])
    if not summary["warnings"]:
        lines.append("- None")

    lines.extend(["", "## Manual Upload Checklist", ""])
    if not summary["ready_packets"]:
        lines.append("No packets are ready for manual upload.")
    for packet in summary["ready_packets"]:
        platforms = ", ".join(packet["platforms"]) or "unspecified platforms"
        lines.extend(
            [
                f'### {_inline(packet["post_id"], "unknown post")}',
                "",
                f'- [ ] Review video: `{_inline(packet["video_path"], "")}`',
                f'- [ ] Copy caption: `{_inline(packet["caption_path"], "")}`',
                f"- [ ] Upload manually to: {_inline(platforms)}",
                "- [ ] Confirm published externally",
                "",
            ]
        )

    paths = summary["paths"]
    lines.extend(
        [
            "## Final Paths",
            "",
            f'- Render manifest: `{paths["render_manifest"]}`',
            f'- Video manifest: `{paths["video_manifest"]}`',
            f'- Publish queue manifest: `{paths["publish_queue_manifest"]}`',
            f'- Report: `{paths["report_md"]}`',
            "",
            "This report supports local manual review only. It does not publish or upload content.",
            "",
        ]
    )
    return "\n".join(lines)


def write_text_atomically(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8")
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def write_json_atomically(payload: dict, path: Path) -> None:
    write_text_atomically(json.dumps(payload, indent=2, sort_keys=True) + "\n", path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local Markdown pipeline health report.")
    parser.add_argument("--render-manifest", default="runtime/renders/manifest.json")
    parser.add_argument("--video-manifest", default="runtime/videos/manifest.json")
    parser.add_argument("--publish-queue-manifest", default="runtime/publish_queue/manifest.json")
    parser.add_argument("--pipeline-summary", default=None)
    parser.add_argument("--output-md", default="runtime/reports/latest_pipeline_report.md")
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--pretty", action="store_true", default=False)
    args = parser.parse_args()

    render_manifest = Path(args.render_manifest)
    video_manifest = Path(args.video_manifest)
    publish_queue_manifest = Path(args.publish_queue_manifest)
    pipeline_summary = Path(args.pipeline_summary) if args.pipeline_summary else None
    output_md = Path(args.output_md)
    output_json = Path(args.output_json) if args.output_json else None

    render_payload, render_error = load_json_file(render_manifest)
    video_payload, video_error = load_json_file(video_manifest)
    publish_payload, publish_error = load_json_file(publish_queue_manifest)
    pipeline_payload, pipeline_error = (load_json_file(pipeline_summary) if pipeline_summary else (None, None))
    summary = build_report_summary(
        render_payload=render_payload,
        video_payload=video_payload,
        publish_payload=publish_payload,
        pipeline_payload=pipeline_payload,
        render_manifest=render_manifest,
        video_manifest=video_manifest,
        publish_queue_manifest=publish_queue_manifest,
        pipeline_summary=pipeline_summary,
        output_md=output_md,
        output_json=output_json,
        load_errors={
            "render": render_error,
            "video": video_error,
            "publish": publish_error,
            "pipeline": pipeline_error,
        },
    )

    try:
        write_text_atomically(render_markdown_report(summary), output_md)
        if output_json:
            write_json_atomically(summary, output_json)
    except OSError as exc:
        print(f"Error: failed to write pipeline report: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
