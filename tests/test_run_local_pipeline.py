from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from scripts.run_local_pipeline import ARTIFACTS, STAGES, main, run_local_pipeline, write_summary_atomically


def _completed(command: list[str], returncode: int = 0, stdout: str = "{}", stderr: str = ""):
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


def test_default_stage_list_order():
    with patch("scripts.run_local_pipeline.subprocess.run", side_effect=lambda command, **_: _completed(command)):
        summary = run_local_pipeline(python_executable="python")

    assert [stage["name"] for stage in summary["stages"]] == [stage["name"] for stage in STAGES]


def test_overwrite_forwarded_only_to_supported_stages():
    with patch("scripts.run_local_pipeline.subprocess.run", side_effect=lambda command, **_: _completed(command)):
        summary = run_local_pipeline(overwrite=True, python_executable="python")

    commands = {stage["name"]: stage["command"] for stage in summary["stages"]}
    assert "--overwrite" in commands["build_render_inputs"]
    assert "--overwrite" in commands["render_cards"]
    assert "--overwrite" in commands["export_videos"]
    assert "--overwrite" in commands["build_publish_queue"]
    assert "--overwrite" not in commands["build_render_manifest"]
    assert "--overwrite" not in commands["build_video_manifest"]
    assert "--overwrite" not in commands["build_publish_queue_manifest"]


def test_dry_run_forwarded_to_supported_stages_and_skips_manifest_writers():
    with patch("scripts.run_local_pipeline.subprocess.run", side_effect=lambda command, **_: _completed(command)):
        summary = run_local_pipeline(dry_run=True, python_executable="python")

    by_name = {stage["name"]: stage for stage in summary["stages"]}
    for name in ("build_render_inputs", "render_cards", "export_videos", "build_publish_queue"):
        assert "--dry-run" in by_name[name]["command"]
    for name in ("build_render_manifest", "build_video_manifest", "build_publish_queue_manifest"):
        assert by_name[name]["skipped"] is True
        assert by_name[name]["skip_reason"] == "dry-run"
        assert by_name[name]["command"] == []


def test_limit_forwarded_only_to_supported_stages():
    with patch("scripts.run_local_pipeline.subprocess.run", side_effect=lambda command, **_: _completed(command)):
        summary = run_local_pipeline(limit=2, python_executable="python")

    commands = {stage["name"]: stage["command"] for stage in summary["stages"]}
    for name in ("render_cards", "export_videos", "build_publish_queue"):
        assert commands[name][-2:] == ["--limit", "2"]
    for name in ("build_render_inputs", "build_render_manifest", "build_video_manifest", "build_publish_queue_manifest"):
        assert "--limit" not in commands[name]


def test_duration_seconds_forwarded_only_to_video_export_stage():
    with patch("scripts.run_local_pipeline.subprocess.run", side_effect=lambda command, **_: _completed(command)):
        summary = run_local_pipeline(duration_seconds=4.5, python_executable="python")

    commands = {stage["name"]: stage["command"] for stage in summary["stages"]}
    assert commands["export_videos"][-2:] == ["--duration-seconds", "4.5"]
    for name in (
        "build_render_inputs",
        "render_cards",
        "build_render_manifest",
        "build_video_manifest",
        "build_publish_queue",
        "build_publish_queue_manifest",
    ):
        assert "--duration-seconds" not in commands[name]


def test_skipped_stage_appears_in_summary():
    with patch("scripts.run_local_pipeline.subprocess.run", side_effect=lambda command, **_: _completed(command)):
        summary = run_local_pipeline(skip_flags={"skip_cards"}, python_executable="python")

    stage = summary["stages"][1]
    assert stage["name"] == "render_cards"
    assert stage["skipped"] is True
    assert stage["skip_reason"] == "cli-flag"
    assert stage["command"] == []


def test_successful_subprocess_json_stdout_is_parsed():
    with patch(
        "scripts.run_local_pipeline.subprocess.run",
        side_effect=lambda command, **_: _completed(command, stdout='{"written": 3}'),
    ):
        summary = run_local_pipeline(python_executable="python")

    assert summary["success"] is True
    assert summary["stages"][0]["stdout_json"] == {"written": 3}


