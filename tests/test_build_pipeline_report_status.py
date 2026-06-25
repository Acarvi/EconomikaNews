from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from scripts.build_pipeline_report import main


def _write_json(path: Path, payload: dict | list | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")


def _setup_base_manifests(tmp_path: Path) -> tuple[Path, Path, Path]:
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
                    "platforms": ["tiktok", "instagram_reels", "youtube_shorts"],
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


def _run_with_status(
    tmp_path: Path,
    status_payload: dict | str | None,
    capsys,
    extra_args: list[str] | None = None,
    use_manifests: bool = True
) -> tuple[int, str, dict]:
    if use_manifests:
        render, video, publish = _setup_base_manifests(tmp_path)
    else:
        render = tmp_path / "renders.json"
        video = tmp_path / "videos.json"
        publish = tmp_path / "publish.json"
    
    status_file = tmp_path / "status.json"
    if status_payload is not None:
        _write_json(status_file, status_payload)
    
    output_md = tmp_path / "report.md"
    output_json = tmp_path / "report.json"
    
    args = ["build_pipeline_report.py"]
    if use_manifests:
        args.extend([
            "--render-manifest", str(render),
            "--video-manifest", str(video),
            "--publish-queue-manifest", str(publish),
        ])
    else:
        args.extend([
            "--render-manifest", str(render),
            "--video-manifest", str(video),
            "--publish-queue-manifest", str(publish),
        ])
    
    args.extend([
        "--publish-status-file", str(status_file),
        "--output-md", str(output_md),
        "--output-json", str(output_json),
    ])
    
    if extra_args:
        args.extend(extra_args)
        
    with patch("sys.argv", args):
        exit_code = main()
        
    captured = capsys.readouterr()
    stdout_json = {}
    if captured.out.strip():
        try:
            stdout_json = json.loads(captured.out)
        except json.JSONDecodeError:
            pass
            
    markdown_content = ""
    if output_md.exists():
        markdown_content = output_md.read_text(encoding="utf-8")
        
    json_summary = {}
    if output_json.exists():
        json_summary = json.loads(output_json.read_text(encoding="utf-8"))
        
    return exit_code, markdown_content, json_summary


def test_missing_status_file_defaults_platforms_to_pending(tmp_path: Path, capsys):
    exit_code, markdown, summary = _run_with_status(tmp_path, None, capsys)
    assert exit_code == 0
    assert summary["publish_status_found"] is False
    assert summary["publish_status_valid"] is True
    assert summary["publish_complete"] is False
    assert summary["publish_pending_count"] == 3
    assert summary["publish_failed_count"] == 0
    assert "- [ ] Upload manually to: tiktok" in markdown
    assert "- [ ] Upload manually to: instagram_reels" in markdown
    assert "- [ ] Upload manually to: youtube_shorts" in markdown


def test_valid_status_file_shows_statuses_and_details_in_markdown(tmp_path: Path, capsys):
    status_payload = {
        "version": 1,
        "entries": [
            {
                "post_id": "post-1",
                "platform": "tiktok",
                "status": "published",
                "external_url": "https://tiktok.com/123",
                "notes": "First manual test upload",
                "updated_at": "2026-06-25T12:00:00Z"
            },
            {
                "post_id": "post-1",
                "platform": "instagram_reels",
                "status": "skipped",
                "notes": "Incompatible format",
                "updated_at": "2026-06-25T12:05:00Z"
            },
            {
                "post_id": "post-1",
                "platform": "youtube_shorts",
                "status": "failed",
                "notes": "Network failure",
                "updated_at": "2026-06-25T12:10:00Z"
            }
        ]
    }
    exit_code, markdown, summary = _run_with_status(tmp_path, status_payload, capsys)
    assert exit_code == 0
    assert summary["publish_status_found"] is True
    assert summary["publish_status_valid"] is True
    
    assert summary["publish_status_counts"]["published"] == 1
    assert summary["publish_status_counts"]["skipped"] == 1
    assert summary["publish_status_counts"]["failed"] == 1
    assert summary["publish_complete"] is False
    assert summary["publish_pending_count"] == 0
    assert summary["publish_failed_count"] == 1
    
    # Check Markdown contains external URL, notes, and checklist checkbox states
    assert "Manual Publish Status" in markdown
    assert "https://tiktok.com/123" in markdown
    assert "First manual test upload" in markdown
    assert "Incompatible format" in markdown
    assert "Network failure" in markdown
    
    # Checklist verification
    assert "- [x] Published on tiktok: https://tiktok.com/123" in markdown
    assert "- [x] Skipped instagram_reels: Incompatible format" in markdown
    assert "- [ ] Retry failed youtube_shorts: Network failure" in markdown


def test_checklist_pending_unchecked(tmp_path: Path, capsys):
    status_payload = {
        "version": 1,
        "entries": [
            {
                "post_id": "post-1",
                "platform": "tiktok",
                "status": "pending",
                "updated_at": "2026-06-25T12:00:00Z"
            }
        ]
    }
    exit_code, markdown, summary = _run_with_status(tmp_path, status_payload, capsys)
    assert exit_code == 0
    assert "- [ ] Upload manually to: tiktok" in markdown


def test_publish_complete_when_all_published_or_skipped(tmp_path: Path, capsys):
    status_payload = {
        "version": 1,
        "entries": [
            {
                "post_id": "post-1",
                "platform": "tiktok",
                "status": "published",
                "updated_at": "2026-06-25T12:00:00Z"
            },
            {
                "post_id": "post-1",
                "platform": "instagram_reels",
                "status": "skipped",
                "updated_at": "2026-06-25T12:00:00Z"
            },
            {
                "post_id": "post-1",
                "platform": "youtube_shorts",
                "status": "published",
                "updated_at": "2026-06-25T12:00:00Z"
            }
        ]
    }
    exit_code, markdown, summary = _run_with_status(tmp_path, status_payload, capsys)
    assert exit_code == 0
    assert summary["publish_complete"] is True
    assert summary["publish_pending_count"] == 0
    assert summary["publish_failed_count"] == 0


def test_invalid_status_json_does_not_crash(tmp_path: Path, capsys):
    exit_code, markdown, summary = _run_with_status(tmp_path, "{invalid_json", capsys)
    assert exit_code == 0
    assert summary["publish_status_found"] is True
    assert summary["publish_status_valid"] is False
    assert "Invalid JSON" in summary["publish_status_error"]
    assert "Publish status could not be loaded" in markdown


def test_unmatched_status_entry(tmp_path: Path, capsys):
    status_payload = {
        "version": 1,
        "entries": [
            {
                "post_id": "post-2",
                "platform": "tiktok",
                "status": "published",
                "external_url": "https://tiktok.com/unmatched",
                "notes": "Unmatched note",
                "updated_at": "2026-06-25T12:00:00Z"
            }
        ]
    }
    exit_code, markdown, summary = _run_with_status(tmp_path, status_payload, capsys)
    assert exit_code == 0
    assert len(summary["unmatched_publish_status_entries"]) == 1
    assert summary["unmatched_publish_status_entries"][0]["post_id"] == "post-2"
    assert "Unmatched Publish Status Entries" in markdown
    assert "post-2" in markdown
    assert "https://tiktok.com/unmatched" in markdown


def test_status_matching_by_post_id_and_platform(tmp_path: Path, capsys):
    status_payload = {
        "version": 1,
        "entries": [
            {
                "post_id": "post-1",
                "platform": "tiktok",
                "status": "published",
                "updated_at": "2026-06-25T12:00:00Z"
            },
            {
                "post_id": "different-post",
                "platform": "tiktok",
                "status": "skipped",
                "updated_at": "2026-06-25T12:00:00Z"
            }
        ]
    }
    exit_code, markdown, summary = _run_with_status(tmp_path, status_payload, capsys)
    assert exit_code == 0
    
    by_packet = summary["publish_status_by_packet"][0]
    tiktok_status = next(p for p in by_packet["platforms"] if p["platform"] == "tiktok")
    reels_status = next(p for p in by_packet["platforms"] if p["platform"] == "instagram_reels")
    assert tiktok_status["status"] == "published"
    assert reels_status["status"] == "pending"


def test_no_publish_queue_manifest_works(tmp_path: Path, capsys):
    status_payload = {
        "version": 1,
        "entries": []
    }
    exit_code, markdown, summary = _run_with_status(tmp_path, status_payload, capsys, use_manifests=False)
    assert exit_code == 0
    assert summary["publish_queue_manifest_found"] is False
    assert "# Economika Local Pipeline Report" in markdown
