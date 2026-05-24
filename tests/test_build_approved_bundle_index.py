from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.build_approved_bundle_index import (
    build_bundle_index,
    load_bundle_metadata,
    main,
    summarize_bundle,
    write_index_atomically,
)


def _write_metadata(bundle_dir: Path, **overrides) -> dict:
    payload = {
        "post_id": bundle_dir.name,
        "account_handle": "economika",
        "url": f"https://x.com/economika/status/{bundle_dir.name}",
        "text_prefix": "A useful economic signal",
        "score": 10.0,
        "metrics": {"likes": 7},
        "review_status": "approved",
        "reviewed_at": "2026-05-24T10:00:00Z",
        "local_media": [],
        "bundle_errors": [],
    }
    payload.update(overrides)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "metadata.json").write_text(json.dumps(payload), encoding="utf-8")
    return payload


def test_missing_bundles_dir_creates_empty_index_and_exits_0(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    bundles_dir = tmp_path / "missing-approved"
    output_json = bundles_dir / "index.json"

    args = [
        "build_approved_bundle_index.py",
        "--bundles-dir", str(bundles_dir),
        "--output-json", str(output_json),
    ]
    with patch("sys.argv", args):
        assert main() == 0

    assert output_json.exists()
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["bundle_count"] == 0
    assert payload["invalid_bundle_count"] == 0
    assert payload["bundles"] == []
    assert payload["invalid_bundles"] == []

    summary = json.loads(capsys.readouterr().out)
    assert summary["valid_bundle_count"] == 0
    assert summary["invalid_bundle_count"] == 0
    assert summary["errors"] == []


def test_empty_bundles_dir_creates_empty_index(tmp_path: Path):
    bundles_dir = tmp_path / "approved"
    bundles_dir.mkdir()

    index = build_bundle_index(bundles_dir)

    assert index["bundle_count"] == 0
    assert index["invalid_bundle_count"] == 0
    assert index["bundles"] == []


def test_valid_metadata_creates_one_index_bundle(tmp_path: Path):
    bundles_dir = tmp_path / "approved"
    _write_metadata(bundles_dir / "post-1")
    (bundles_dir / "index.json").write_text("{}", encoding="utf-8")
    (bundles_dir / "loose.txt").write_text("ignored", encoding="utf-8")

    index = build_bundle_index(bundles_dir)

    assert index["bundle_count"] == 1
    bundle = index["bundles"][0]
    assert bundle["post_id"] == "post-1"
    assert bundle["account_handle"] == "economika"
    assert bundle["review_status"] == "approved"
    assert bundle["metadata_path"].endswith("post-1/metadata.json")
    assert bundle["bundle_dir"].endswith("post-1")
    assert bundle["local_media_count"] == 0
    assert bundle["has_media"] is False
    assert bundle["ready_for_render"] is True


def test_index_sorted_by_score_reviewed_at_and_post_id(tmp_path: Path):
    bundles_dir = tmp_path / "approved"
    _write_metadata(bundles_dir / "c-post", score=20, reviewed_at="2026-05-24T08:00:00Z")
    _write_metadata(bundles_dir / "b-post", score=20, reviewed_at="2026-05-24T11:00:00Z")
    _write_metadata(bundles_dir / "a-post", score=20, reviewed_at="2026-05-24T11:00:00Z")
    _write_metadata(bundles_dir / "top-post", score=30, reviewed_at="2026-05-23T11:00:00Z")

    index = build_bundle_index(bundles_dir)

    assert [bundle["post_id"] for bundle in index["bundles"]] == [
        "top-post",
        "a-post",
        "b-post",
        "c-post",
    ]


def test_metadata_missing_excluded_and_counted_invalid(tmp_path: Path):
    bundle_dir = tmp_path / "approved" / "missing-meta"
    bundle_dir.mkdir(parents=True)

    index = build_bundle_index(tmp_path / "approved", include_invalid=True)

    assert index["bundle_count"] == 0
    assert index["invalid_bundle_count"] == 1
    assert "Metadata file not found" in index["invalid_bundles"][0]["error"]


def test_invalid_json_excluded_and_counted_invalid(tmp_path: Path):
    bundle_dir = tmp_path / "approved" / "bad-json"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "metadata.json").write_text("{invalid", encoding="utf-8")

    index = build_bundle_index(tmp_path / "approved", include_invalid=True)

    assert index["bundle_count"] == 0
    assert index["invalid_bundle_count"] == 1
    assert "Invalid JSON" in index["invalid_bundles"][0]["error"]


