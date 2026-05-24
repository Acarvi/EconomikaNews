from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.build_approved_media_bundle import (
    build_all_bundles,
    build_bundle_for_candidate,
    candidate_bundle_dir,
    default_downloader,
    extract_media_urls,
    infer_media_extension,
    load_approved_payload,
    main,
)


def _write_approved_candidates(path: Path, candidates: list[dict]) -> dict:
    payload = {
        "source_candidates_file": "runtime/outputs/x_candidates.json",
        "db_path": "runtime/economika_news.db",
        "approved_count": len(candidates),
        "candidates": candidates,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


# 1. Tests for load_approved_payload
def test_load_approved_payload_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Approved file not found"):
        load_approved_payload(tmp_path / "missing.json")


def test_load_approved_payload_invalid_json(tmp_path: Path):
    f = tmp_path / "invalid.json"
    f.write_text("{invalid", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_approved_payload(f)


def test_load_approved_payload_not_object(tmp_path: Path):
    f = tmp_path / "invalid.json"
    f.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="top-level must be a JSON object"):
        load_approved_payload(f)


def test_load_approved_payload_missing_candidates(tmp_path: Path):
    f = tmp_path / "invalid.json"
    f.write_text('{"other": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="missing 'candidates' key"):
        load_approved_payload(f)


def test_load_approved_payload_candidates_not_list(tmp_path: Path):
    f = tmp_path / "invalid.json"
    f.write_text('{"candidates": 123}', encoding="utf-8")
    with pytest.raises(ValueError, match="'candidates' must be a list"):
        load_approved_payload(f)


# 2. Tests for candidate_bundle_dir
def test_candidate_bundle_dir(tmp_path: Path):
    assert candidate_bundle_dir(tmp_path, "123") == tmp_path / "123"


# 3. Tests for extract_media_urls
def test_extract_media_urls_shapes():
    candidate = {
        "post_id": "1",
        "url": "https://x.com/alpha/status/123",
        "expanded_url": "https://x.com/alpha/status/456",
        "media_url": "https://example.com/media.png",
        "media": [
            {
                "url": "https://example.com/video.mp4",
                "media_url": "https://example.com/preview.jpg",
                "expanded_url": "https://cdn.example.com/full.webp",
            },
            "https://example.com/item.webp",
        ],
    }
    extracted = extract_media_urls(candidate)
    urls = [x["url"] for x in extracted]
    assert "https://example.com/media.png" in urls
    assert "https://example.com/video.mp4" in urls
    assert "https://example.com/preview.jpg" in urls
    assert "https://cdn.example.com/full.webp" in urls
    assert "https://example.com/item.webp" in urls
    assert "https://x.com/alpha/status/123" not in urls
    assert "https://x.com/alpha/status/456" not in urls


def test_extract_media_urls_filters_unsupported_urls():
    candidate = {
        "post_id": "1",
        "media": [
            "https://t.co/abcde",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "data:image/png;base64,123",
            "/relative/path.jpg",
            "https://x.com/alpha/status/123",
            "https://twitter.com/alpha/statuses/456",
            "https://example.com/direct.jpg",
        ],
    }
    assert [item["url"] for item in extract_media_urls(candidate)] == [
        "https://example.com/direct.jpg"
    ]


# 4. Tests for infer_media_extension
def test_infer_media_extension_priority():
    # content-type wins
    assert infer_media_extension("https://example.com/abc", "image/png") == ".png"
    assert infer_media_extension("https://example.com/abc.jpg", "image/png") == ".png"

    # path suffix
    assert infer_media_extension("https://example.com/abc.webp", None) == ".webp"
    assert infer_media_extension("https://example.com/abc.jpeg", None) == ".jpg"

    # query string ignored
    assert infer_media_extension("https://example.com/media?format=png", None) == ".bin"
    assert infer_media_extension("https://example.com/media.jpg?format=png", None) == ".jpg"

    # fallback
    assert infer_media_extension("https://example.com/abc", None) == ".bin"
    assert infer_media_extension("https://example.com/abc.unknown", None) == ".bin"


def test_infer_media_extension_supported_content_types():
    assert infer_media_extension("https://example.com/asset", "image/jpeg") == ".jpg"
    assert infer_media_extension("https://example.com/asset", "image/png") == ".png"
    assert infer_media_extension("https://example.com/asset", "image/webp") == ".webp"
    assert infer_media_extension("https://example.com/asset", "image/gif") == ".gif"
    assert infer_media_extension("https://example.com/asset", "video/mp4") == ".mp4"
    assert infer_media_extension("https://example.com/asset", "video/webm") == ".webm"
    assert infer_media_extension("https://example.com/asset", "application/octet-stream") == ".bin"


# 5. Test default_downloader mock
@patch("urllib.request.urlopen")
def test_default_downloader(mock_urlopen, tmp_path: Path):
    mock_response = MagicMock()
    mock_response.info.return_value.get_content_type.return_value = "image/jpeg"
    mock_response.read.return_value = b"fake-jpeg-data"
    mock_urlopen.return_value.__enter__.return_value = mock_response

    dest = tmp_path / "test.jpg"
    content_type = default_downloader("https://example.com/img.jpg", dest)
    assert content_type == "image/jpeg"
    assert dest.read_bytes() == b"fake-jpeg-data"


# 6. Tests for build_bundle_for_candidate
def test_build_bundle_for_candidate_invalid_types(tmp_path: Path):
    dummy_downloader = MagicMock()
    res1 = build_bundle_for_candidate("not-a-dict", tmp_path, dummy_downloader)
    assert not res1["success"]
    assert "must be a dictionary object" in res1["errors"][0]

    res2 = build_bundle_for_candidate({}, tmp_path, dummy_downloader)
    assert not res2["success"]
    assert "missing required 'post_id'" in res2["errors"][0]


def test_build_bundle_for_candidate_no_media(tmp_path: Path):
    candidate = {
        "post_id": "no-media-post",
        "account_handle": "alpha",
        "url": "https://x.com/alpha/status/1",
        "media_count": 0,
        "media": [],
    }
    dummy_downloader = MagicMock()
    res = build_bundle_for_candidate(candidate, tmp_path, dummy_downloader)
    assert res["success"]
    assert res["media_downloaded"] == 0

    metadata_file = tmp_path / "no-media-post" / "metadata.json"
    assert metadata_file.exists()
    data = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert data["post_id"] == "no-media-post"
    assert data["account_handle"] == "alpha"
    assert data["url"] == "https://x.com/alpha/status/1"
    assert data["original_candidate"] == candidate
    assert data["local_media"] == []


def test_build_bundle_for_candidate_unsupported_urls(tmp_path: Path):
    candidate = {
        "post_id": "unsupported-urls",
        "media": [
            "file:///etc/passwd",
            "javascript:alert(1)",
            "data:image/png;base64,123",
            "/relative/path.jpg",
            "https://t.co/abcde",
            "https://x.com/alpha/status/123",
            "https://twitter.com/alpha/statuses/456",
        ]
    }
    dummy_downloader = MagicMock()
    res = build_bundle_for_candidate(candidate, tmp_path, dummy_downloader)
    assert res["success"]
    
    metadata_file = tmp_path / "unsupported-urls" / "metadata.json"
    assert metadata_file.exists()
    data = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert len(data["local_media"]) == 7
    for item in data["local_media"]:
        assert item["status"] == "skipped_unsupported_url"
        assert item["local_path"] == ""


def test_build_bundle_for_candidate_success_and_overwrite(tmp_path: Path):
    candidate = {
        "post_id": "happy-post",
        "media": [
            "https://example.com/img1.png",
            "https://example.com/img2.jpg",
        ]
    }
    # Mock downloader
    downloads = []
    def dummy_downloader(url: str, dest_path: Path, timeout: float) -> str:
        downloads.append((url, dest_path))
        if "img1" in url:
            dest_path.write_text("img1-data", encoding="utf-8")
            return "image/png"
        else:
            dest_path.write_text("img2-data", encoding="utf-8")
            return "image/jpeg"

    # First run without overwrite
    res1 = build_bundle_for_candidate(candidate, tmp_path, dummy_downloader, overwrite=False)
    assert res1["success"]
    assert res1["media_downloaded"] == 2
    assert (tmp_path / "happy-post" / "media_1.png").exists()
    assert (tmp_path / "happy-post" / "media_2.jpg").exists()

    # Second run without overwrite (skips all)
    downloads.clear()
    res2 = build_bundle_for_candidate(candidate, tmp_path, dummy_downloader, overwrite=False)
    assert res2["success"]
    assert res2["media_downloaded"] == 0
    assert res2["media_skipped"] == 2

    # Third run WITH overwrite (downloads again atomically)
    downloads.clear()
    res3 = build_bundle_for_candidate(candidate, tmp_path, dummy_downloader, overwrite=True)
    assert res3["success"]
    assert res3["media_downloaded"] == 2
    assert res3["media_skipped"] == 0
    assert (tmp_path / "happy-post" / "media_1.png").read_text(encoding="utf-8") == "img1-data"


def test_build_bundle_for_candidate_overwrite_replaces_existing_media(tmp_path: Path):
    candidate = {
        "post_id": "replace-post",
        "media": ["https://example.com/img.png"],
    }
    post_dir = tmp_path / "replace-post"
    post_dir.mkdir()
    existing = post_dir / "media_1.png"
    existing.write_text("old", encoding="utf-8")

    def dummy_downloader(url: str, dest_path: Path, timeout: float) -> str:
        dest_path.write_text("new", encoding="utf-8")
        return "image/png"

    res = build_bundle_for_candidate(candidate, tmp_path, dummy_downloader, overwrite=True)
    assert res["success"]
    assert res["media_downloaded"] == 1
    assert existing.read_text(encoding="utf-8") == "new"


def test_build_bundle_for_candidate_dry_run(tmp_path: Path):
    candidate = {
        "post_id": "dry-post",
        "media": ["https://example.com/img.png"]
    }
    dummy_downloader = MagicMock()
    res = build_bundle_for_candidate(candidate, tmp_path, dummy_downloader, dry_run=True)
    assert res["success"]
    assert res["media_downloaded"] == 0
    dummy_downloader.assert_not_called()
    assert not (tmp_path / "dry-post").exists()


def test_build_bundle_for_candidate_download_error(tmp_path: Path):
    candidate = {
        "post_id": "error-post",
        "media": [
            "https://example.com/fail.png",
            "https://example.com/ok.jpg"
        ]
    }
    def faulty_downloader(url: str, dest_path: Path, timeout: float) -> str:
        if "fail" in url:
            raise ConnectionError("Connection reset")
        dest_path.write_text("ok", encoding="utf-8")
        return "image/jpeg"

    res = build_bundle_for_candidate(candidate, tmp_path, faulty_downloader)
    # The candidate is bundled, but has failures
    assert not res["success"]
    assert res["media_failed"] == 1
    assert res["media_downloaded"] == 1
    assert "Failed to download media_1" in res["errors"][0]

    metadata_file = tmp_path / "error-post" / "metadata.json"
    assert metadata_file.exists()
    data = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert data["local_media"][0]["status"] == "failed"
    assert "Connection reset" in data["local_media"][0]["error"]
    assert data["local_media"][1]["status"] == "downloaded"
    assert len(data["bundle_errors"]) == 1


# 7. Test atomic metadata write behavior
def test_metadata_atomic_write_behavior(tmp_path: Path):
    candidate = {
        "post_id": "atomic-post",
        "media": []
    }
    # We patch os.replace to check that it is called with .tmp and final path
    with patch("os.replace", wraps=os.replace) as mock_replace:
        res = build_bundle_for_candidate(candidate, tmp_path, MagicMock())
        assert res["success"]
        assert mock_replace.called
        # Verify that the first argument ends with metadata.json.tmp and the second with metadata.json
        args = mock_replace.call_args[0]
        assert args[0].endswith("metadata.json.tmp")
        assert args[1].endswith("metadata.json")


def test_media_write_uses_tmp_and_atomic_replace(tmp_path: Path):
    candidate = {
        "post_id": "atomic-media",
        "media": ["https://example.com/media.jpg"],
    }

    def dummy_downloader(url: str, dest_path: Path, timeout: float) -> str:
        assert dest_path.name == "media_1.tmp"
        dest_path.write_text("media", encoding="utf-8")
        return "image/jpeg"

    with patch("os.replace", wraps=os.replace) as mock_replace:
        res = build_bundle_for_candidate(candidate, tmp_path, dummy_downloader)

    assert res["success"]
    replace_calls = [call.args for call in mock_replace.call_args_list]
    assert any(args[0].endswith("media_1.tmp") and args[1].endswith("media_1.jpg") for args in replace_calls)


# 8. CLI integration tests via main()
def test_cli_success(tmp_path: Path):
    approved_file = tmp_path / "approved.json"
    output_dir = tmp_path / "approved"
    
    candidates = [
        {
            "post_id": "cli-post-1",
            "account_handle": "cli",
            "url": "https://x.com/cli/status/1",
            "media": ["https://example.com/1.png"]
        },
        {
            "post_id": "cli-post-2",
            "media": []
        }
    ]
    _write_approved_candidates(approved_file, candidates)

    def dummy_downloader(url, dest, timeout):
        dest.write_text("data")
        return "image/png"

    # Patch default_downloader so it uses our dummy
    with patch("scripts.build_approved_media_bundle.default_downloader", dummy_downloader):
        args = [
            "build_approved_media_bundle.py",
            "--approved-file", str(approved_file),
            "--output-dir", str(output_dir),
        ]
        with patch("sys.argv", args):
            assert main() == 0

    assert (output_dir / "cli-post-1" / "metadata.json").exists()
    assert (output_dir / "cli-post-1" / "media_1.png").exists()
    assert (output_dir / "cli-post-2" / "metadata.json").exists()


def test_empty_approved_list_summary_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    approved_file = tmp_path / "approved.json"
    output_dir = tmp_path / "approved"
    _write_approved_candidates(approved_file, [])

    args = [
        "build_approved_media_bundle.py",
        "--approved-file", str(approved_file),
        "--output-dir", str(output_dir),
    ]
    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["approved_count"] == 0
    assert summary["bundled_count"] == 0
    assert summary["media_downloaded"] == 0
    assert summary["media_skipped"] == 0
    assert summary["media_failed"] == 0
    assert summary["errors"] == []
    assert not output_dir.exists()


def test_cli_invalid_candidates_ignored(tmp_path: Path):
    approved_file = tmp_path / "approved.json"
    output_dir = tmp_path / "approved"
    
    candidates = [
        # missing post_id
        {
            "account_handle": "no-id"
        },
        # valid candidate
        {
            "post_id": "valid-id",
            "media": []
        }
    ]
    _write_approved_candidates(approved_file, candidates)

    args = [
        "build_approved_media_bundle.py",
        "--approved-file", str(approved_file),
        "--output-dir", str(output_dir),
    ]
    with patch("sys.argv", args):
        assert main() == 0

    # valid candidate folder is created, invalid is skipped
    assert (output_dir / "valid-id" / "metadata.json").exists()
    assert not (output_dir / "no-id").exists()


def test_cli_missing_file_exits_1(tmp_path: Path):
    args = [
        "build_approved_media_bundle.py",
        "--approved-file", str(tmp_path / "missing.json"),
    ]
    with patch("sys.argv", args):
        assert main() == 1


def test_cli_invalid_json_exits_1(tmp_path: Path):
    approved_file = tmp_path / "approved.json"
    approved_file.write_text("{invalid", encoding="utf-8")
    
    args = [
        "build_approved_media_bundle.py",
        "--approved-file", str(approved_file),
    ]
    with patch("sys.argv", args):
        assert main() == 1


@pytest.mark.parametrize("content", ["[]", '{"other": 1}', '{"candidates": 123}'])
def test_cli_invalid_top_level_exits_1(tmp_path: Path, content: str):
    approved_file = tmp_path / "approved.json"
    approved_file.write_text(content, encoding="utf-8")

    args = [
        "build_approved_media_bundle.py",
        "--approved-file", str(approved_file),
    ]
    with patch("sys.argv", args):
        assert main() == 1


def test_cli_download_error_exits_0(tmp_path: Path):
    approved_file = tmp_path / "approved.json"
    output_dir = tmp_path / "approved"
    
    candidates = [
        {
            "post_id": "fail-post",
            "media": ["https://example.com/fail.png"]
        }
    ]
    _write_approved_candidates(approved_file, candidates)

    def faulty_downloader(url, dest, timeout):
        raise ConnectionError("Failed")

    with patch("scripts.build_approved_media_bundle.default_downloader", faulty_downloader):
        args = [
            "build_approved_media_bundle.py",
            "--approved-file", str(approved_file),
            "--output-dir", str(output_dir),
        ]
        with patch("sys.argv", args):
            assert main() == 0

    # folder exists but has download failures recorded
    assert (output_dir / "fail-post" / "metadata.json").exists()
    metadata = json.loads((output_dir / "fail-post" / "metadata.json").read_text(encoding="utf-8"))
    assert len(metadata["bundle_errors"]) == 1


def test_build_all_bundles_invalid_candidate_skipped_with_error(tmp_path: Path):
    summary = build_all_bundles(
        payload={"candidates": [{"account_handle": "missing"}, {"post_id": "valid", "media": []}]},
        output_dir=tmp_path,
        downloader=MagicMock(),
    )
    assert summary["approved_count"] == 2
    assert summary["bundled_count"] == 1
    assert summary["errors"] == ["Candidate at index 0 is missing required 'post_id'"]
    assert (tmp_path / "valid" / "metadata.json").exists()
