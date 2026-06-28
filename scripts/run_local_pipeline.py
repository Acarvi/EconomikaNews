from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


STAGES = (
    {
        "name": "build_render_inputs",
        "script": "scripts/build_render_inputs.py",
        "skip_flag": "skip_render_inputs",
        "supports_overwrite": True,
        "supports_dry_run": True,
        "supports_limit": False,
        "manifest_writer": False,
    },
    {
        "name": "render_cards",
        "script": "scripts/render_text_cards.py",
        "skip_flag": "skip_cards",
        "supports_overwrite": True,
        "supports_dry_run": True,
        "supports_limit": True,
        "manifest_writer": False,
    },
    {
        "name": "build_render_manifest",
        "script": "scripts/build_render_manifest.py",
        "skip_flag": "skip_render_manifest",
        "supports_overwrite": False,
        "supports_dry_run": False,
        "supports_limit": False,
        "manifest_writer": True,
    },
    {
        "name": "export_videos",
        "script": "scripts/export_card_videos.py",
        "skip_flag": "skip_videos",
        "supports_overwrite": True,
        "supports_dry_run": True,
        "supports_limit": True,
        "supports_duration_seconds": True,
        "manifest_writer": False,
    },
    {
        "name": "build_video_manifest",
        "script": "scripts/build_video_manifest.py",
        "skip_flag": "skip_video_manifest",
        "supports_overwrite": False,
        "supports_dry_run": False,
        "supports_limit": False,
        "manifest_writer": True,
    },
    {
        "name": "build_publish_queue",
        "script": "scripts/build_publish_queue.py",
        "skip_flag": "skip_publish_queue",
        "supports_overwrite": True,
        "supports_dry_run": True,
        "supports_limit": True,
        "manifest_writer": False,
    },
    {
        "name": "build_publish_queue_manifest",
        "script": "scripts/build_publish_queue_manifest.py",
        "skip_flag": "skip_publish_queue_manifest",
        "supports_overwrite": False,
        "supports_dry_run": False,
        "supports_limit": False,
        "manifest_writer": True,
    },
)

ARTIFACTS = {
    "render_manifest": "runtime/renders/manifest.json",
    "video_manifest": "runtime/videos/manifest.json",
    "publish_queue_manifest": "runtime/publish_queue/manifest.json",
}


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_stdout_json(stdout: str) -> Any | None:
    try:
        return json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return None


def build_command(
    stage: dict[str, Any],
    *,
    python_executable: str,
    overwrite: bool,
    dry_run: bool,
    limit: int | None,
    duration_seconds: float | None = None,
) -> list[str]:
    command = [python_executable, stage["script"]]
    if overwrite and stage["supports_overwrite"]:
        command.append("--overwrite")
    if dry_run and stage["supports_dry_run"]:
        command.append("--dry-run")
    if limit is not None and stage["supports_limit"]:
        command.extend(["--limit", str(limit)])
    if duration_seconds is not None and stage.get("supports_duration_seconds"):
        command.extend(["--duration-seconds", str(duration_seconds)])
    return command


def skipped_stage(name: str, reason: str) -> dict[str, Any]:
    now = utc_now_iso()
    return {
        "name": name,
        "command": [],
        "returncode": 0,
        "stdout_json": None,
        "stdout": "",
        "stderr": "",
        "started_at": now,
        "finished_at": now,
        "duration_seconds": 0.0,
        "skipped": True,
        "skip_reason": reason,
        "error": "",
    }


def run_stage(name: str, command: list[str]) -> dict[str, Any]:
    started_at = utc_now_iso()
    started_clock = time.perf_counter()
    stdout = ""
    stderr = ""
    returncode = 1
    error = ""

    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        returncode = completed.returncode
        if returncode != 0:
            error = f"Stage exited with code {returncode}"
    except OSError as exc:
        error = f"Failed to start stage: {exc}"

    return {
        "name": name,
        "command": command,
        "returncode": returncode,
        "stdout_json": parse_stdout_json(stdout),
        "stdout": stdout,
        "stderr": stderr,
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "duration_seconds": round(time.perf_counter() - started_clock, 3),
        "skipped": False,
        "error": error,
    }