def test_metadata_missing_post_id_excluded_and_counted_invalid(tmp_path: Path):
    bundles_dir = tmp_path / "approved"
    _write_metadata(bundles_dir / "missing-id", post_id="")

    index = build_bundle_index(bundles_dir, include_invalid=True)

    assert index["bundle_count"] == 0
    assert index["invalid_bundle_count"] == 1
    assert "missing required 'post_id'" in index["invalid_bundles"][0]["error"]


def test_review_status_not_approved_is_strict_invalid(tmp_path: Path):
    bundles_dir = tmp_path / "approved"
    _write_metadata(bundles_dir / "rejected-post", review_status="rejected")

    bundle, invalid = summarize_bundle(bundles_dir / "rejected-post")

    assert bundle is None
    assert invalid is not None
    assert "review_status must be 'approved'" in invalid["error"]


def test_local_media_downloaded_and_skipped_existing_included(tmp_path: Path):
    bundles_dir = tmp_path / "approved"
    _write_metadata(
        bundles_dir / "media-post",
        local_media=[
            {
                "index": 1,
                "filename": "media_1.jpg",
                "local_path": str(bundles_dir / "media-post" / "media_1.jpg"),
                "content_type": "image/jpeg",
                "source_url": "https://example.com/1.jpg",
                "status": "downloaded",
            },
            {
                "index": 2,
                "filename": "media_2.png",
                "local_path": str(bundles_dir / "media-post" / "media_2.png"),
                "content_type": "image/png",
                "source_url": "https://example.com/2.png",
                "status": "skipped_existing",
            },
        ],
    )

    index = build_bundle_index(bundles_dir)

    bundle = index["bundles"][0]
    assert bundle["local_media_count"] == 2
    assert bundle["has_media"] is True
    assert [item["filename"] for item in bundle["media_files"]] == ["media_1.jpg", "media_2.png"]


def test_local_media_failed_and_unsupported_excluded(tmp_path: Path):
    bundles_dir = tmp_path / "approved"
    _write_metadata(
        bundles_dir / "media-post",
        local_media=[
            {"index": 1, "status": "failed", "filename": "media_1.jpg", "local_path": "media_1.jpg"},
            {
                "index": 2,
                "status": "skipped_unsupported_url",
                "filename": "media_2.jpg",
                "local_path": "media_2.jpg",
            },
            {"index": 3, "status": "downloaded", "filename": "media_3.jpg", "local_path": "media_3.jpg"},
        ],
    )

    index = build_bundle_index(bundles_dir)

    bundle = index["bundles"][0]
    assert bundle["local_media_count"] == 1
    assert bundle["media_files"][0]["filename"] == "media_3.jpg"


def test_bundle_errors_keep_bundle_but_not_ready_for_render(tmp_path: Path):
    bundles_dir = tmp_path / "approved"
    _write_metadata(bundles_dir / "partial-post", bundle_errors=["Failed to download media_1"])

    index = build_bundle_index(bundles_dir)

    assert index["bundle_count"] == 1
    assert index["bundles"][0]["ready_for_render"] is False
    assert index["bundles"][0]["bundle_errors"] == ["Failed to download media_1"]


def test_output_written_atomically(tmp_path: Path):
    output_json = tmp_path / "approved" / "index.json"
    payload = {"bundle_count": 0}

    with patch("os.replace", wraps=os.replace) as mock_replace:
        write_index_atomically(payload, output_json)

    assert output_json.exists()
    args = mock_replace.call_args[0]
    assert args[0].endswith("index.json.tmp")
    assert args[1].endswith("index.json")


def test_output_write_parent_dir_created(tmp_path: Path):
    output_json = tmp_path / "new" / "nested" / "index.json"

    write_index_atomically({"bundle_count": 0}, output_json)

    assert output_json.exists()


def test_cli_summary_printed(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    bundles_dir = tmp_path / "approved"
    output_json = tmp_path / "out" / "index.json"
    _write_metadata(bundles_dir / "summary-post")

    args = [
        "build_approved_bundle_index.py",
        "--bundles-dir", str(bundles_dir),
        "--output-json", str(output_json),
    ]
    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["valid_bundle_count"] == 1
    assert summary["invalid_bundle_count"] == 0
    assert summary["errors"] == []


def test_load_bundle_metadata_requires_object(tmp_path: Path):
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="top-level must be a JSON object"):
        load_bundle_metadata(metadata_path)
