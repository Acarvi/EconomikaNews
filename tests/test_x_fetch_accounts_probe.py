from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from app.ingestion.models import (
    EngagementMetrics,
    IngestionResult,
    SourceAccount,
    SourceMedia,
    SourcePost,
)
from scripts.x_fetch_accounts_probe import main


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    config_data = {
        "accounts": [
            {
                "handle": "acc1",
                "category": "politics",
                "weight": 1.0,
            },
            {
                "handle": "acc2",
                "category": "economics",
                "weight": 2.0,
            },
        ]
    }
    path = tmp_path / "accounts.yaml"
    path.write_text(yaml.dump(config_data), encoding="utf-8")
    return path


@pytest.fixture
def mock_posts() -> dict[str, list[SourcePost]]:
    captured_at = datetime.now(UTC)
    media_item = SourceMedia(
        media_type="image",
        url="https://example.com/img.jpg",
        preview_url="https://example.com/img_prev.jpg",
    )

    # Post 1 (acc1)
    # views=100, likes=10, reposts=5, replies=2
    # Score = (100 + 10*1 + 5*3 + 2*2) * 1.0 = 129
    p1 = SourcePost(
        source="x",
        post_id="post1",
        url="https://x.com/acc1/status/post1",
        author_handle="acc1",
        text="Text for post 1",
        created_at=captured_at,
        captured_at=captured_at,
        media=[media_item],
        metrics=EngagementMetrics(likes=10, reposts=5, replies=2, views=100),
    )

    # Post 2 (acc1) - Lower score copy
    # views=0, likes=1, reposts=0, replies=0
    # Score = (0 + 1) * 1.0 = 1
    p2_low = SourcePost(
        source="x",
        post_id="post2",
        url="https://x.com/acc1/status/post2",
        author_handle="acc1",
        text="Text for post 2 (low)",
        created_at=captured_at,
        captured_at=captured_at,
        media=[],
        metrics=EngagementMetrics(likes=1, reposts=0, replies=0, views=0),
    )

    # Post 2 (acc2) - Higher score copy (acc2 has weight 2.0)
    # views=0, likes=1, reposts=0, replies=0
    # Score = (0 + 1) * 2.0 = 2
    p2_high = SourcePost(
        source="x",
        post_id="post2",
        url="https://x.com/acc2/status/post2",
        author_handle="acc2",
        text="Text for post 2 (high)",
        created_at=captured_at,
        captured_at=captured_at,
        media=[],
        metrics=EngagementMetrics(likes=1, reposts=0, replies=0, views=0),
    )

    # Post 3 (acc2)
    # views=1000, likes=20, reposts=10, replies=5
    # Score = (1000 + 20*1 + 10*3 + 5*2) * 2.0 = (1000 + 20 + 30 + 10) * 2.0 = 1060 * 2.0 = 2120
    p3 = SourcePost(
        source="x",
        post_id="post3",
        url="https://x.com/acc2/status/post3",
        author_handle="acc2",
        text="Text for post 3",
        created_at=captured_at,
        captured_at=captured_at,
        media=[media_item, media_item],
        metrics=EngagementMetrics(likes=20, reposts=10, replies=5, views=1000),
    )

    return {
        "acc1": [p1, p2_low],
        "acc2": [p2_high, p3],
    }


def test_invalid_config_file_returns_error_code(tmp_path: Path) -> None:
    # Test missing file
    with patch("sys.argv", ["script", "--accounts-file", str(tmp_path / "missing.yaml")]):
        assert main() == 1

    # Test invalid format (not a list under 'accounts')
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("accounts: not-a-list", encoding="utf-8")
    with patch("sys.argv", ["script", "--accounts-file", str(bad_config)]):
        assert main() == 1