def run_local_pipeline(
    *,
    overwrite: bool = False,
    dry_run: bool = False,
    stop_on_error: bool = True,
    limit: int | None = None,
    duration_seconds: float | None = None,
    skip_flags: set[str] | None = None,
    python_executable: str = sys.executable,
) -> dict[str, Any]:
    started_at = utc_now_iso()
    started_clock = time.perf_counter()
    stages: list[dict[str, Any]] = []
    errors: list[str] = []
    stopped = False
    skip_flags = skip_flags or set()

    for stage in STAGES:
        if stage["skip_flag"] in skip_flags:
            stages.append(skipped_stage(stage["name"], "cli-flag"))
            continue
        if dry_run and stage["manifest_writer"]:
            stages.append(skipped_stage(stage["name"], "dry-run"))
            continue
        if stopped:
            stages.append(skipped_stage(stage["name"], "stopped-after-error"))
            continue

        command = build_command(
            stage,
            python_executable=python_executable,
            overwrite=overwrite,
            dry_run=dry_run,
            limit=limit,
            duration_seconds=duration_seconds,
        )
        result = run_stage(stage["name"], command)
        stages.append(result)
        if result["returncode"] != 0:
            errors.append(f'{stage["name"]}: {result["error"]}')
            stopped = stop_on_error

    return {
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "duration_seconds": round(time.perf_counter() - started_clock, 3),
        "success": not errors,
        "dry_run": dry_run,
        "overwrite": overwrite,
        "stop_on_error": stop_on_error,
        "stages": stages,
        "errors": errors,
        "artifacts": dict(ARTIFACTS),
    }


def write_summary_atomically(summary: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f"{output_path.name}.tmp")
    try:
        temp_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp_path, output_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full local artifact pipeline.")
    parser.add_argument("--overwrite", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--stop-on-error", action="store_true", dest="stop_on_error", default=True)
    parser.add_argument("--continue-on-error", action="store_false", dest="stop_on_error")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--duration-seconds", type=float, default=None)
    parser.add_argument("--skip-render-inputs", action="store_true", default=False)
    parser.add_argument("--skip-cards", action="store_true", default=False)
    parser.add_argument("--skip-render-manifest", action="store_true", default=False)
    parser.add_argument("--skip-videos", action="store_true", default=False)
    parser.add_argument("--skip-video-manifest", action="store_true", default=False)
    parser.add_argument("--skip-publish-queue", action="store_true", default=False)
    parser.add_argument("--skip-publish-queue-manifest", action="store_true", default=False)
    parser.add_argument("--summary-json", default=None)
    parser.add_argument("--python-executable", default=sys.executable)
    args = parser.parse_args()

    skip_flags = {
        name
        for name in (
            "skip_render_inputs",
            "skip_cards",
            "skip_render_manifest",
            "skip_videos",
            "skip_video_manifest",
            "skip_publish_queue",
            "skip_publish_queue_manifest",
        )
        if getattr(args, name)
    }
    summary = run_local_pipeline(
        overwrite=args.overwrite,
        dry_run=args.dry_run,
        stop_on_error=args.stop_on_error,
        limit=args.limit,
        duration_seconds=args.duration_seconds,
        skip_flags=skip_flags,
        python_executable=args.python_executable,
    )

    if args.summary_json:
        try:
            write_summary_atomically(summary, Path(args.summary_json))
        except OSError as exc:
            message = f"Failed to write summary JSON {args.summary_json}: {exc}"
            summary["success"] = False
            summary["errors"].append(message)
            print(f"Error: {message}", file=sys.stderr)

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