def test_non_json_stdout_is_kept_raw():
    with patch(
        "scripts.run_local_pipeline.subprocess.run",
        side_effect=lambda command, **_: _completed(command, stdout="plain output\n"),
    ):
        summary = run_local_pipeline(python_executable="python")

    assert summary["stages"][0]["stdout"] == "plain output\n"
    assert summary["stages"][0]["stdout_json"] is None


def test_stop_on_error_stops_subsequent_stages_and_exits_1(capsys):
    calls = 0

    def fail_first(command, **_):
        nonlocal calls
        calls += 1
        return _completed(command, returncode=4, stderr="failed")

    with (
        patch("scripts.run_local_pipeline.subprocess.run", side_effect=fail_first),
        patch("sys.argv", ["run_local_pipeline.py"]),
    ):
        assert main() == 1

    summary = json.loads(capsys.readouterr().out)
    assert calls == 1
    assert summary["success"] is False
    assert all(stage["skip_reason"] == "stopped-after-error" for stage in summary["stages"][1:])


def test_continue_on_error_runs_remaining_stages_and_exits_1(capsys):
    calls = 0

    def fail_first(command, **_):
        nonlocal calls
        calls += 1
        return _completed(command, returncode=2 if calls == 1 else 0)

    with (
        patch("scripts.run_local_pipeline.subprocess.run", side_effect=fail_first),
        patch("sys.argv", ["run_local_pipeline.py", "--continue-on-error"]),
    ):
        assert main() == 1

    summary = json.loads(capsys.readouterr().out)
    assert calls == len(STAGES)
    assert summary["stop_on_error"] is False
    assert summary["stages"][-1]["skipped"] is False


def test_summary_json_written_atomically(tmp_path: Path):
    output = tmp_path / "nested" / "summary.json"
    summary = {"success": True}

    with patch("os.replace", wraps=os.replace) as mock_replace:
        write_summary_atomically(summary, output)

    assert json.loads(output.read_text(encoding="utf-8")) == summary
    assert Path(mock_replace.call_args.args[0]).name == "summary.json.tmp"
    assert mock_replace.call_args.args[1] == output
    assert not output.with_name("summary.json.tmp").exists()


def test_final_summary_includes_artifact_paths():
    with patch("scripts.run_local_pipeline.subprocess.run", side_effect=lambda command, **_: _completed(command)):
        summary = run_local_pipeline(python_executable="python")

    assert summary["artifacts"] == ARTIFACTS


def test_python_executable_used_in_commands():
    executable = r"C:\custom\python.exe"
    with patch("scripts.run_local_pipeline.subprocess.run", side_effect=lambda command, **_: _completed(command)):
        summary = run_local_pipeline(python_executable=executable)

    assert all(stage["command"][0] == executable for stage in summary["stages"])


def test_invalid_summary_json_path_exits_1_with_clear_stderr(tmp_path: Path, capsys):
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("content", encoding="utf-8")
    output = parent_file / "summary.json"

    with (
        patch("scripts.run_local_pipeline.subprocess.run", side_effect=lambda command, **_: _completed(command)),
        patch("sys.argv", ["run_local_pipeline.py", "--summary-json", str(output)]),
    ):
        assert main() == 1

    captured = capsys.readouterr()
    assert "Failed to write summary JSON" in captured.err
    assert json.loads(captured.out)["success"] is False


def test_subprocess_launch_error_is_recorded_and_stops_pipeline():
    with patch("scripts.run_local_pipeline.subprocess.run", side_effect=OSError("missing executable")):
        summary = run_local_pipeline(python_executable="missing-python")

    assert summary["success"] is False
    assert summary["stages"][0]["returncode"] == 1
    assert "Failed to start stage" in summary["stages"][0]["error"]
    assert summary["stages"][1]["skip_reason"] == "stopped-after-error"
