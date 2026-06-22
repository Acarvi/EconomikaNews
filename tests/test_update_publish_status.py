from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import update_publish_status as status_script


NOW = "2026-06-22T10:00:00Z"
LATER = "2026-06-22T11:00:00Z"


def fake_manifest() -> dict:
    return {
        "packets": [
            {
                "post_id": "post-1",
                "platforms": ["tiktok", "instagram_reels"],
                "packet_ready": True,
            },
            {"post_id": "post-2", "platforms": ["youtube_shorts"], "packet_ready": True},
        ]
    }


def write_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fake_manifest()), encoding="utf-8")


def run_cli(tmp_path: Path, *args: str) -> int:
    return status_script.main(
        [
            *args,
            "--status-file",
            str(tmp_path / "status.json"),
            "--publish-queue-manifest",
            str(tmp_path / "manifest.json"),
        ]
    )


def test_missing_status_file_returns_new_payload(tmp_path: Path):
    assert status_script.load_status_file(tmp_path / "missing.json") == {
        "version": 1,
        "updated_at": None,
        "entries": [],
    }


def test_mark_command_creates_missing_status_file(tmp_path: Path):
    assert run_cli(
        tmp_path,
        "mark",
        "--post-id",
        "post-1",
        "--platform",
        "tiktok",
        "--status",
        "drafted",
        "--now",
        NOW,
    ) == 0
    payload = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert payload["entries"][0]["status"] == "drafted"


def test_mark_creates_entry_and_stores_optional_fields(tmp_path: Path):
    payload = status_script.load_status_file(tmp_path / "status.json")
    entry = status_script.mark_status(
        payload,
        post_id="post-1",
        platform="tiktok",
        status="uploaded",
        external_url="https://example.com/video",
        notes="Uploaded manually",
        now=NOW,
    )

    assert entry["status"] == "uploaded"
    assert entry["external_url"] == "https://example.com/video"
    assert entry["notes"] == "Uploaded manually"
    assert entry["published_at"] is None
    assert len(payload["entries"]) == 1


def test_mark_updates_entry_and_appends_history():
    payload = {"version": 1, "updated_at": None, "entries": []}
    first = status_script.mark_status(
        payload, post_id="post-1", platform="tiktok", status="drafted", now=NOW
    )
    updated = status_script.mark_status(
        payload, post_id="post-1", platform="tiktok", status="uploaded", now=LATER
    )

    assert updated is first
    assert updated["status"] == "uploaded"
    assert updated["created_at"] == NOW
    assert updated["updated_at"] == LATER
    assert [item["status"] for item in updated["history"]] == ["drafted", "uploaded"]


def test_published_sets_published_at_once():
    payload = {"version": 1, "updated_at": None, "entries": []}
    entry = status_script.mark_status(
        payload, post_id="post-1", platform="tiktok", status="published", now=NOW
    )
    status_script.mark_status(
        payload, post_id="post-1", platform="tiktok", status="published", now=LATER
    )

    assert entry["published_at"] == NOW


def test_non_published_does_not_set_published_at():
    payload = {"version": 1, "updated_at": None, "entries": []}
    entry = status_script.mark_status(
        payload, post_id="post-1", platform="tiktok", status="failed", now=NOW
    )
    assert entry["published_at"] is None


@pytest.mark.parametrize(
    ("flag", "value"),
    [("--platform", "facebook"), ("--status", "done")],
)
def test_invalid_platform_or_status_exits_one(tmp_path: Path, flag: str, value: str, capsys):
    args = ["mark", "--post-id", "post-1", "--platform", "tiktok", "--status", "pending"]
    args[args.index(flag) + 1] = value
    assert run_cli(tmp_path, *args) == 1
    assert "invalid" in capsys.readouterr().err.lower()


def test_strict_rejects_unknown_post_id(tmp_path: Path, capsys):
    write_manifest(tmp_path / "manifest.json")
    result = run_cli(
        tmp_path,
        "mark",
        "--post-id",
        "unknown",
        "--platform",
        "tiktok",
        "--status",
        "pending",
        "--strict",
    )
    assert result == 1
    assert "not in the publish queue manifest" in capsys.readouterr().err


