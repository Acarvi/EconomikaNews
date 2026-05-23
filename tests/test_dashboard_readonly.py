from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.dashboard.server import render_dashboard


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

    html = render_dashboard(candidates_file)

    assert "account_count" in html
    assert "total_posts" in html
    assert "unique_posts" in html
    assert "Alpha post" in html
    assert "Beta post" in html
    assert "https://x.com/alpha/status/1" in html


def test_filters_account(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    _write_candidates(candidates_file)

    html = render_dashboard(candidates_file, "account=beta")

    assert "Beta post" in html
    assert "Alpha post" not in html


def test_filters_only_media(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    _write_candidates(candidates_file)

    html = render_dashboard(candidates_file, "only_media=true")

    assert "Alpha post" in html
    assert "Beta post" not in html
    assert "alpha-preview.jpg" in html


def test_filters_only_new(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    _write_candidates(candidates_file)

    html = render_dashboard(candidates_file, "only_new=true")

    assert "Alpha post" in html
    assert "Beta post" not in html


def test_filters_min_score(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    _write_candidates(candidates_file)

    html = render_dashboard(candidates_file, "min_score=75")

    assert "Alpha post" in html
    assert "Beta post" not in html


def test_html_escapes_candidate_text(tmp_path: Path) -> None:
    candidates_file = tmp_path / "x_candidates.json"
    _write_candidates(candidates_file)

    html = render_dashboard(candidates_file)

    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html


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
