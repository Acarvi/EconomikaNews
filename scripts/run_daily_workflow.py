from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def build_pipeline_command(args: argparse.Namespace) -> list[str]:
    command = [
        args.python_executable,
        "scripts/run_local_pipeline.py",
        "--summary-json",
        str(args.summary_json),
        "--python-executable",
        args.python_executable,
    ]
    if args.overwrite:
        command.append("--overwrite")
    if args.dry_run:
        command.append("--dry-run")
    if args.continue_on_error:
        command.append("--continue-on-error")
    return command


def build_report_command(args: argparse.Namespace) -> list[str]:
    command = [
        args.python_executable,
        "scripts/build_pipeline_report.py",
        "--pipeline-summary",
        str(args.summary_json),
        "--output-md",
        str(args.report_md),
    ]
    if args.report_json:
        command.extend(["--output-json", str(args.report_json)])
    return command


def run_command(command: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout or "",
            "stderr": completed.stderr or "",
            "error": "",
        }
    except OSError as exc:
        return {
            "command": command,
            "returncode": 1,
            "stdout": "",
            "stderr": "",
            "error": f"Failed to start command: {exc}",
        }


def open_path(path: Path) -> tuple[bool, str]:
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
            return True, ""

        command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            return False, detail or f"opener exited with code {completed.returncode}"
        return True, ""
    except OSError as exc:
        return False, str(exc)


def _command_error(label: str, result: dict[str, Any]) -> str:
    detail = str(result.get("error") or result.get("stderr") or "").strip()
    if len(detail) > 1000:
        detail = f"{detail[:1000].rstrip()}..."
    message = f'{label} failed with exit code {result["returncode"]}'
    return f"{message}: {detail}" if detail else message


def run_daily_workflow(args: argparse.Namespace) -> dict[str, Any]:
    summary_path = Path(args.summary_json)
    report_path = Path(args.report_md)
    report_json_path = Path(args.report_json) if args.report_json else None
    publish_queue_path = Path(args.publish_queue_dir)
    errors: list[str] = []
    warnings: list[str] = []

    pipeline_result = run_command(build_pipeline_command(args))
    pipeline_returncode = pipeline_result["returncode"]
    if pipeline_returncode != 0:
        errors.append(_command_error("Pipeline", pipeline_result))

    report_result: dict[str, Any] | None = None
    if pipeline_returncode == 0 or summary_path.is_file():
        report_result = run_command(build_report_command(args))
        if report_result["returncode"] != 0:
            errors.append(_command_error("Report generation", report_result))
    else:
        warnings.append(f"Report generation skipped because pipeline summary is missing: {summary_path.as_posix()}")

    opened_report = False
    if args.open_report:
        if report_path.is_file():
            opened_report, open_error = open_path(report_path)
            if not opened_report:
                warnings.append(f"Failed to open report {report_path.as_posix()}: {open_error}")
        else:
            warnings.append(f"Report path does not exist: {report_path.as_posix()}")

    opened_publish_queue = False
    if args.open_publish_queue:
        if publish_queue_path.is_dir():
            opened_publish_queue, open_error = open_path(publish_queue_path)
            if not opened_publish_queue:
                warnings.append(f"Failed to open publish queue {publish_queue_path.as_posix()}: {open_error}")
        else:
            warnings.append(f"Publish queue directory does not exist: {publish_queue_path.as_posix()}")

    report_returncode = report_result["returncode"] if report_result is not None else None
    return {
        "success": pipeline_returncode == 0 and report_returncode == 0,
        "pipeline_returncode": pipeline_returncode,
        "report_returncode": report_returncode,
        "summary_json": summary_path.as_posix(),
        "report_md": report_path.as_posix(),
        "report_json": report_json_path.as_posix() if report_json_path else None,
        "publish_queue_dir": publish_queue_path.as_posix(),
        "opened_report": opened_report,
        "opened_publish_queue": opened_publish_queue,
        "errors": errors,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the daily local pipeline and health report workflow.")
    parser.add_argument("--overwrite", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--continue-on-error", action="store_true", default=False)
    parser.add_argument("--summary-json", default="runtime/reports/latest_pipeline_summary.json")
    parser.add_argument("--report-md", default="runtime/reports/latest_pipeline_report.md")
    parser.add_argument("--report-json", default=None)
    parser.add_argument("--open-report", action="store_true", default=False)
    parser.add_argument("--open-publish-queue", action="store_true", default=False)
    parser.add_argument("--publish-queue-dir", default="runtime/publish_queue")
    parser.add_argument("--python-executable", default=sys.executable)
    return parser


def main() -> int:
    summary = run_daily_workflow(build_parser().parse_args())
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
