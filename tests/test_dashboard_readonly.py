from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.dashboard.server import handle_review_post, render_dashboard
from app.storage.sqlite_review_state import (
    get_review_states,
    init_review_db,
    set_review_status,
)


def _write_candidates(path: Path) -> None:
    payload = {
        "account_count": 2,
        "total_posts": 3,
        "unique_posts": 3,
        "new_candidates": 2,
        "already_seen_candidates": 1,
        "errors": [],
        "candidates": [
            {
                "post_id": "alpha-1",
                "score": 100.0,
                "account_handle": "alpha",
                "is_new": True,
                "media_count": 1,
                "url": "https://x.com/alpha/status/1",
                "text_prefix": "Alpha post",
                "metrics": {"views": 1000, "likes": 10, "reposts": 2, "replies": 1},
                "media": [
                    {
                        "media_type": "image",
                        "url": "https://example.com/alpha.jpg",
                        "preview_url": "https://example.com/alpha-preview.jpg",
                    }
                ],
            },
            {
                "post_id": "beta-2",
                "score": 50.0,
                "account_handle": "beta",
                "is_new": False,
                "media_count": 0,
                "url": "https://x.com/beta/status/2",
                "text_prefix": "Beta post",
                "metrics": {"views": 500, "likes": 5, "reposts": 1, "replies": 0},
                "media": [],
            },
            {
                "post_id": "alpha-3",
                "score": 5.0,
                "account_handle": "alpha",
                "is_new": True,
                "media_count": 0,
                "url": "https://x.com/alpha/status/3",
                "text_prefix": "<script>alert('x')</script>",
                "metrics": {"views": 5, "likes": 0, "reposts": 0, "replies": 0},
                "media": [],
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_missing_candidates_file_returns_helpful_page(tmp_path: Path) -> None:
    html = render_dashboard(tmp_path / "missing.json")

    assert "No candidates loaded" in html
    assert "Candidates file not found" in html
    assert "python scripts\\x_fetch_accounts_probe.py" in html
    assert "--include-media --output-json" in html


def test_dashboard_loads_valid_candidates_file(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    _write_candidates(candidates_file)

    html = render_dashboard(candidates_file, db_path=tmp_path / "review.db")

    assert "account_count" in html
    assert "total_posts" in html
    assert "unique_posts" in html
    assert "approved_count" in html
    assert "pending_count" in html
    assert "Alpha post" in html
    assert "Beta post" in html
    assert "https://x.com/alpha/status/1" in html


def test_filters_account(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    _write_candidates(candidates_file)

    html = render_dashboard(candidates_file, "account=beta", db_path=tmp_path / "review.db")

    assert "Beta post" in html
    assert "Alpha post" not in html


def test_filters_only_media(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    _write_candidates(candidates_file)

    html = render_dashboard(candidates_file, "only_media=true", db_path=tmp_path / "review.db")

    assert "Alpha post" in html
    assert "Beta post" not in html
    assert "alpha-preview.jpg" in html


def test_filters_only_new(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    _write_candidates(candidates_file)

    html = render_dashboard(candidates_file, "only_new=true", db_path=tmp_path / "review.db")

    assert "Alpha post" in html
    assert "Beta post" not in html


def test_filters_min_score(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    _write_candidates(candidates_file)

    html = render_dashboard(candidates_file, "min_score=75", db_path=tmp_path / "review.db")

    assert "Alpha post" in html
    assert "Beta post" not in html


def test_html_escapes_candidate_text(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    _write_candidates(candidates_file)

    html = render_dashboard(candidates_file, db_path=tmp_path / "review.db")

    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html


def test_review_db_init_creates_table(tmp_path: Path) -> None:
    db_path = tmp_path / "review.db"

    init_review_db(db_path)

    states = get_review_states(db_path, ["missing"])
    assert states == {}


def test_implicit_pending_if_no_review_row(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    db_path = tmp_path / "review.db"
    _write_candidates(candidates_file)

    html = render_dashboard(candidates_file, db_path=db_path)

    assert 'class="status status-pending">pending<' in html


@pytest.mark.parametrize("status", ["approved", "rejected", "pending"])
def test_set_review_status_variants(tmp_path: Path, status: str) -> None:
    db_path = tmp_path / "review.db"

    set_review_status(db_path, "alpha-1", status, "checked")

    state = get_review_states(db_path, ["alpha-1"])["alpha-1"]
    assert state["status"] == status
    if status == "pending":
        assert state["reviewed_at"] is None
    else:
        assert state["reviewed_at"] is not None


def test_invalid_status_raises_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        set_review_status(tmp_path / "review.db", "alpha-1", "maybe")


def test_post_approve_changes_status_and_returns_redirect(tmp_path: Path) -> None:
    db_path = tmp_path / "review.db"

    status_code, location = handle_review_post(
        db_path,
        "/review",
        b"post_id=alpha-1&status=approved&return_to=%2F%3Fstatus%3Dpending",
    )

    state = get_review_states(db_path, ["alpha-1"])["alpha-1"]
    assert status_code == 303
    assert location == "/?status=pending"
    assert state["status"] == "approved"


def test_status_filter_approved_only_shows_approved_candidates(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    db_path = tmp_path / "review.db"
    _write_candidates(candidates_file)
    set_review_status(db_path, "beta-2", "approved")

    html = render_dashboard(candidates_file, "status=approved", db_path=db_path)

    assert "Beta post" in html
    assert "Alpha post" not in html


def test_status_filter_rejected_only_shows_rejected_candidates(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    db_path = tmp_path / "review.db"
    _write_candidates(candidates_file)
    set_review_status(db_path, "alpha-3", "rejected")

    html = render_dashboard(candidates_file, "status=rejected", db_path=db_path)

    assert "&lt;script&gt;alert" in html
    assert "Alpha post" not in html
    assert "Beta post" not in html


def test_candidate_json_is_not_mutated_by_review_action(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    db_path = tmp_path / "review.db"
    _write_candidates(candidates_file)
    before = candidates_file.read_text(encoding="utf-8")

    status_code, location = handle_review_post(
        db_path,
        "/review",
        b"post_id=alpha-1&status=rejected&return_to=%2F",
    )

    after = candidates_file.read_text(encoding="utf-8")
    assert status_code == 303
    assert location == "/"
    assert after == before


def test_html_escaping_still_works_with_review_actions(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    db_path = tmp_path / "review.db"
    _write_candidates(candidates_file)
    set_review_status(db_path, "alpha-3", "approved", "<b>unsafe</b>")

    html = render_dashboard(candidates_file, db_path=db_path)

    assert "<script>alert" not in html
    assert "<b>unsafe</b>" not in html


def test_no_runtime_secrets_files_tracked() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import subprocess; "
                "print(subprocess.check_output(["
                "'git','ls-files','runtime','*/x_headers.json','x_headers.json',"
                "'.env','.env.*','*.db'"
                "], text=True), end='')"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == ""
