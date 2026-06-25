from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from scripts.build_pipeline_report import main, write_json_atomically, write_text_atomically


def _write_json(path: Path, payload: dict | list | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")


def _manifests(tmp_path: Path) -> tuple[Path, Path, Path]:
    render = tmp_path / "renders.json"
    video = tmp_path / "videos.json"
    publish = tmp_path / "publish.json"
    _write_json(
        render,
        {
            "render_count": 1,
            "invalid_render_count": 0,
            "renders": [{"post_id": "post-1", "ready_for_publish": True, "render_errors": []}],
            "invalid_renders": [],
        },
    )
    _write_json(
        video,
        {
            "video_count": 1,
            "invalid_video_count": 0,
            "videos": [{"post_id": "post-1", "ready_for_upload": True, "video_errors": []}],
            "invalid_videos": [],
        },
    )
    _write_json(
        publish,
        {
            "packet_count": 1,
            "invalid_packet_count": 0,
            "packets": [
                {
                    "post_id": "post-1",
                    "source_account_handle": "juanrallo",
                    "source_url": "https://x.com/juanrallo/status/1",
                    "platforms": ["tiktok", "youtube_shorts"],
                    "packet_ready": True,
                    "video_path": "runtime/publish_queue/post-1/video.mp4",
                    "caption_path": "runtime/publish_queue/post-1/caption.txt",
                    "metadata_path": "runtime/publish_queue/post-1/metadata.json",
                    "caption_preview": "Economic signal detected.",
                    "packet_errors": [],
                }
            ],
            "invalid_packets": [],
        },
    )
    return render, video, publish


def _run(tmp_path: Path, extra_args: list[str] | None = None) -> tuple[int, str, str]:
    render, video, publish = _manifests(tmp_path)
    output = tmp_path / "report.md"
    args = [
        "build_pipeline_report.py",
        "--render-manifest",
        str(render),
        "--video-manifest",
        str(video),
        "--publish-queue-manifest",
        str(publish),
        "--output-md",
        str(output),
    ]
    args.extend(extra_args or [])
    with patch("sys.argv", args):
        exit_code = main()
    return exit_code, output.read_text(encoding="utf-8"), str(output)


def test_all_manifests_valid_creates_markdown_report(tmp_path: Path, capsys):
    exit_code, markdown, output = _run(tmp_path)
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert Path(output).exists()
    assert summary["overall_ready"] is True
    assert "# Economika Local Pipeline Report" in markdown


def test_markdown_includes_overall_status_and_artifact_counts(tmp_path: Path, capsys):
    _, markdown, _ = _run(tmp_path)
    capsys.readouterr()

    assert "**Overall ready:** yes" in markdown
    assert "| Render cards | 1 | 0 | 1 |" in markdown
    assert "| Videos | 1 | 0 | 1 |" in markdown
    assert "| Publish packets | 1 | 0 | 1 |" in markdown


def test_markdown_includes_ready_paths_and_manual_upload_checklist(tmp_path: Path, capsys):
    _, markdown, _ = _run(tmp_path)
    capsys.readouterr()

    assert "runtime/publish_queue/post-1/video.mp4" in markdown
    assert "runtime/publish_queue/post-1/caption.txt" in markdown
    assert "Review video:" in markdown
    assert "Upload manually to: tiktok" in markdown
    assert "Upload manually to: youtube_shorts" in markdown


def test_markdown_includes_source_handle_and_url(tmp_path: Path, capsys):
    _, markdown, _ = _run(tmp_path)
    capsys.readouterr()

    assert "Source: @juanrallo" in markdown
    assert "https://x.com/juanrallo/status/1" in markdown


def test_missing_render_manifest_warns_without_crashing(tmp_path: Path, capsys):
    render, video, publish = _manifests(tmp_path)
    render.unlink()
    output = tmp_path / "report.md"
    args = ["report.py", "--render-manifest", str(render), "--video-manifest", str(video), "--publish-queue-manifest", str(publish), "--output-md", str(output)]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["overall_ready"] is True
    assert any("Missing file" in warning for warning in summary["warnings"])
    assert "Render manifest: missing" in output.read_text(encoding="utf-8")


def test_missing_video_manifest_warns_without_crashing(tmp_path: Path, capsys):
    render, video, publish = _manifests(tmp_path)
    video.unlink()
    output = tmp_path / "report.md"
    args = ["report.py", "--render-manifest", str(render), "--video-manifest", str(video), "--publish-queue-manifest", str(publish), "--output-md", str(output)]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["overall_ready"] is True
    assert summary["warnings"]


def test_missing_publish_queue_manifest_is_error_and_not_ready(tmp_path: Path, capsys):
    render, video, publish = _manifests(tmp_path)
    publish.unlink()
    output = tmp_path / "report.md"
    args = ["report.py", "--render-manifest", str(render), "--video-manifest", str(video), "--publish-queue-manifest", str(publish), "--output-md", str(output)]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["overall_ready"] is False
    assert any("Missing file" in error for error in summary["errors"])


def test_invalid_render_json_warns_without_crashing(tmp_path: Path, capsys):
    render, video, publish = _manifests(tmp_path)
    render.write_text("{", encoding="utf-8")
    output = tmp_path / "report.md"
    args = ["report.py", "--render-manifest", str(render), "--video-manifest", str(video), "--publish-queue-manifest", str(publish), "--output-md", str(output)]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["overall_ready"] is True
    assert "Invalid JSON" in summary["warnings"][0]


def test_invalid_publish_json_is_error_and_not_ready(tmp_path: Path, capsys):
    render, video, publish = _manifests(tmp_path)
    publish.write_text("[]", encoding="utf-8")
    output = tmp_path / "report.md"
    args = ["report.py", "--render-manifest", str(render), "--video-manifest", str(video), "--publish-queue-manifest", str(publish), "--output-md", str(output)]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["overall_ready"] is False
    assert "top-level must be an object" in summary["errors"][0]


def test_pipeline_summary_is_included(tmp_path: Path, capsys):
    pipeline = tmp_path / "pipeline.json"
    _write_json(pipeline, {"success": True, "duration_seconds": 2.5, "dry_run": False, "overwrite": True, "stages": [{"name": "render_cards", "returncode": 0, "skipped": False}]})

    _, markdown, _ = _run(tmp_path, ["--pipeline-summary", str(pipeline)])
    summary = json.loads(capsys.readouterr().out)
    assert summary["pipeline_summary_found"] is True
    assert "Duration seconds: 2.5" in markdown
    assert "Stage count: 1" in markdown


def test_failed_pipeline_stage_is_listed_and_not_ready(tmp_path: Path, capsys):
    pipeline = tmp_path / "pipeline.json"
    _write_json(pipeline, {"success": False, "errors": [], "stages": [{"name": "export_videos", "returncode": 2, "skipped": False, "error": "Stage exited with code 2"}]})

    _, markdown, _ = _run(tmp_path, ["--pipeline-summary", str(pipeline)])
    summary = json.loads(capsys.readouterr().out)
    assert summary["overall_ready"] is False
    assert "Failed: export_videos: Stage exited with code 2" in markdown


def test_output_json_writes_valid_summary(tmp_path: Path, capsys):
    output_json = tmp_path / "report.json"
    _run(tmp_path, ["--output-json", str(output_json), "--pretty"])
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads(output_json.read_text(encoding="utf-8"))

    assert saved["overall_ready"] is True
    assert saved["ready_packets"][0]["post_id"] == "post-1"
    assert printed == saved


def test_atomic_writes_leave_no_tmp_files(tmp_path: Path):
    text_path = tmp_path / "report.md"
    json_path = tmp_path / "report.json"

    with patch("os.replace", wraps=os.replace) as mock_replace:
        write_text_atomically("report\n", text_path)
        write_json_atomically({"ready": True}, json_path)

    assert mock_replace.call_count == 2
    assert not text_path.with_name("report.md.tmp").exists()
    assert not json_path.with_name("report.json.tmp").exists()


def test_cli_summary_printed_with_requested_fields(tmp_path: Path, capsys):
    _run(tmp_path)
    summary = json.loads(capsys.readouterr().out)

    for field in (
        "output_md",
        "output_json",
        "render_manifest_found",
        "video_manifest_found",
        "publish_queue_manifest_found",
        "pipeline_summary_found",
        "warnings",
        "errors",
        "overall_ready",
        "publish_ready_count",
    ):
        assert field in summary
