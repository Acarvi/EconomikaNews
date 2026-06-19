from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from scripts.export_card_videos import (
    export_all_videos,
    export_static_card_video,
    export_video_for_render,
    iter_publishable_renders,
    main,
    write_video_metadata_atomically,
)


def _write_json(path: Path, payload: dict | list | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")


def _write_png(path: Path, size: tuple[int, int] = (64, 96)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color="#111827").save(path, format="PNG")


def _render(card_path: Path, post_id: str = "post-1", ready: bool = True, **overrides) -> dict:
    render = {
        "post_id": post_id,
        "card_path": card_path.as_posix(),
        "ready_for_publish": ready,
        "render_errors": [] if ready else ["not ready"],
    }
    render.update(overrides)
    return render


def _manifest(*renders: dict) -> dict:
    return {"generated_at": "2026-06-19T10:00:00Z", "renders": list(renders)}


def _fake_writer(card_path: Path, output_path: Path, duration_seconds: float, fps: int) -> None:
    assert card_path.exists()
    assert duration_seconds > 0
    assert fps > 0
    output_path.write_bytes(b"fake mp4")


def test_missing_manifest_returns_exit_code_1(tmp_path: Path, capsys):
    args = ["export_card_videos.py", "--manifest-file", str(tmp_path / "missing.json")]

    with patch("sys.argv", args):
        assert main() == 1

    assert "Manifest file missing" in capsys.readouterr().err


def test_invalid_json_returns_exit_code_1(tmp_path: Path, capsys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{", encoding="utf-8")

    with patch("sys.argv", ["export_card_videos.py", "--manifest-file", str(manifest)]):
        assert main() == 1

    assert "Invalid manifest JSON" in capsys.readouterr().err


def test_invalid_manifest_shapes_return_exit_code_1(tmp_path: Path, capsys):
    for payload, message in [([], "top-level must be a JSON object"), ({}, "'renders' must be a list")]:
        manifest = tmp_path / f"{len(str(payload))}.json"
        _write_json(manifest, payload)
        with patch("sys.argv", ["export_card_videos.py", "--manifest-file", str(manifest)]):
            assert main() == 1
        assert message in capsys.readouterr().err


def test_empty_renders_summary_zero(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    _write_json(manifest, _manifest())

    summary = export_all_videos(manifest, tmp_path / "videos", writer=_fake_writer)

    assert summary["renders_seen"] == 0
    assert summary["videos_written"] == 0
    assert summary["videos_skipped"] == 0
    assert summary["errors"] == []


def test_ready_render_exports_video_and_metadata_with_fake_writer(tmp_path: Path):
    card = tmp_path / "renders" / "post-1" / "card.png"
    _write_png(card, size=(64, 96))
    manifest = tmp_path / "manifest.json"
    _write_json(manifest, _manifest(_render(card)))

    summary = export_all_videos(manifest, tmp_path / "videos", duration_seconds=2, fps=12, writer=_fake_writer)

    video = tmp_path / "videos" / "post-1" / "video.mp4"
    metadata_path = tmp_path / "videos" / "post-1" / "video_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert summary["videos_written"] == 1
    assert video.read_bytes() == b"fake mp4"
    assert metadata["post_id"] == "post-1"
    assert metadata["source_card_path"] == card.as_posix()
    assert metadata["source_account_handle"] == ""
    assert metadata["source_url"] == ""
    assert metadata["video_path"] == video.as_posix()
    assert metadata["duration_seconds"] == 2
    assert metadata["fps"] == 12
    assert metadata["width"] == 64
    assert metadata["height"] == 96
    assert metadata["ready_for_upload"] is True
    assert metadata["video_errors"] == []


def test_video_metadata_includes_source_provenance_from_render_manifest(tmp_path: Path):
    card = tmp_path / "renders" / "post-1" / "card.png"
    _write_png(card)
    render = _render(
        card,
        account_handle="juanrallo",
        url="https://x.com/juanrallo/status/2057499359705813029",
    )

    result = export_video_for_render(render, tmp_path / "videos", writer=_fake_writer)

    metadata = json.loads((tmp_path / "videos" / "post-1" / "video_metadata.json").read_text(encoding="utf-8"))
    assert result["written"] is True
    assert metadata["source_account_handle"] == "juanrallo"
    assert metadata["source_url"] == "https://x.com/juanrallo/status/2057499359705813029"
    assert metadata["source_manifest_entry"] == render


def test_not_ready_render_skipped_by_default(tmp_path: Path):
    card = tmp_path / "renders" / "post-1" / "card.png"
    _write_png(card)
    manifest = tmp_path / "manifest.json"
    _write_json(manifest, _manifest(_render(card, ready=False)))

    summary = export_all_videos(manifest, tmp_path / "videos", writer=_fake_writer)

    assert summary["renders_seen"] == 0
    assert not (tmp_path / "videos").exists()


def test_include_not_ready_exports_but_marks_not_ready(tmp_path: Path):
    card = tmp_path / "renders" / "post-1" / "card.png"
    _write_png(card)
    manifest = tmp_path / "manifest.json"
    _write_json(manifest, _manifest(_render(card, ready=False)))

    summary = export_all_videos(manifest, tmp_path / "videos", include_not_ready=True, writer=_fake_writer)

    metadata = json.loads((tmp_path / "videos" / "post-1" / "video_metadata.json").read_text(encoding="utf-8"))
    assert summary["renders_seen"] == 1
    assert summary["items"][0]["video_ready"] is False
    assert metadata["ready_for_upload"] is False


def test_missing_card_path_skipped_with_error(tmp_path: Path):
    result = export_video_for_render({"post_id": "post-1", "ready_for_publish": True}, tmp_path / "videos")

    assert result["skipped"] is True
    assert "missing card_path" in result["error"]


def test_missing_card_file_skipped_with_error(tmp_path: Path):
    result = export_video_for_render(
        _render(tmp_path / "renders" / "post-1" / "card.png"),
        tmp_path / "videos",
        writer=_fake_writer,
    )

    assert result["skipped"] is True
    assert "card_path missing or not a file" in result["error"]


def test_missing_post_id_skipped_with_error(tmp_path: Path):
    card = tmp_path / "renders" / "post-1" / "card.png"
    _write_png(card)

    result = export_video_for_render({"card_path": card.as_posix(), "ready_for_publish": True}, tmp_path / "videos")

    assert result["skipped"] is True
    assert "missing post_id" in result["error"]


def test_existing_video_skipped_when_overwrite_false(tmp_path: Path):
    card = tmp_path / "renders" / "post-1" / "card.png"
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    _write_png(card)
    video.parent.mkdir(parents=True)
    video.write_bytes(b"old")

    result = export_video_for_render(_render(card), tmp_path / "videos", writer=_fake_writer)

    assert result["skipped"] is True
    assert result["skipped_existing"] is True
    assert video.read_bytes() == b"old"


def test_overwrite_true_replaces_existing_video(tmp_path: Path):
    card = tmp_path / "renders" / "post-1" / "card.png"
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    _write_png(card)
    video.parent.mkdir(parents=True)
    video.write_bytes(b"old")

    result = export_video_for_render(_render(card), tmp_path / "videos", overwrite=True, writer=_fake_writer)

    assert result["written"] is True
    assert video.read_bytes() == b"fake mp4"


def test_dry_run_creates_no_directories_or_files(tmp_path: Path):
    card = tmp_path / "renders" / "post-1" / "card.png"
    _write_png(card)

    result = export_video_for_render(_render(card), tmp_path / "videos", dry_run=True, writer=_fake_writer)

    assert result["written"] is False
    assert result["skipped"] is False
    assert result["video_ready"] is True
    assert not (tmp_path / "videos").exists()


def test_metadata_written_atomically(tmp_path: Path):
    metadata_path = tmp_path / "videos" / "post-1" / "video_metadata.json"

    with patch("os.replace", wraps=os.replace) as mock_replace:
        write_video_metadata_atomically({"post_id": "post-1"}, metadata_path)

    assert metadata_path.exists()
    args = mock_replace.call_args[0]
    assert args[0].endswith("video_metadata.json.tmp")
    assert args[1].endswith("video_metadata.json")


def test_video_written_atomically(tmp_path: Path):
    card = tmp_path / "renders" / "post-1" / "card.png"
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    _write_png(card)

    with patch("os.replace", wraps=os.replace) as mock_replace:
        export_static_card_video(card, video, duration_seconds=1, fps=1, writer=_fake_writer)

    assert video.exists()
    args = mock_replace.call_args[0]
    assert args[0].endswith("video.tmp.mp4")
    assert args[1].endswith("video.mp4")


def test_video_tmp_file_cleaned_on_writer_error(tmp_path: Path):
    card = tmp_path / "renders" / "post-1" / "card.png"
    video = tmp_path / "videos" / "post-1" / "video.mp4"
    _write_png(card)

    def failing_writer(_card_path: Path, output_path: Path, _duration_seconds: float, _fps: int) -> None:
        output_path.write_bytes(b"partial")
        raise OSError("encoder failed")

    result = export_video_for_render(_render(card), tmp_path / "videos", writer=failing_writer)

    assert result["skipped"] is True
    assert "encoder failed" in result["error"]
    assert not video.exists()
    assert not (tmp_path / "videos" / "post-1" / "video.tmp.mp4").exists()
    assert not (tmp_path / "videos" / "post-1" / "video_metadata.json").exists()


def test_cli_summary_printed(tmp_path: Path, capsys):
    card = tmp_path / "renders" / "post-1" / "card.png"
    _write_png(card)
    manifest = tmp_path / "manifest.json"
    _write_json(manifest, _manifest(_render(card)))
    args = [
        "export_card_videos.py",
        "--manifest-file",
        str(manifest),
        "--output-dir",
        str(tmp_path / "videos"),
        "--dry-run",
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["renders_seen"] == 1
    assert summary["dry_run"] is True


def test_iter_publishable_renders_ignores_non_object_entries(tmp_path: Path):
    card = tmp_path / "renders" / "post-1" / "card.png"
    manifest = _manifest(_render(card), ["bad"], {"post_id": "post-2", "ready_for_publish": False})

    assert [render["post_id"] for render in iter_publishable_renders(manifest)] == ["post-1"]
    assert [render["post_id"] for render in iter_publishable_renders(manifest, include_not_ready=True)] == [
        "post-1",
        "post-2",
    ]