def test_non_strict_allows_unknown_post_id_with_warning(tmp_path: Path, capsys):
    write_manifest(tmp_path / "manifest.json")
    result = run_cli(
        tmp_path,
        "mark",
        "--post-id",
        "unknown",
        "--platform",
        "tiktok",
        "--status",
        "pending",
        "--now",
        NOW,
    )
    assert result == 0
    assert "Warning:" in capsys.readouterr().err
    assert (tmp_path / "status.json").exists()


def test_strict_rejects_platform_not_in_packet(tmp_path: Path, capsys):
    write_manifest(tmp_path / "manifest.json")
    result = run_cli(
        tmp_path,
        "mark",
        "--post-id",
        "post-1",
        "--platform",
        "youtube_shorts",
        "--status",
        "pending",
        "--strict",
    )
    assert result == 1
    assert "not listed" in capsys.readouterr().err


def test_strict_list_rejects_unknown_post_filter(tmp_path: Path, capsys):
    write_manifest(tmp_path / "manifest.json")
    assert run_cli(tmp_path, "list", "--post-id", "unknown", "--strict") == 1
    assert "not in the publish queue manifest" in capsys.readouterr().err


def test_list_includes_pending_manifest_entries_before_mark():
    entries = status_script.list_statuses(
        {"version": 1, "entries": []}, fake_manifest()
    )
    assert len(entries) == 3
    assert {entry["status"] for entry in entries} == {"pending"}


def test_list_filters_by_post_and_platform():
    payload = {"version": 1, "entries": []}
    status_script.mark_status(
        payload, post_id="post-1", platform="tiktok", status="published", now=NOW
    )
    by_post = status_script.list_statuses(payload, fake_manifest(), post_id="post-1")
    by_platform = status_script.list_statuses(
        payload, fake_manifest(), platform="youtube_shorts"
    )
    assert len(by_post) == 2
    assert {item["post_id"] for item in by_post} == {"post-1"}
    assert [(item["post_id"], item["platform"]) for item in by_platform] == [
        ("post-2", "youtube_shorts")
    ]


def test_summary_counts_pending_and_recorded_statuses():
    payload = {"version": 1, "entries": []}
    status_script.mark_status(
        payload, post_id="post-1", platform="tiktok", status="published", now=NOW
    )
    status_script.mark_status(
        payload, post_id="post-1", platform="instagram_reels", status="skipped", now=NOW
    )
    status_script.mark_status(
        payload, post_id="outside", platform="tiktok", status="failed", now=NOW
    )
    summary = status_script.summarize_statuses(payload, fake_manifest())

    assert summary["total_queueable"] == 3
    assert summary["total"] == 4
    assert summary["by_status"]["pending"] == 1
    assert summary["by_status"]["published"] == 1
    assert summary["by_status"]["skipped"] == 1
    assert summary["by_status"]["failed"] == 1


def test_atomic_write_leaves_no_tmp_file(tmp_path: Path):
    path = tmp_path / "nested" / "status.json"
    status_script.write_status_file_atomically({"version": 1, "entries": []}, path)
    assert path.exists()
    assert not path.with_name("status.json.tmp").exists()


def test_invalid_existing_status_json_exits_one(tmp_path: Path, capsys):
    (tmp_path / "status.json").write_text("{broken", encoding="utf-8")
    assert run_cli(tmp_path, "list") == 1
    assert "invalid status JSON" in capsys.readouterr().err


def test_text_formats_work(tmp_path: Path, capsys):
    write_manifest(tmp_path / "manifest.json")
    assert run_cli(tmp_path, "list", "--format", "text") == 0
    assert "POST ID" in capsys.readouterr().out
    assert run_cli(tmp_path, "summary", "--format", "text") == 0
    output = capsys.readouterr().out
    assert "PLATFORM" in output
    assert "Queueable combinations" in output
