from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from scripts.run_daily_workflow import build_parser, main, run_daily_workflow


def _args(**overrides) -> argparse.Namespace:
    defaults = vars(build_parser().parse_args([]))
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _completed(command: list[str], returncode: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(command, returncode, "{}", stderr)


def test_default_commands_run_pipeline_then_report():
    calls: list[list[str]] = []

    def record(command, **_):
        calls.append(command)
        return _completed(command)

    with patch("scripts.run_daily_workflow.subprocess.run", side_effect=record):
        summary = run_daily_workflow(_args(python_executable="python"))

    assert calls[0][:2] == ["python", "scripts/run_local_pipeline.py"]
    assert calls[1][:2] == ["python", "scripts/build_pipeline_report.py"]
    assert summary["success"] is True


def test_pipeline_flags_are_forwarded():
    calls: list[list[str]] = []

    def record(command, **_):
        calls.append(command)
        return _completed(command)

    args = _args(overwrite=True, dry_run=True, continue_on_error=True, python_executable="python")
    with patch("scripts.run_daily_workflow.subprocess.run", side_effect=record):
        run_daily_workflow(args)

    pipeline_command = calls[0]
    assert "--overwrite" in pipeline_command
    assert "--dry-run" in pipeline_command
    assert "--continue-on-error" in pipeline_command


def test_python_executable_used_for_both_commands():
    calls: list[list[str]] = []

    def record(command, **_):
        calls.append(command)
        return _completed(command)

    executable = r"C:\custom\python.exe"
    with patch("scripts.run_daily_workflow.subprocess.run", side_effect=record):
        run_daily_workflow(_args(python_executable=executable))

    assert calls[0][0] == executable
    assert calls[1][0] == executable
    python_flag = calls[0].index("--python-executable")
    assert calls[0][python_flag + 1] == executable


def test_custom_summary_path_used_by_both_stages(tmp_path: Path):
    calls: list[list[str]] = []

    def record(command, **_):
        calls.append(command)
        return _completed(command)

    summary_path = tmp_path / "custom-summary.json"
    with patch("scripts.run_daily_workflow.subprocess.run", side_effect=record):
        run_daily_workflow(_args(summary_json=str(summary_path), python_executable="python"))

    assert str(summary_path) in calls[0]
    assert str(summary_path) in calls[1]


def test_custom_report_paths_passed_to_report_builder(tmp_path: Path):
    calls: list[list[str]] = []

    def record(command, **_):
        calls.append(command)
        return _completed(command)

    report_md = tmp_path / "custom.md"
    report_json = tmp_path / "custom.json"
    args = _args(report_md=str(report_md), report_json=str(report_json), python_executable="python")
    with patch("scripts.run_daily_workflow.subprocess.run", side_effect=record):
        summary = run_daily_workflow(args)

    assert str(report_md) in calls[1]
    assert str(report_json) in calls[1]
    assert summary["report_json"] == report_json.as_posix()


def test_report_attempted_when_pipeline_fails_and_summary_exists(tmp_path: Path):
    summary_path = tmp_path / "summary.json"
    summary_path.write_text("{}", encoding="utf-8")
    calls: list[list[str]] = []

    def fail_pipeline(command, **_):
        calls.append(command)
        return _completed(command, returncode=1 if len(calls) == 1 else 0, stderr="pipeline failed")

    with patch("scripts.run_daily_workflow.subprocess.run", side_effect=fail_pipeline):
        summary = run_daily_workflow(_args(summary_json=str(summary_path), python_executable="python"))

    assert len(calls) == 2
    assert calls[1][1] == "scripts/build_pipeline_report.py"
    assert summary["pipeline_returncode"] == 1
    assert summary["report_returncode"] == 0
    assert summary["success"] is False


def test_pipeline_failure_without_summary_skips_report(tmp_path: Path):
    with patch(
        "scripts.run_daily_workflow.subprocess.run",
        side_effect=lambda command, **_: _completed(command, returncode=1, stderr="failed"),
    ) as mocked_run:
        summary = run_daily_workflow(_args(summary_json=str(tmp_path / "missing.json"), python_executable="python"))

    assert mocked_run.call_count == 1
    assert summary["report_returncode"] is None
    assert summary["success"] is False
    assert "summary is missing" in summary["warnings"][0]


def test_report_failure_makes_final_success_false():
    calls = 0

    def fail_report(command, **_):
        nonlocal calls
        calls += 1
        return _completed(command, returncode=3 if calls == 2 else 0, stderr="report failed")

    with patch("scripts.run_daily_workflow.subprocess.run", side_effect=fail_report):
        summary = run_daily_workflow(_args(python_executable="python"))

    assert summary["pipeline_returncode"] == 0
    assert summary["report_returncode"] == 3
    assert summary["success"] is False
    assert "report failed" in summary["errors"][0]


def test_open_report_opens_existing_path(tmp_path: Path):
    report_path = tmp_path / "report.md"
    report_path.write_text("report", encoding="utf-8")

    with (
        patch("scripts.run_daily_workflow.subprocess.run", side_effect=lambda command, **_: _completed(command)),
        patch("scripts.run_daily_workflow.open_path", return_value=(True, "")) as mocked_open,
    ):
        summary = run_daily_workflow(_args(report_md=str(report_path), open_report=True, python_executable="python"))

    mocked_open.assert_called_once_with(report_path)
    assert summary["opened_report"] is True


def test_open_publish_queue_opens_existing_directory(tmp_path: Path):
    queue_dir = tmp_path / "queue"
    queue_dir.mkdir()

    with (
        patch("scripts.run_daily_workflow.subprocess.run", side_effect=lambda command, **_: _completed(command)),
        patch("scripts.run_daily_workflow.open_path", return_value=(True, "")) as mocked_open,
    ):
        summary = run_daily_workflow(
            _args(publish_queue_dir=str(queue_dir), open_publish_queue=True, python_executable="python")
        )

    mocked_open.assert_called_once_with(queue_dir)
    assert summary["opened_publish_queue"] is True


def test_open_failure_is_warning_not_hard_failure(tmp_path: Path):
    report_path = tmp_path / "report.md"
    report_path.write_text("report", encoding="utf-8")

    with (
        patch("scripts.run_daily_workflow.subprocess.run", side_effect=lambda command, **_: _completed(command)),
        patch("scripts.run_daily_workflow.open_path", return_value=(False, "no default app")),
    ):
        summary = run_daily_workflow(_args(report_md=str(report_path), open_report=True, python_executable="python"))

    assert summary["success"] is True
    assert summary["opened_report"] is False
    assert "no default app" in summary["warnings"][0]


def test_missing_report_path_is_warning(tmp_path: Path):
    report_path = tmp_path / "missing.md"

    with patch("scripts.run_daily_workflow.subprocess.run", side_effect=lambda command, **_: _completed(command)):
        summary = run_daily_workflow(_args(report_md=str(report_path), open_report=True, python_executable="python"))

    assert summary["success"] is True
    assert summary["opened_report"] is False
    assert "does not exist" in summary["warnings"][0]


def test_subprocess_start_failure_is_reported(tmp_path: Path):
    with patch("scripts.run_daily_workflow.subprocess.run", side_effect=OSError("missing executable")):
        summary = run_daily_workflow(_args(summary_json=str(tmp_path / "missing.json"), python_executable="bad-python"))

    assert summary["success"] is False
    assert "Failed to start command" in summary["errors"][0]


def test_summary_json_printed_to_stdout(capsys):
    with (
        patch("scripts.run_daily_workflow.subprocess.run", side_effect=lambda command, **_: _completed(command)),
        patch("sys.argv", ["run_daily_workflow.py", "--python-executable", "python"]),
    ):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["success"] is True
    assert summary["summary_json"] == "runtime/reports/latest_pipeline_summary.json"
    assert summary["report_md"] == "runtime/reports/latest_pipeline_report.md"
