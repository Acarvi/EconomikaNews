from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from scripts.build_publish_queue_manifest import (
    build_publish_queue_manifest,
    collect_manifest_errors,
    main,
    normalize_caption_preview,
    write_manifest_atomically,
)


def _write_json(path: Path, payload: dict | list | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")


def _write_video(path: Path, content: bytes = b"fake mp4") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _write_caption(path: Path, text: str = "ECONOMIKA - senal detectada.\n\nFuente: @juanrallo\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _metadata(packet_dir: Path, post_id: str = "post-1", **overrides) -> dict:
    payload = {
        "post_id": post_id,
        "created_at": "2026-06-19T10:00:00Z",
        "packet_dir": packet_dir.as_posix(),
        "video_path": (packet_dir / "video.mp4").as_posix(),
        "caption_path": (packet_dir / "caption.txt").as_posix(),
        "source_video_path": f"runtime/videos/{post_id}/video.mp4",
        "source_video_manifest_entry": {"post_id": post_id},
        "source_account_handle": "juanrallo",
        "source_url": "https://x.com/juanrallo/status/2057499359705813029",
        "platforms": ["tiktok", "instagram_reels", "youtube_shorts"],
        "packet_ready": True,
        "packet_errors": [],
        "manual_upload": True,
    }
    payload.update(overrides)
    return payload


def _write_packet(packet_dir: Path, **metadata_overrides) -> None:
    _write_video(packet_dir / "video.mp4")
    _write_caption(packet_dir / "caption.txt")
    post_id = metadata_overrides.pop("post_id", packet_dir.name)
    _write_json(packet_dir / "metadata.json", _metadata(packet_dir, post_id=post_id, **metadata_overrides))


def test_missing_queue_dir_creates_empty_manifest_and_cli_exits_zero(tmp_path: Path, capsys):
    output_json = tmp_path / "queue" / "manifest.json"
    args = [
        "build_publish_queue_manifest.py",
        "--queue-dir",
        str(tmp_path / "missing"),
        "--output-json",
        str(output_json),
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    manifest = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["packet_count"] == 0
    assert summary["invalid_packet_count"] == 0
    assert manifest["packets"] == []


def test_empty_queue_dir_creates_empty_manifest(tmp_path: Path):
    queue_dir = tmp_path / "queue"
    queue_dir.mkdir()

    manifest = build_publish_queue_manifest(queue_dir)

    assert manifest["packet_count"] == 0
    assert manifest["invalid_packet_count"] == 0
    assert manifest["packets"] == []


def test_valid_packet_creates_manifest_entry(tmp_path: Path):
    packet_dir = tmp_path / "queue" / "post-1"
    caption = "ECONOMIKA - senal detectada.\n\nFuente: @juanrallo\nURL: https://x.com/juanrallo/status/1\n"
    _write_video(packet_dir / "video.mp4")
    _write_caption(packet_dir / "caption.txt", caption)
    _write_json(packet_dir / "metadata.json", _metadata(packet_dir))

    entry = build_publish_queue_manifest(tmp_path / "queue")["packets"][0]

    assert entry["post_id"] == "post-1"
    assert entry["packet_dir"] == packet_dir.as_posix()
    assert entry["video_path"] == (packet_dir / "video.mp4").as_posix()
    assert entry["caption_path"] == (packet_dir / "caption.txt").as_posix()
    assert entry["metadata_path"] == (packet_dir / "metadata.json").as_posix()
    assert entry["file_size_bytes"] == (packet_dir / "video.mp4").stat().st_size
    assert entry["source_account_handle"] == "juanrallo"
    assert entry["source_url"] == "https://x.com/juanrallo/status/2057499359705813029"
    assert entry["platforms"] == ["tiktok", "instagram_reels", "youtube_shorts"]
    assert entry["caption_length"] == len(caption)
    assert entry["caption_preview"] == normalize_caption_preview(caption)
    assert entry["manual_upload"] is True
    assert entry["packet_ready"] is True
    assert entry["packet_errors"] == []


def test_missing_video_counted_invalid(tmp_path: Path):
    (tmp_path / "queue" / "post-1").mkdir(parents=True)

    manifest = build_publish_queue_manifest(tmp_path / "queue", include_invalid=True)

    assert manifest["packet_count"] == 0
    assert manifest["invalid_packet_count"] == 1
    assert manifest["invalid_packets"][0]["error"] == "video.mp4 missing"


def test_zero_byte_video_counted_invalid(tmp_path: Path):
    _write_video(tmp_path / "queue" / "post-1" / "video.mp4", content=b"")

    manifest = build_publish_queue_manifest(tmp_path / "queue", include_invalid=True)

    assert manifest["packet_count"] == 0
    assert manifest["invalid_packet_count"] == 1
    assert manifest["invalid_packets"][0]["error"] == "video.mp4 is empty"


def test_missing_caption_keeps_packet_not_ready_and_summary_errors_include_it(tmp_path: Path):
    packet_dir = tmp_path / "queue" / "post-1"
    _write_video(packet_dir / "video.mp4")
    _write_json(packet_dir / "metadata.json", _metadata(packet_dir))

    manifest = build_publish_queue_manifest(tmp_path / "queue", include_invalid=True)
    entry = manifest["packets"][0]

    assert entry["packet_ready"] is False
    assert "Caption missing" in entry["packet_errors"]
    assert "post-1: Caption missing" in collect_manifest_errors(manifest)


def test_missing_metadata_keeps_packet_not_ready_and_summary_errors_include_it(tmp_path: Path):
    packet_dir = tmp_path / "queue" / "post-1"
    _write_video(packet_dir / "video.mp4")
    _write_caption(packet_dir / "caption.txt")

    manifest = build_publish_queue_manifest(tmp_path / "queue", include_invalid=True)
    entry = manifest["packets"][0]

    assert entry["packet_ready"] is False
    assert "Metadata missing" in entry["packet_errors"]
    assert "post-1: Metadata missing" in collect_manifest_errors(manifest)


def test_invalid_metadata_json_keeps_packet_not_ready(tmp_path: Path):
    packet_dir = tmp_path / "queue" / "post-1"
    _write_video(packet_dir / "video.mp4")
    _write_caption(packet_dir / "caption.txt")
    _write_json(packet_dir / "metadata.json", "{")

    entry = build_publish_queue_manifest(tmp_path / "queue")["packets"][0]

    assert entry["packet_ready"] is False
    assert "Invalid packet metadata JSON" in entry["packet_errors"][0]


def test_metadata_post_id_mismatch_keeps_packet_not_ready(tmp_path: Path):
    packet_dir = tmp_path / "queue" / "post-1"
    _write_packet(packet_dir, post_id="other")

    entry = build_publish_queue_manifest(tmp_path / "queue")["packets"][0]

    assert entry["packet_ready"] is False
    assert "Packet metadata post_id mismatch" in entry["packet_errors"][0]


def test_metadata_video_path_mismatch_keeps_packet_not_ready(tmp_path: Path):
    packet_dir = tmp_path / "queue" / "post-1"
    _write_packet(packet_dir, video_path=(tmp_path / "other.mp4").as_posix())

    entry = build_publish_queue_manifest(tmp_path / "queue")["packets"][0]

    assert entry["packet_ready"] is False
    assert "Packet metadata video_path mismatch" in entry["packet_errors"][0]


def test_metadata_caption_path_mismatch_keeps_packet_not_ready(tmp_path: Path):
    packet_dir = tmp_path / "queue" / "post-1"
    _write_packet(packet_dir, caption_path=(tmp_path / "other.txt").as_posix())

    entry = build_publish_queue_manifest(tmp_path / "queue")["packets"][0]

    assert entry["packet_ready"] is False
    assert "Packet metadata caption_path mismatch" in entry["packet_errors"][0]


def test_metadata_packet_ready_false_keeps_packet_not_ready(tmp_path: Path):
    packet_dir = tmp_path / "queue" / "post-1"
    _write_packet(packet_dir, packet_ready=False)

    entry = build_publish_queue_manifest(tmp_path / "queue")["packets"][0]

    assert entry["packet_ready"] is False
    assert "Packet metadata packet_ready is not true" in entry["packet_errors"]


def test_metadata_packet_errors_keep_packet_not_ready(tmp_path: Path):
    packet_dir = tmp_path / "queue" / "post-1"
    _write_packet(packet_dir, packet_errors=["manual review needed"])

    entry = build_publish_queue_manifest(tmp_path / "queue")["packets"][0]

    assert entry["packet_ready"] is False
    assert "manual review needed" in entry["packet_errors"]


def test_manual_upload_false_keeps_packet_not_ready(tmp_path: Path):
    packet_dir = tmp_path / "queue" / "post-1"
    _write_packet(packet_dir, manual_upload=False)

    entry = build_publish_queue_manifest(tmp_path / "queue")["packets"][0]

    assert entry["packet_ready"] is False
    assert "Packet metadata manual_upload is not true" in entry["packet_errors"]


def test_platforms_missing_or_empty_keeps_packet_not_ready(tmp_path: Path):
    packet_dir = tmp_path / "queue" / "post-1"
    _write_packet(packet_dir, platforms=[])

    entry = build_publish_queue_manifest(tmp_path / "queue")["packets"][0]

    assert entry["packet_ready"] is False
    assert "Packet metadata platforms must be a non-empty list" in entry["packet_errors"]


def test_direct_files_inside_queue_dir_ignored(tmp_path: Path):
    queue_dir = tmp_path / "queue"
    queue_dir.mkdir()
    (queue_dir / "notes.txt").write_text("ignore", encoding="utf-8")
    (queue_dir / "manifest.json").write_text("{}", encoding="utf-8")

    manifest = build_publish_queue_manifest(queue_dir, include_invalid=True)

    assert manifest["packet_count"] == 0
    assert manifest["invalid_packet_count"] == 0


def test_include_invalid_controls_invalid_packet_details(tmp_path: Path):
    (tmp_path / "queue" / "post-1").mkdir(parents=True)

    hidden = build_publish_queue_manifest(tmp_path / "queue", include_invalid=False)
    detailed = build_publish_queue_manifest(tmp_path / "queue", include_invalid=True)

    assert hidden["invalid_packet_count"] == 1
    assert hidden["invalid_packets"] == []
    assert detailed["invalid_packets"][0]["packet_dir"].endswith("queue/post-1")


def test_summary_errors_include_invalid_and_not_ready_packet_errors(tmp_path: Path):
    (tmp_path / "queue" / "missing-video").mkdir(parents=True)
    packet_dir = tmp_path / "queue" / "missing-caption"
    _write_video(packet_dir / "video.mp4")
    _write_json(packet_dir / "metadata.json", _metadata(packet_dir, post_id="missing-caption"))

    manifest = build_publish_queue_manifest(tmp_path / "queue", include_invalid=True)

    errors = collect_manifest_errors(manifest)
    assert any(error.endswith("missing-video: video.mp4 missing") for error in errors)
    assert "missing-caption: Caption missing" in errors


def test_packets_sorted_by_created_at_desc_then_post_id_asc(tmp_path: Path):
    for post_id in ("post-b", "post-a", "post-old"):
        packet_dir = tmp_path / "queue" / post_id
        _write_packet(packet_dir, created_at="2026-06-19T10:00:00Z")
    _write_json(
        tmp_path / "queue" / "post-old" / "metadata.json",
        _metadata(tmp_path / "queue" / "post-old", post_id="post-old", created_at="2026-06-18T10:00:00Z"),
    )

    manifest = build_publish_queue_manifest(tmp_path / "queue")

    assert [packet["post_id"] for packet in manifest["packets"]] == ["post-a", "post-b", "post-old"]


def test_atomic_write_uses_tmp_replace(tmp_path: Path):
    output_json = tmp_path / "queue" / "manifest.json"

    with patch("os.replace", wraps=os.replace) as mock_replace:
        write_manifest_atomically({"packets": []}, output_json)

    assert output_json.exists()
    args = mock_replace.call_args[0]
    assert args[0].endswith("manifest.json.tmp")
    assert args[1].endswith("manifest.json")


def test_cli_summary_printed(tmp_path: Path, capsys):
    packet_dir = tmp_path / "queue" / "post-1"
    _write_packet(packet_dir)
    args = [
        "build_publish_queue_manifest.py",
        "--queue-dir",
        str(tmp_path / "queue"),
        "--output-json",
        str(tmp_path / "queue" / "manifest.json"),
        "--pretty",
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["packet_count"] == 1
    assert summary["invalid_packet_count"] == 0
    assert summary["errors"] == []


def test_cli_summary_includes_invalid_errors_when_excluded_from_manifest(tmp_path: Path, capsys):
    (tmp_path / "queue" / "post-1").mkdir(parents=True)
    output_json = tmp_path / "queue" / "manifest.json"
    args = [
        "build_publish_queue_manifest.py",
        "--queue-dir",
        str(tmp_path / "queue"),
        "--output-json",
        str(output_json),
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    manifest = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["errors"][0].endswith("post-1: video.mp4 missing")
    assert manifest["invalid_packet_count"] == 1
    assert manifest["invalid_packets"] == []


def test_cli_include_invalid_true_writes_invalid_details(tmp_path: Path, capsys):
    (tmp_path / "queue" / "post-1").mkdir(parents=True)
    output_json = tmp_path / "queue" / "manifest.json"
    args = [
        "build_publish_queue_manifest.py",
        "--queue-dir",
        str(tmp_path / "queue"),
        "--output-json",
        str(output_json),
        "--include-invalid",
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    manifest = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["errors"][0].endswith("post-1: video.mp4 missing")
    assert manifest["invalid_packets"][0]["error"] == "video.mp4 missing"


def test_cli_write_failure_returns_exit_code_1(tmp_path: Path, capsys):
    args = [
        "build_publish_queue_manifest.py",
        "--queue-dir",
        str(tmp_path / "missing"),
        "--output-json",
        str(tmp_path / "queue" / "manifest.json"),
    ]

    with (
        patch("sys.argv", args),
        patch("scripts.build_publish_queue_manifest.write_manifest_atomically", side_effect=OSError("disk full")),
    ):
        assert main() == 1

    assert "failed to write manifest" in capsys.readouterr().err
