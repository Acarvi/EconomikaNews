from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

from app.storage.sqlite_review_state import set_review_status
from scripts.export_approved_candidates import (
    build_approved_export,
    load_candidates_payload,
    write_approved_export,
)


def _write_candidates(path: Path) -> dict:
    payload = {
        "candidates": [
            {
                "score": 100.0,
                "account_handle": "alpha",
                "post_id": "alpha-1",
                "url": "https://x.com/alpha/status/1",
                "text_prefix": "Alpha post",
                "metrics": {"views": 1000, "likes": 10, "reposts": 2, "replies": 1},
                "media_count": 1,
                "media": [{"media_type": "image", "url": "https://example.com/a.jpg"}],
                "source": "x",
                "is_new": True,
            },
            {
                "score": 50.0,
                "account_handle": "beta",
                "post_id": "beta-2",
                "url": "https://x.com/beta/status/2",
                "text_prefix": "Beta post",
                "metrics": {"views": 500, "likes": 5, "reposts": 1, "replies": 0},
                "media_count": 0,
                "media": [],
                "source": "x",
            },
            {
                "score": 5.0,
                "account_handle": "gamma",
                "post_id": "gamma-3",
                "url": "https://x.com/gamma/status/3",
                "text_prefix": "Gamma post",
                "metrics": {"views": 5, "likes": 0, "reposts": 0, "replies": 0},
                "media_count": 0,
                "media": [],
                "source": "x",
            },
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _run_export(candidates_file: Path, db_path: Path, output_json: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/export_approved_candidates.py",
            "--candidates-file",
            str(candidates_file),
            "--db-path",
            str(db_path),
            "--output-json",
            str(output_json),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_missing_candidates_file_returns_exit_code_1(tmp_path: Path) -> None:
    result = _run_export(tmp_path / "missing.json", tmp_path / "review.db", tmp_path / "out.json")

    assert result.returncode == 1
    assert "Candidates file not found" in result.stderr


def test_invalid_json_returns_exit_code_1(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    candidates_file.write_text("{invalid", encoding="utf-8")

    result = _run_export(candidates_file, tmp_path / "review.db", tmp_path / "out.json")

    assert result.returncode == 1
    assert "Invalid candidates JSON" in result.stderr


def test_no_approved_candidates_writes_zero_count(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    db_path = tmp_path / "review.db"
    output_json = tmp_path / "outputs" / "approved_candidates.json"
    _write_candidates(candidates_file)

    result = _run_export(candidates_file, db_path, output_json)

    assert result.returncode == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["approved_count"] == 0
    assert payload["candidates"] == []


def test_approved_candidates_are_exported_with_review_metadata(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    db_path = tmp_path / "review.db"
    output_json = tmp_path / "outputs" / "approved_candidates.json"
    _write_candidates(candidates_file)
    set_review_status(db_path, "alpha-1", "approved", "good")
    set_review_status(db_path, "beta-2", "rejected", "no")

    result = _run_export(candidates_file, db_path, output_json)

    assert result.returncode == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["approved_count"] == 1
    assert [c["post_id"] for c in payload["candidates"]] == ["alpha-1"]
    candidate = payload["candidates"][0]
    assert candidate["review_status"] == "approved"
    assert candidate["reviewed_at"] is not None
    assert candidate["review_note"] == "good"
    assert candidate["review_updated_at"] is not None


def test_rejected_pending_and_implicit_pending_are_not_exported(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    db_path = tmp_path / "review.db"
    output_json = tmp_path / "out" / "approved.json"
    _write_candidates(candidates_file)
    set_review_status(db_path, "alpha-1", "approved")
    set_review_status(db_path, "beta-2", "rejected")
    set_review_status(db_path, "gamma-3", "pending")

    result = _run_export(candidates_file, db_path, output_json)

    assert result.returncode == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert [c["post_id"] for c in payload["candidates"]] == ["alpha-1"]


def test_candidate_json_is_not_mutated(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    db_path = tmp_path / "review.db"
    source_payload = _write_candidates(candidates_file)
    source_copy = copy.deepcopy(source_payload)
    set_review_status(db_path, "alpha-1", "approved")

    loaded = load_candidates_payload(candidates_file)
    exported = build_approved_export(loaded, db_path, candidates_file)
    write_approved_export(exported, tmp_path / "outputs" / "approved_candidates.json")

    assert source_payload == source_copy
    assert json.loads(candidates_file.read_text(encoding="utf-8")) == source_copy


def test_output_parent_directory_is_created(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    db_path = tmp_path / "review.db"
    _write_candidates(candidates_file)
    set_review_status(db_path, "alpha-1", "approved")
    output_json = tmp_path / "nested" / "folder" / "approved_candidates.json"

    result = _run_export(candidates_file, db_path, output_json)

    assert result.returncode == 0
    assert output_json.exists()
