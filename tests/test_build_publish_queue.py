from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from scripts.build_publish_queue import (
    ALLOWED_PLATFORMS,
    build_caption,
    build_publish_queue,
    main,
    normalize_platforms,
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


def _video_entry(video_path: Path, post_id: str = "post-1", ready: bool = True, **overrides) -> dict:
    entry = {
        "post_id": post_id,
        "video_path": video_path.as_posix(),
        "ready_for_upload": ready,
        "source_manifest_entry": {
            "post_id": post_id,
            "account_handle": "economika",
            "url": "https://x.com/economika/status/1",
        },
        "video_errors": [] if ready else ["not ready"],
    }
    entry.update(overrides)
    return entry


def _manifest(*videos: dict) -> dict:
    return {"generated_at": "2026-06-19T10:00:00Z", "videos": list(videos)}


def test_missing_manifest_exits_1(tmp_path: Path, capsys):
    args = ["build_publish_queue.py", "--video-manifest", str(tmp_path / "missing.json")]

    with patch("sys.argv", args):
        assert main() == 1

    assert "Video manifest missing" in capsys.readouterr().err


def test_invalid_json_exits_1(tmp_path: Path, capsys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{", encoding="utf-8")

    with patch("sys.argv", ["build_publish_queue.py", "--video-manifest", str(manifest)]):
        assert main() == 1

    assert "Invalid video manifest JSON" in capsys.readouterr().err


def test_invalid_manifest_shape_exits_1(tmp_path: Path, capsys):
    for payload, message in [([], "top-level must be a JSON object"), ({}, "'videos' must be a list")]:
        manifest = tmp_path / f"{len(str(payload))}.json"
        _write_json(manifest, payload)
        with patch("sys.argv", ["build_publish_queue.py", "--video-manifest", str(manifest)]):
            assert main() == 1
        assert message in capsys.readouterr().err


def test_empty_videos_summary_zero(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    _write_json(manifest, _manifest())

    summary = build_publish_queue(manifest, tmp_path / "queue", list(ALLOWED_PLATFORMS))

    assert summary["videos_seen"] == 0
    assert summary["packets_written"] == 0
    assert summary["packets_skipped"] == 0
    assert summary["errors"] == []


def test_ready_video_creates_packet_files(tmp_path: Path):
    source_video = tmp_path / "videos" / "post-1" / "video.mp4"
    manifest = tmp_path / "manifest.json"
    _write_video(source_video)
    _write_json(manifest, _manifest(_video_entry(source_video)))

    summary = build_publish_queue(manifest, tmp_path / "queue", list(ALLOWED_PLATFORMS))

    packet_dir = tmp_path / "queue" / "post-1"
    metadata = json.loads((packet_dir / "metadata.json").read_text(encoding="utf-8"))
    assert summary["packets_written"] == 1
    assert (packet_dir / "video.mp4").read_bytes() == b"fake mp4"
    assert (packet_dir / "caption.txt").exists()
    assert metadata["post_id"] == "post-1"
    assert metadata["packet_dir"] == packet_dir.as_posix()
    assert metadata["video_path"] == (packet_dir / "video.mp4").as_posix()
    assert metadata["caption_path"] == (packet_dir / "caption.txt").as_posix()
    assert metadata["source_video_path"] == source_video.as_posix()
    assert metadata["source_account_handle"] == "economika"
    assert metadata["source_url"] == "https://x.com/economika/status/1"
    assert metadata["platforms"] == list(ALLOWED_PLATFORMS)
    assert metadata["packet_ready"] is True
    assert metadata["packet_errors"] == []
    assert metadata["manual_upload"] is True


def test_caption_under_500_chars(tmp_path: Path):
    source_video = tmp_path / "videos" / "post-1" / "video.mp4"
    entry = _video_entry(
        source_video,
        source_manifest_entry={
            "account_handle": "economika",
            "url": "https://example.com/" + ("x" * 800),
        },
    )

    assert len(build_caption(entry)) <= 500


def test_missing_account_handle_uses_unknown_source(tmp_path: Path):
    source_video = tmp_path / "videos" / "post-1" / "video.mp4"
    caption = build_caption(_video_entry(source_video, source_manifest_entry={}))

    assert "Fuente: desconocida" in caption


def test_source_handle_appears_in_caption(tmp_path: Path):
    source_video = tmp_path / "videos" / "post-1" / "video.mp4"
    caption = build_caption(_video_entry(source_video, source_account_handle="juanrallo", source_manifest_entry={}))

    assert "Fuente: @juanrallo" in caption


def test_caption_includes_url_line_when_source_url_exists(tmp_path: Path):
    source_video = tmp_path / "videos" / "post-1" / "video.mp4"
    caption = build_caption(
        _video_entry(
            source_video,
            source_account_handle="juanrallo",
            source_url="https://x.com/juanrallo/status/2057499359705813029",
            source_manifest_entry={},
        )
    )

    assert "Fuente: @juanrallo" in caption
    assert "URL: https://x.com/juanrallo/status/2057499359705813029" in caption


def test_caption_omits_url_line_when_missing(tmp_path: Path):
    source_video = tmp_path / "videos" / "post-1" / "video.mp4"
    caption = build_caption(_video_entry(source_video, source_manifest_entry={}))

    assert "URL:" not in caption


def test_packet_metadata_includes_source_provenance(tmp_path: Path):
    source_video = tmp_path / "videos" / "post-1" / "video.mp4"
    manifest = tmp_path / "manifest.json"
    _write_video(source_video)
    _write_json(
        manifest,
        _manifest(
            _video_entry(
                source_video,
                source_account_handle="juanrallo",
                source_url="https://x.com/juanrallo/status/2057499359705813029",
                source_manifest_entry={},
            )
        ),
    )

    build_publish_queue(manifest, tmp_path / "queue", list(ALLOWED_PLATFORMS))

    metadata = json.loads((tmp_path / "queue" / "post-1" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["source_account_handle"] == "juanrallo"
    assert metadata["source_url"] == "https://x.com/juanrallo/status/2057499359705813029"


def test_not_ready_video_skipped_by_default(tmp_path: Path):
    source_video = tmp_path / "videos" / "post-1" / "video.mp4"
    manifest = tmp_path / "manifest.json"
    _write_video(source_video)
    _write_json(manifest, _manifest(_video_entry(source_video, ready=False)))

    summary = build_publish_queue(manifest, tmp_path / "queue", list(ALLOWED_PLATFORMS))

    assert summary["videos_seen"] == 0
    assert not (tmp_path / "queue").exists()


def test_include_not_ready_includes_but_packet_not_ready(tmp_path: Path):
    source_video = tmp_path / "videos" / "post-1" / "video.mp4"
    manifest = tmp_path / "manifest.json"
    _write_video(source_video)
    _write_json(manifest, _manifest(_video_entry(source_video, ready=False)))

    summary = build_publish_queue(
        manifest,
        tmp_path / "queue",
        list(ALLOWED_PLATFORMS),
        include_not_ready=True,
    )

    metadata = json.loads((tmp_path / "queue" / "post-1" / "metadata.json").read_text(encoding="utf-8"))
    assert summary["videos_seen"] == 1
    assert summary["items"][0]["packet_ready"] is False
    assert metadata["packet_ready"] is False
    assert metadata["packet_errors"] == ["Source video ready_for_upload is not true"]


def test_missing_video_file_skipped_with_error(tmp_path: Path):
    source_video = tmp_path / "videos" / "post-1" / "video.mp4"
    manifest = tmp_path / "manifest.json"
    _write_json(manifest, _manifest(_video_entry(source_video)))

    summary = build_publish_queue(manifest, tmp_path / "queue", list(ALLOWED_PLATFORMS))

    assert summary["packets_skipped"] == 1
    assert "video_path missing or not a file" in summary["errors"][0]


def test_existing_packet_skipped_when_overwrite_false(tmp_path: Path):
    source_video = tmp_path / "videos" / "post-1" / "video.mp4"
    packet_video = tmp_path / "queue" / "post-1" / "video.mp4"
    manifest = tmp_path / "manifest.json"
    _write_video(source_video, b"new")
    _write_video(packet_video, b"old")
    _write_json(manifest, _manifest(_video_entry(source_video)))

    summary = build_publish_queue(manifest, tmp_path / "queue", list(ALLOWED_PLATFORMS))

    assert summary["packets_skipped"] == 1
    assert summary["skipped_existing"] == 1
    assert packet_video.read_bytes() == b"old"


def test_overwrite_true_replaces_packet(tmp_path: Path):
    source_video = tmp_path / "videos" / "post-1" / "video.mp4"
    packet_video = tmp_path / "queue" / "post-1" / "video.mp4"
    manifest = tmp_path / "manifest.json"
    _write_video(source_video, b"new")
    _write_video(packet_video, b"old")
    _write_json(manifest, _manifest(_video_entry(source_video)))

    summary = build_publish_queue(manifest, tmp_path / "queue", list(ALLOWED_PLATFORMS), overwrite=True)

    assert summary["packets_written"] == 1
    assert packet_video.read_bytes() == b"new"


def test_dry_run_creates_no_files(tmp_path: Path):
    source_video = tmp_path / "videos" / "post-1" / "video.mp4"
    manifest = tmp_path / "manifest.json"
    _write_video(source_video)
    _write_json(manifest, _manifest(_video_entry(source_video)))

    summary = build_publish_queue(manifest, tmp_path / "queue", list(ALLOWED_PLATFORMS), dry_run=True)

    assert summary["videos_seen"] == 1
    assert summary["packets_written"] == 0
    assert not (tmp_path / "queue").exists()


def test_limit_works(tmp_path: Path):
    entries = []
    for post_id in ("post-1", "post-2"):
        source_video = tmp_path / "videos" / post_id / "video.mp4"
        _write_video(source_video)
        entries.append(_video_entry(source_video, post_id=post_id))
    manifest = tmp_path / "manifest.json"
    _write_json(manifest, _manifest(*entries))

    summary = build_publish_queue(manifest, tmp_path / "queue", list(ALLOWED_PLATFORMS), limit=1)

    assert summary["videos_seen"] == 1
    assert (tmp_path / "queue" / "post-1").exists()
    assert not (tmp_path / "queue" / "post-2").exists()


def test_platform_normalization_default_all():
    assert normalize_platforms(None) == list(ALLOWED_PLATFORMS)


def test_platform_normalization_accepts_comma_separated_values():
    assert normalize_platforms(["tiktok,instagram_reels", "youtube_shorts"]) == list(ALLOWED_PLATFORMS)


def test_invalid_platform_exits_1(capsys):
    with patch("sys.argv", ["build_publish_queue.py", "--platform", "bad"]):
        assert main() == 1

    assert "Invalid platform: bad" in capsys.readouterr().err


def test_atomic_temp_files_not_left_after_success(tmp_path: Path):
    source_video = tmp_path / "videos" / "post-1" / "video.mp4"
    manifest = tmp_path / "manifest.json"
    _write_video(source_video)
    _write_json(manifest, _manifest(_video_entry(source_video)))

    build_publish_queue(manifest, tmp_path / "queue", list(ALLOWED_PLATFORMS))

    packet_dir = tmp_path / "queue" / "post-1"
    assert not (packet_dir / "video.tmp.mp4").exists()
    assert not (packet_dir / "caption.txt.tmp").exists()
    assert not (packet_dir / "metadata.json.tmp").exists()


def test_cli_summary_printed(tmp_path: Path, capsys):
    source_video = tmp_path / "videos" / "post-1" / "video.mp4"
    manifest = tmp_path / "manifest.json"
    _write_video(source_video)
    _write_json(manifest, _manifest(_video_entry(source_video)))
    args = [
        "build_publish_queue.py",
        "--video-manifest",
        str(manifest),
        "--output-dir",
        str(tmp_path / "queue"),
        "--platform",
        "tiktok,instagram_reels",
        "--dry-run",
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["videos_seen"] == 1
    assert summary["platforms"] == ["tiktok", "instagram_reels"]
    assert summary["dry_run"] is True
