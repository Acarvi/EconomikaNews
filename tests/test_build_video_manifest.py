from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from scripts.build_video_manifest import (
    build_video_manifest,
    collect_manifest_errors,
    main,
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


def _metadata(path: Path, post_id: str = "post-1", **overrides) -> dict:
    payload = {
        "post_id": post_id,
        "source_card_path": f"runtime/renders/{post_id}/card.png",
        "source_manifest_entry": {"post_id": post_id},
        "video_path": path.as_posix(),
        "duration_seconds": 6,
        "fps": 30,
        "width": 1080,
        "height": 1920,
        "ready_for_upload": True,
        "video_errors": [],
    }
    payload.update(overrides)
    return payload


def test_missing_videos_dir_creates_empty_manifest_and_cli_exits_zero(tmp_path: Path, capsys):
    output_json = tmp_path / "videos" / "manifest.json"
    args = [
        "build_video_manifest.py",
        "--videos-dir",
        str(tmp_path / "missing"),
        "--output-json",
        str(output_json),
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    manifest = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["video_count"] == 0
    assert summary["invalid_video_count"] == 0
    assert manifest["videos"] == []


def test_empty_videos_dir_creates_empty_manifest(tmp_path: Path):
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()

    manifest = build_video_manifest(videos_dir)

    assert manifest["video_count"] == 0
    assert manifest["invalid_video_count"] == 0
    assert manifest["videos"] == []


def test_valid_video_and_matching_metadata_creates_manifest_entry(tmp_path: Path):
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    metadata = tmp_path / "videos" / "post-1" / "video_metadata.json"
    _write_video(video)
    _write_json(metadata, _metadata(video))

    manifest = build_video_manifest(tmp_path / "videos")

    assert manifest["video_count"] == 1
    entry = manifest["videos"][0]
    assert entry["post_id"] == "post-1"
    assert entry["video_path"] == video.as_posix()
    assert entry["metadata_path"] == metadata.as_posix()
    assert entry["file_size_bytes"] == video.stat().st_size
    assert entry["duration_seconds"] == 6
    assert entry["fps"] == 30
    assert entry["width"] == 1080
    assert entry["height"] == 1920
    assert entry["source_card_path"] == "runtime/renders/post-1/card.png"
    assert entry["source_account_handle"] == ""
    assert entry["source_url"] == ""
    assert entry["ready_for_upload"] is True
    assert entry["video_errors"] == []


def test_video_manifest_preserves_top_level_source_provenance(tmp_path: Path):
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    _write_video(video)
    _write_json(
        tmp_path / "videos" / "post-1" / "video_metadata.json",
        _metadata(
            video,
            source_account_handle="juanrallo",
            source_url="https://x.com/juanrallo/status/2057499359705813029",
        ),
    )

    entry = build_video_manifest(tmp_path / "videos")["videos"][0]

    assert entry["source_account_handle"] == "juanrallo"
    assert entry["source_url"] == "https://x.com/juanrallo/status/2057499359705813029"


def test_video_manifest_falls_back_to_nested_source_manifest_provenance(tmp_path: Path):
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    _write_video(video)
    _write_json(
        tmp_path / "videos" / "post-1" / "video_metadata.json",
        _metadata(
            video,
            source_manifest_entry={
                "post_id": "post-1",
                "account_handle": "juanrallo",
                "url": "https://x.com/juanrallo/status/2057499359705813029",
            },
        ),
    )

    entry = build_video_manifest(tmp_path / "videos")["videos"][0]

    assert entry["source_account_handle"] == "juanrallo"
    assert entry["source_url"] == "https://x.com/juanrallo/status/2057499359705813029"


def test_older_metadata_without_source_provenance_still_works(tmp_path: Path):
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    metadata = _metadata(video)
    metadata.pop("source_manifest_entry")
    _write_video(video)
    _write_json(tmp_path / "videos" / "post-1" / "video_metadata.json", metadata)

    entry = build_video_manifest(tmp_path / "videos")["videos"][0]

    assert entry["ready_for_upload"] is True
    assert entry["source_account_handle"] == ""
    assert entry["source_url"] == ""


def test_missing_video_counted_invalid(tmp_path: Path):
    (tmp_path / "videos" / "post-1").mkdir(parents=True)

    manifest = build_video_manifest(tmp_path / "videos", include_invalid=True)

    assert manifest["video_count"] == 0
    assert manifest["invalid_video_count"] == 1
    assert manifest["invalid_videos"][0]["error"] == "video.mp4 missing"


def test_zero_byte_video_counted_invalid(tmp_path: Path):
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    _write_video(video, content=b"")

    manifest = build_video_manifest(tmp_path / "videos", include_invalid=True)

    assert manifest["video_count"] == 0
    assert manifest["invalid_video_count"] == 1
    assert manifest["invalid_videos"][0]["error"] == "video.mp4 is empty"


def test_missing_metadata_keeps_video_not_ready_and_summary_errors_include_it(tmp_path: Path):
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    _write_video(video)

    manifest = build_video_manifest(tmp_path / "videos", include_invalid=True)
    entry = manifest["videos"][0]

    assert entry["ready_for_upload"] is False
    assert entry["video_errors"] == ["Video metadata missing"]
    assert collect_manifest_errors(manifest) == ["post-1: Video metadata missing"]


def test_invalid_metadata_json_keeps_video_not_ready(tmp_path: Path):
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    _write_video(video)
    _write_json(tmp_path / "videos" / "post-1" / "video_metadata.json", "{")

    entry = build_video_manifest(tmp_path / "videos")["videos"][0]

    assert entry["ready_for_upload"] is False
    assert "Invalid video metadata JSON" in entry["video_errors"][0]


def test_metadata_post_id_mismatch_keeps_video_not_ready(tmp_path: Path):
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    _write_video(video)
    _write_json(tmp_path / "videos" / "post-1" / "video_metadata.json", _metadata(video, post_id="other"))

    entry = build_video_manifest(tmp_path / "videos")["videos"][0]

    assert entry["ready_for_upload"] is False
    assert "Video metadata post_id mismatch" in entry["video_errors"][0]


def test_metadata_video_path_mismatch_keeps_video_not_ready(tmp_path: Path):
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    _write_video(video)
    _write_json(
        tmp_path / "videos" / "post-1" / "video_metadata.json",
        _metadata(video, video_path=(tmp_path / "other.mp4").as_posix()),
    )

    entry = build_video_manifest(tmp_path / "videos")["videos"][0]

    assert entry["ready_for_upload"] is False
    assert "Video metadata video_path mismatch" in entry["video_errors"][0]


def test_metadata_ready_false_keeps_video_not_ready(tmp_path: Path):
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    _write_video(video)
    _write_json(tmp_path / "videos" / "post-1" / "video_metadata.json", _metadata(video, ready_for_upload=False))

    entry = build_video_manifest(tmp_path / "videos")["videos"][0]

    assert entry["ready_for_upload"] is False
    assert entry["video_errors"] == ["Video metadata ready_for_upload is not true"]


def test_metadata_video_errors_keep_video_not_ready(tmp_path: Path):
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    _write_video(video)
    _write_json(tmp_path / "videos" / "post-1" / "video_metadata.json", _metadata(video, video_errors=["encode warning"]))

    entry = build_video_manifest(tmp_path / "videos")["videos"][0]

    assert entry["ready_for_upload"] is False
    assert entry["video_errors"] == ["encode warning"]


def test_dimensions_duration_and_fps_validation(tmp_path: Path):
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    _write_video(video)
    _write_json(
        tmp_path / "videos" / "post-1" / "video_metadata.json",
        _metadata(video, width=0, height=-1, duration_seconds=0, fps=0),
    )

    errors = build_video_manifest(tmp_path / "videos")["videos"][0]["video_errors"]

    assert "Video metadata duration_seconds must be greater than zero" in errors
    assert "Video metadata fps must be greater than zero" in errors
    assert "Video metadata width must be greater than zero" in errors
    assert "Video metadata height must be greater than zero" in errors


def test_direct_files_inside_videos_dir_ignored(tmp_path: Path):
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    (videos_dir / "notes.txt").write_text("ignore", encoding="utf-8")
    (videos_dir / "manifest.json").write_text("{}", encoding="utf-8")

    manifest = build_video_manifest(videos_dir, include_invalid=True)

    assert manifest["video_count"] == 0
    assert manifest["invalid_video_count"] == 0


def test_include_invalid_controls_invalid_video_details(tmp_path: Path):
    (tmp_path / "videos" / "post-1").mkdir(parents=True)

    hidden = build_video_manifest(tmp_path / "videos", include_invalid=False)
    detailed = build_video_manifest(tmp_path / "videos", include_invalid=True)

    assert hidden["invalid_video_count"] == 1
    assert hidden["invalid_videos"] == []
    assert detailed["invalid_videos"][0]["video_dir"].endswith("videos/post-1")


def test_summary_errors_include_invalid_and_not_ready_video_errors(tmp_path: Path):
    (tmp_path / "videos" / "missing-video").mkdir(parents=True)
    _write_video(tmp_path / "videos" / "missing-metadata" / "video.mp4")

    manifest = build_video_manifest(tmp_path / "videos", include_invalid=True)

    errors = collect_manifest_errors(manifest)
    assert any(error.endswith("missing-video: video.mp4 missing") for error in errors)
    assert "missing-metadata: Video metadata missing" in errors


def test_videos_sorted_by_created_at_desc_then_post_id_asc(tmp_path: Path):
    for post_id in ("post-b", "post-a", "post-old"):
        video = tmp_path / "videos" / post_id / "video.mp4"
        _write_video(video)
        _write_json(tmp_path / "videos" / post_id / "video_metadata.json", _metadata(video, post_id=post_id))

    old_time = 1_700_000_000
    new_time = 1_800_000_000
    os.utime(tmp_path / "videos" / "post-old" / "video.mp4", (old_time, old_time))
    os.utime(tmp_path / "videos" / "post-a" / "video.mp4", (new_time, new_time))
    os.utime(tmp_path / "videos" / "post-b" / "video.mp4", (new_time, new_time))

    manifest = build_video_manifest(tmp_path / "videos")

    assert [video["post_id"] for video in manifest["videos"]] == ["post-a", "post-b", "post-old"]


def test_atomic_write_uses_tmp_replace(tmp_path: Path):
    output_json = tmp_path / "videos" / "manifest.json"

    with patch("os.replace", wraps=os.replace) as mock_replace:
        write_manifest_atomically({"videos": []}, output_json)

    assert output_json.exists()
    args = mock_replace.call_args[0]
    assert args[0].endswith("manifest.json.tmp")
    assert args[1].endswith("manifest.json")


def test_cli_summary_printed(tmp_path: Path, capsys):
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    _write_video(video)
    _write_json(tmp_path / "videos" / "post-1" / "video_metadata.json", _metadata(video))
    args = [
        "build_video_manifest.py",
        "--videos-dir",
        str(tmp_path / "videos"),
        "--output-json",
        str(tmp_path / "videos" / "manifest.json"),
        "--pretty",
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["video_count"] == 1
    assert summary["invalid_video_count"] == 0
    assert summary["errors"] == []


def test_cli_summary_includes_invalid_errors_when_excluded_from_manifest(tmp_path: Path, capsys):
    (tmp_path / "videos" / "post-1").mkdir(parents=True)
    output_json = tmp_path / "videos" / "manifest.json"
    args = [
        "build_video_manifest.py",
        "--videos-dir",
        str(tmp_path / "videos"),
        "--output-json",
        str(output_json),
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    manifest = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["errors"][0].endswith("post-1: video.mp4 missing")
    assert manifest["invalid_video_count"] == 1
    assert manifest["invalid_videos"] == []


def test_cli_include_invalid_true_writes_invalid_details(tmp_path: Path, capsys):
    (tmp_path / "videos" / "post-1").mkdir(parents=True)
    output_json = tmp_path / "videos" / "manifest.json"
    args = [
        "build_video_manifest.py",
        "--videos-dir",
        str(tmp_path / "videos"),
        "--output-json",
        str(output_json),
        "--include-invalid",
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    manifest = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["errors"][0].endswith("post-1: video.mp4 missing")
    assert manifest["invalid_videos"][0]["error"] == "video.mp4 missing"


def test_cli_write_failure_returns_exit_code_1(tmp_path: Path, capsys):
    args = [
        "build_video_manifest.py",
        "--videos-dir",
        str(tmp_path / "missing"),
        "--output-json",
        str(tmp_path / "videos" / "manifest.json"),
    ]

    with (
        patch("sys.argv", args),
        patch("scripts.build_video_manifest.write_manifest_atomically", side_effect=OSError("disk full")),
    ):
        assert main() == 1

    assert "failed to write manifest" in capsys.readouterr().err
