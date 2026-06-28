from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

from scripts.generate_preview_reel import (
    NO_READY_PACKETS_ERROR,
    find_ready_packet,
    generate_preview_reel,
    main,
    resolve_card_path,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _args(**overrides) -> argparse.Namespace:
    defaults = {
        "post_id": None,
        "overwrite": False,
        "open": False,
        "no_open_video": False,
        "no_open_folder": False,
        "preview_dir": "runtime/preview_reels",
        "summary_json": None,
        "python_executable": "python",
        "continue_on_error": False,
        "duration_seconds": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _success_run(_command: list[str]) -> dict:
    return {"command": _command, "returncode": 0, "stdout": "{}", "stderr": "", "error": ""}


def _packet(post_id: str = "post-1", ready: bool = True) -> dict:
    return {
        "post_id": post_id,
        "video_path": f"runtime/publish_queue/{post_id}/video.mp4",
        "caption_path": f"runtime/publish_queue/{post_id}/caption.txt",
        "metadata_path": f"runtime/publish_queue/{post_id}/metadata.json",
        "packet_ready": ready,
        "source_account_handle": "economika",
        "source_url": "https://example.com/post",
        "platforms": ["tiktok", "instagram_reels", "youtube_shorts"],
    }


def _write_packet_files(root: Path, post_id: str = "post-1") -> None:
    packet_dir = root / "runtime" / "publish_queue" / post_id
    packet_dir.mkdir(parents=True, exist_ok=True)
    (packet_dir / "video.mp4").write_bytes(b"fake mp4")
    (packet_dir / "caption.txt").write_text("caption body", encoding="utf-8")
    _write_json(packet_dir / "metadata.json", _packet(post_id))


def _write_manifests(root: Path, packets: list[dict], card_post_id: str | None = "post-1") -> None:
    _write_json(root / "runtime" / "publish_queue" / "manifest.json", {"packets": packets})
    if card_post_id is not None:
        card_path = root / "runtime" / "renders" / card_post_id / "card.png"
        card_path.parent.mkdir(parents=True, exist_ok=True)
        card_path.write_bytes(b"fake png")
        _write_json(
            root / "runtime" / "renders" / "manifest.json",
            {"renders": [{"post_id": card_post_id, "card_path": card_path.as_posix()}]},
        )


def test_creates_preview_dir_and_copies_artifacts(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_packet_files(tmp_path)
    _write_manifests(tmp_path, [_packet()])

    with patch("scripts.generate_preview_reel.run_command", side_effect=_success_run):
        summary = generate_preview_reel(_args())

    preview = tmp_path / "runtime" / "preview_reels" / "post-1"
    assert summary["success"] is True
    assert preview.is_dir()
    assert (preview / "reel.mp4").read_bytes() == b"fake mp4"
    assert (preview / "caption.txt").read_text(encoding="utf-8") == "caption body"
    assert json.loads((preview / "metadata.json").read_text(encoding="utf-8"))["post_id"] == "post-1"
    assert (preview / "card.png").read_bytes() == b"fake png"


def test_works_without_card_path_and_emits_warning(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_packet_files(tmp_path)
    _write_manifests(tmp_path, [_packet()], card_post_id=None)

    with patch("scripts.generate_preview_reel.run_command", side_effect=_success_run):
        summary = generate_preview_reel(_args())

    assert summary["success"] is True
    assert "Card path not found" in "\n".join(summary["warnings"])
    assert not (tmp_path / "runtime" / "preview_reels" / "post-1" / "card.png").exists()


def test_selects_first_ready_packet_when_post_id_omitted():
    manifest = {"packets": [_packet("not-ready", ready=False), _packet("ready-1"), _packet("ready-2")]}
    assert find_ready_packet(manifest)["post_id"] == "ready-1"


def test_selects_requested_post_id_when_provided():
    manifest = {"packets": [_packet("ready-1"), _packet("ready-2")]}
    assert find_ready_packet(manifest, "ready-2")["post_id"] == "ready-2"


def test_fails_when_requested_post_id_not_found(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_packet_files(tmp_path, "post-1")
    _write_manifests(tmp_path, [_packet("post-1")])

    with patch("scripts.generate_preview_reel.run_command", side_effect=_success_run):
        summary = generate_preview_reel(_args(post_id="missing"))

    assert summary["success"] is False
    assert "Ready publish packet not found for post_id: missing" in summary["errors"]


def test_fails_when_no_ready_packet_exists(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_manifests(tmp_path, [_packet("post-1", ready=False)], card_post_id=None)

    with patch("scripts.generate_preview_reel.run_command", side_effect=_success_run):
        summary = generate_preview_reel(_args())

    assert summary["success"] is False
    assert NO_READY_PACKETS_ERROR in summary["errors"]


def test_overwrite_false_does_not_clobber_existing_preview_files(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_packet_files(tmp_path)
    _write_manifests(tmp_path, [_packet()])
    preview = tmp_path / "runtime" / "preview_reels" / "post-1"
    preview.mkdir(parents=True)
    (preview / "reel.mp4").write_bytes(b"existing")

    with patch("scripts.generate_preview_reel.run_command", side_effect=_success_run):
        summary = generate_preview_reel(_args())

    assert summary["success"] is True
    assert (preview / "reel.mp4").read_bytes() == b"existing"
    assert "Skipped existing file" in "\n".join(summary["warnings"])


def test_overwrite_true_replaces_existing_files(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_packet_files(tmp_path)
    _write_manifests(tmp_path, [_packet()])
    preview = tmp_path / "runtime" / "preview_reels" / "post-1"
    preview.mkdir(parents=True)
    (preview / "reel.mp4").write_bytes(b"existing")

    with patch("scripts.generate_preview_reel.run_command", side_effect=_success_run):
        summary = generate_preview_reel(_args(overwrite=True))

    assert summary["success"] is True
    assert (preview / "reel.mp4").read_bytes() == b"fake mp4"


def test_preview_report_contains_source_caption_and_checklist(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_packet_files(tmp_path)
    _write_manifests(tmp_path, [_packet()])

    with patch("scripts.generate_preview_reel.run_command", side_effect=_success_run):
        generate_preview_reel(_args())

    report = (tmp_path / "runtime" / "preview_reels" / "post-1" / "preview_report.md").read_text(encoding="utf-8")
    assert "economika" in report
    assert "https://example.com/post" in report
    assert "caption body" in report
    assert "Upload Checklist" in report
    assert "update_publish_status.py" in report


def test_open_opens_video_and_folder(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_packet_files(tmp_path)
    _write_manifests(tmp_path, [_packet()])

    with (
        patch("scripts.generate_preview_reel.run_command", side_effect=_success_run),
        patch("scripts.generate_preview_reel.open_path", return_value=(True, "")) as opener,
    ):
        summary = generate_preview_reel(_args(open=True))

    assert summary["opened_video"] is True
    assert summary["opened_folder"] is True
    assert opener.call_count == 2


def test_no_open_video_suppresses_video_open(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_packet_files(tmp_path)
    _write_manifests(tmp_path, [_packet()])

    with (
        patch("scripts.generate_preview_reel.run_command", side_effect=_success_run),
        patch("scripts.generate_preview_reel.open_path", return_value=(True, "")) as opener,
    ):
        summary = generate_preview_reel(_args(open=True, no_open_video=True))

    assert summary["opened_video"] is False
    assert summary["opened_folder"] is True
    assert opener.call_count == 1


def test_no_open_folder_suppresses_folder_open(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_packet_files(tmp_path)
    _write_manifests(tmp_path, [_packet()])

    with (
        patch("scripts.generate_preview_reel.run_command", side_effect=_success_run),
        patch("scripts.generate_preview_reel.open_path", return_value=(True, "")) as opener,
    ):
        summary = generate_preview_reel(_args(open=True, no_open_folder=True))

    assert summary["opened_video"] is True
    assert summary["opened_folder"] is False
    assert opener.call_count == 1


def test_open_failures_become_warnings(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_packet_files(tmp_path)
    _write_manifests(tmp_path, [_packet()])

    with (
        patch("scripts.generate_preview_reel.run_command", side_effect=_success_run),
        patch("scripts.generate_preview_reel.open_path", return_value=(False, "blocked")),
    ):
        summary = generate_preview_reel(_args(open=True))

    assert summary["success"] is True
    assert summary["opened_video"] is False
    assert summary["opened_folder"] is False
    assert "Failed to open video" in "\n".join(summary["warnings"])
    assert "Failed to open preview folder" in "\n".join(summary["warnings"])


def test_summary_json_includes_expected_paths(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _write_packet_files(tmp_path)
    _write_manifests(tmp_path, [_packet()])
    output = tmp_path / "summary.json"

    with (
        patch("scripts.generate_preview_reel.run_command", side_effect=_success_run),
        patch("sys.argv", ["generate_preview_reel.py", "--summary-json", str(output)]),
    ):
        assert main() == 0

    stdout_summary = json.loads(capsys.readouterr().out)
    file_summary = json.loads(output.read_text(encoding="utf-8"))
    assert stdout_summary == file_summary
    assert stdout_summary["preview_dir"] == "runtime/preview_reels/post-1"
    assert stdout_summary["reel_mp4"] == "runtime/preview_reels/post-1/reel.mp4"
    assert stdout_summary["card_png"] == "runtime/preview_reels/post-1/card.png"
    assert stdout_summary["caption_txt"] == "runtime/preview_reels/post-1/caption.txt"
    assert stdout_summary["metadata_json"] == "runtime/preview_reels/post-1/metadata.json"
    assert stdout_summary["preview_report_md"] == "runtime/preview_reels/post-1/preview_report.md"


def test_resolve_card_path_falls_back_to_convention(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    card = tmp_path / "runtime" / "renders" / "post-1" / "card.png"
    card.parent.mkdir(parents=True)
    card.write_bytes(b"png")

    assert resolve_card_path("post-1", {"renders": []}) == Path("runtime/renders/post-1/card.png")
