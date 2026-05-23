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
def runtime_config_file(tmp_path: Path, temp_config_file: Path) -> Path:
    path = tmp_path / "x_internal.local.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "x_internal": {
                    "headers_file": "runtime/secrets/x_headers.json",
                    "timeline_template_url": "timeline-template",
                    "user_lookup_template_url": "lookup-template",
                    "user_id": None,
                },
                "paths": {
                    "accounts_file": str(temp_config_file),
                    "db_path": str(tmp_path / "configured.db"),
                    "output_json": str(tmp_path / "configured_candidates.json"),
                },
            }
        ),
        encoding="utf-8",
    )
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

    argv = ["script", "--accounts-file", str(temp_config_file), "--no-cache"]
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

    argv = ["script", "--accounts-file", str(temp_config_file), "--include-media", "--no-cache"]
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
    argv_omitted = ["script", "--accounts-file", str(temp_config_file), "--no-cache"]
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
        "--no-cache",
    ]

    with patch("sys.argv", argv_custom):
        assert main() == 0

    assert custom_temp_path.exists()
    file_content = json.loads(custom_temp_path.read_text(encoding="utf-8"))
    assert file_content["provider_name"] == "x_internal_api"
    assert len(file_content["candidates"]) == 3

    # Case 3: flag without value => module default path. Patch it to tmp_path so
    # the test never writes real runtime output.
    default_out_path = tmp_path / "default_candidates.json"
    with patch("scripts.x_fetch_accounts_probe.DEFAULT_OUTPUT_JSON_PATH", str(default_out_path)):
        argv_no_val = [
            "script",
            "--accounts-file",
            str(temp_config_file),
            "--output-json",
            "--no-cache",
        ]
        with patch("sys.argv", argv_no_val):
            assert main() == 0

    assert default_out_path.exists()
    file_content = json.loads(default_out_path.read_text(encoding="utf-8"))
    assert file_content["provider_name"] == "x_internal_api"
    assert len(file_content["candidates"]) == 3


@patch("scripts.x_fetch_accounts_probe.XInternalApiProvider")
def test_fetch_accounts_uses_config_paths(
    mock_provider_cls: MagicMock,
    runtime_config_file: Path,
    mock_posts: dict[str, list[SourcePost]],
    tmp_path: Path,
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

    with patch("sys.argv", ["script", "--config", str(runtime_config_file)]):
        assert main() == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["account_count"] == 2
    assert payload["db_path"] == str(tmp_path / "configured.db")


@patch("scripts.x_fetch_accounts_probe.XInternalApiProvider")
def test_fetch_accounts_env_db_path_wins_over_config(
    mock_provider_cls: MagicMock,
    runtime_config_file: Path,
    mock_posts: dict[str, list[SourcePost]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    env_db_path = tmp_path / "env.db"
    monkeypatch.setenv("ECONOMIKA_DB_PATH", str(env_db_path))

    with patch("sys.argv", ["script", "--config", str(runtime_config_file)]):
        assert main() == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["db_path"] == str(env_db_path)


@patch("scripts.x_fetch_accounts_probe.XInternalApiProvider")
def test_fetch_accounts_uses_config_output_json_when_flag_has_no_value(
    mock_provider_cls: MagicMock,
    runtime_config_file: Path,
    mock_posts: dict[str, list[SourcePost]],
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

    with patch("sys.argv", ["script", "--config", str(runtime_config_file), "--output-json"]):
        assert main() == 0

    config_data = yaml.safe_load(runtime_config_file.read_text(encoding="utf-8"))
    output_path = Path(config_data["paths"]["output_json"])
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["provider_name"] == "x_internal_api"


@patch("scripts.x_fetch_accounts_probe.XInternalApiProvider")
def test_fetch_accounts_still_works_without_config(
    mock_provider_cls: MagicMock,
    temp_config_file: Path,
    mock_posts: dict[str, list[SourcePost]],
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

    argv = ["script", "--accounts-file", str(temp_config_file), "--no-cache"]
    with patch("sys.argv", argv):
        assert main() == 0


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


@patch("scripts.x_fetch_accounts_probe.XInternalApiProvider")
def test_fetch_accounts_seen_posts_cache_behavior(
    mock_provider_cls: MagicMock,
    temp_config_file: Path,
    mock_posts: dict[str, list[SourcePost]],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Setup mock provider
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

    db_file = tmp_path / "economika_news.db"
    assert not db_file.exists()

    # 1. First run: cache active, db_file gets created and populated. All candidates are new.
    argv1 = [
        "script",
        "--accounts-file",
        str(temp_config_file),
        "--db-path",
        str(db_file),
    ]
    with patch("sys.argv", argv1):
        assert main() == 0

    assert db_file.exists()

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    
    assert payload["cache_enabled"] is True
    assert payload["db_path"] == str(db_file)
    assert payload["new_candidates"] == 3
    assert payload["already_seen_candidates"] == 0

    for c in payload["candidates"]:
        assert c["is_new"] is True

    # 2. Second run: same candidates. All should be recognized as already seen (is_new = False).
    argv2 = [
        "script",
        "--accounts-file",
        str(temp_config_file),
        "--db-path",
        str(db_file),
    ]
    with patch("sys.argv", argv2):
        assert main() == 0

    captured = capsys.readouterr()
    payload2 = json.loads(captured.out)

    assert payload2["cache_enabled"] is True
    assert payload2["new_candidates"] == 0
    assert payload2["already_seen_candidates"] == 3

    for c in payload2["candidates"]:
        assert c["is_new"] is False

    # 3. Third run: with --only-new, candidates list is filtered to empty since all are seen.
    argv3 = [
        "script",
        "--accounts-file",
        str(temp_config_file),
        "--db-path",
        str(db_file),
        "--only-new",
    ]
    with patch("sys.argv", argv3):
        assert main() == 0

    captured = capsys.readouterr()
    payload3 = json.loads(captured.out)

    assert payload3["cache_enabled"] is True
    assert payload3["new_candidates"] == 0
    assert payload3["already_seen_candidates"] == 3
    assert len(payload3["candidates"]) == 0
    assert payload3["unique_posts"] == 0

    # 4. Fourth run: with --no-cache, does not touch DB, is_new is omitted, cache fields are null.
    db_file_no_cache = tmp_path / "economika_news_no_cache.db"
    assert not db_file_no_cache.exists()
    argv4 = [
        "script",
        "--accounts-file",
        str(temp_config_file),
        "--db-path",
        str(db_file_no_cache),
        "--no-cache",
    ]
    with patch("sys.argv", argv4):
        assert main() == 0

    assert not db_file_no_cache.exists()

    captured = capsys.readouterr()
    payload4 = json.loads(captured.out)

    assert payload4["cache_enabled"] is False
    assert payload4["db_path"] is None
    assert payload4["new_candidates"] is None
    assert payload4["already_seen_candidates"] is None
    for c in payload4["candidates"]:
        assert "is_new" not in c

    # 5. Invalid flags combination: --no-cache and --only-new together exits with 1.
    argv5 = [
        "script",
        "--accounts-file",
        str(temp_config_file),
        "--no-cache",
        "--only-new",
    ]
    with patch("sys.argv", argv5):
        assert main() == 1

    captured = capsys.readouterr()
    assert "--only-new requires cache enabled" in captured.err