@patch("scripts.x_fetch_accounts_probe.XInternalApiProvider")
def test_fetch_accounts_scoring_dedupe_and_sorting(
    mock_provider_cls: MagicMock,
    temp_config_file: Path,
    mock_posts: dict[str, list[SourcePost]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Setup mock provider instance
    mock_provider = MagicMock()
    mock_provider_cls.return_value = mock_provider
    mock_provider.provider_name = "x_internal_api"

    def fetch_side_effect(account: SourceAccount, lookback_hours: int) -> IngestionResult:
        posts = mock_posts.get(account.handle, [])
        return IngestionResult(
            account=account,
            posts=posts,
            errors=[],
            provider_name="x_internal_api",
            captured_at=datetime.now(UTC),
        )

    mock_provider.fetch_recent_posts.side_effect = fetch_side_effect

    argv = ["script", "--accounts-file", str(temp_config_file)]
    with patch("sys.argv", argv):
        status = main()

    assert status == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    # 1. Verify JSON outer structure
    assert payload["provider_name"] == "x_internal_api"
    assert payload["account_count"] == 2
    assert payload["fetched_accounts"] == ["acc1", "acc2"]
    assert payload["total_posts"] == 4
    assert payload["unique_posts"] == 3
    assert not payload["errors"]

    # 2. Verify candidates and deduplication (post2 score from acc2 (2.0) should beat acc1 (1.0))
    candidates = payload["candidates"]
    assert len(candidates) == 3

    # Candidates should be sorted descending by score: post3 (2120.0), post1 (129.0), post2 (2.0)
    assert candidates[0]["post_id"] == "post3"
    assert candidates[0]["score"] == 2120.0
    assert candidates[0]["account_handle"] == "acc2"
    assert candidates[0]["media_count"] == 2

    assert candidates[1]["post_id"] == "post1"
    assert candidates[1]["score"] == 129.0
    assert candidates[1]["account_handle"] == "acc1"
    assert candidates[1]["media_count"] == 1

    assert candidates[2]["post_id"] == "post2"
    assert candidates[2]["score"] == 2.0
    assert candidates[2]["account_handle"] == "acc2"  # Kept the higher score candidate from acc2
    assert candidates[2]["media_count"] == 0

    # Ensure media is NOT included by default
    for c in candidates:
        assert "media" not in c


@patch("scripts.x_fetch_accounts_probe.XInternalApiProvider")
def test_fetch_accounts_include_media(
    mock_provider_cls: MagicMock,
    temp_config_file: Path,
    mock_posts: dict[str, list[SourcePost]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_provider = MagicMock()
    mock_provider_cls.return_value = mock_provider
    mock_provider.provider_name = "x_internal_api"
    mock_provider.fetch_recent_posts.side_effect = lambda account, lookback_hours: IngestionResult(
        account=account,
        posts=mock_posts.get(account.handle, []),
        errors=[],
        provider_name="x_internal_api",
        captured_at=datetime.now(UTC),
    )

    argv = ["script", "--accounts-file", str(temp_config_file), "--include-media"]
    with patch("sys.argv", argv):
        assert main() == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    candidates = payload["candidates"]

    # Verify media is included when requested
    post3_candidate = next(c for c in candidates if c["post_id"] == "post3")
    assert "media" in post3_candidate
    assert len(post3_candidate["media"]) == 2
    assert post3_candidate["media"][0]["media_type"] == "image"
    assert post3_candidate["media"][0]["url"] == "https://example.com/img.jpg"


@patch("scripts.x_fetch_accounts_probe.XInternalApiProvider")
def test_fetch_accounts_output_json_behavior(
    mock_provider_cls: MagicMock,
    temp_config_file: Path,
    mock_posts: dict[str, list[SourcePost]],
    tmp_path: Path,
) -> None:
    mock_provider = MagicMock()
    mock_provider_cls.return_value = mock_provider
    mock_provider.provider_name = "x_internal_api"
    mock_provider.fetch_recent_posts.side_effect = lambda account, lookback_hours: IngestionResult(
        account=account,
        posts=mock_posts.get(account.handle, []),
        errors=[],
        provider_name="x_internal_api",
        captured_at=datetime.now(UTC),
    )

    # Case 1: omitted flag => no file written
    argv_omitted = ["script", "--accounts-file", str(temp_config_file)]
    with patch("sys.argv", argv_omitted):
        assert main() == 0

    # Ensure no file is written under default path
    default_out_path = Path("runtime/outputs/x_candidates.json")
    # (Since tests run in root directory of project, make sure it doesn't exist, but we will patch output path anyway to be clean)

    # Case 2: flag with value => custom path
    custom_temp_path = tmp_path / "sub" / "custom_candidates.json"
    argv_custom = [
        "script",
        "--accounts-file",
        str(temp_config_file),
        "--output-json",
        str(custom_temp_path),
    ]

    with patch("sys.argv", argv_custom):
        assert main() == 0

    assert custom_temp_path.exists()
    file_content = json.loads(custom_temp_path.read_text(encoding="utf-8"))
    assert file_content["provider_name"] == "x_internal_api"
    assert len(file_content["candidates"]) == 3

    # Case 3: flag without value => const default path (runtime/outputs/x_candidates.json)
    default_out_path = Path("runtime/outputs/x_candidates.json")
    existed = default_out_path.exists()
    backup_data = None
    if existed:
        backup_data = default_out_path.read_text(encoding="utf-8")
        default_out_path.unlink()

    try:
        argv_no_val = [
            "script",
            "--accounts-file",
            str(temp_config_file),
            "--output-json",
        ]
        with patch("sys.argv", argv_no_val):
            assert main() == 0

        assert default_out_path.exists()
        file_content = json.loads(default_out_path.read_text(encoding="utf-8"))
        assert file_content["provider_name"] == "x_internal_api"
        assert len(file_content["candidates"]) == 3
    finally:
        # Clean up
        if default_out_path.exists():
            try:
                default_out_path.unlink()
            except OSError:
                pass
        if existed and backup_data is not None:
            try:
                default_out_path.parent.mkdir(parents=True, exist_ok=True)
                default_out_path.write_text(backup_data, encoding="utf-8")
            except OSError:
                pass


def test_example_accounts_config_file_valid() -> None:
    config_path = Path("config/accounts.example.yaml")
    assert config_path.exists(), "config/accounts.example.yaml does not exist"

    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert isinstance(data, dict), "Config data is not a dict"
    assert "accounts" in data, "Config data does not have top-level 'accounts' key"
    assert isinstance(data["accounts"], list), "'accounts' is not a list"
    assert len(data["accounts"]) > 0, "'accounts' list is empty"

    first_account = data["accounts"][0]
    assert isinstance(first_account, dict), "First account entry is not a dict"
    assert "handle" in first_account, "First account is missing 'handle'"
    assert "category" in first_account, "First account is missing 'category'"
    assert "weight" in first_account, "First account is missing 'weight'"
