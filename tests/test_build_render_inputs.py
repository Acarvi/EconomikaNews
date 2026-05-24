from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.build_render_inputs import (
    build_render_input,
    build_render_inputs,
    load_bundle_index,
    main,
    write_render_input_atomically,
)


def _bundle(**overrides) -> dict:
    payload = {
        "post_id": "post-1",
        "account_handle": "economika",
        "url": "https://x.com/economika/status/1",
        "text_prefix": "  Markets rally after a central bank signal  ",
        "score": 123,
        "metrics": {"likes": 10, "reposts": 2},
        "review_status": "approved",
        "reviewed_at": "2026-05-24T10:00:00Z",
        "review_note": None,
        "metadata_path": "runtime/approved/post-1/metadata.json",
        "bundle_dir": "runtime/approved/post-1",
        "has_media": True,
        "media_files": [
            {
                "index": 1,
                "filename": "media_1.jpg",
                "local_path": "runtime/approved/post-1/media_1.jpg",
                "content_type": "image/jpeg",
                "source_url": "https://example.com/media_1.jpg",
            }
        ],
        "bundle_errors": [],
        "ready_for_render": True,
    }
    payload.update(overrides)
    return payload


def _write_index(path: Path, bundles: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"bundles": bundles}, indent=2), encoding="utf-8")


def test_load_bundle_index_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Bundle index file not found"):
        load_bundle_index(tmp_path / "missing.json")


def test_cli_missing_index_file_returns_exit_code_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    args = ["build_render_inputs.py", "--index-file", str(tmp_path / "missing.json")]

    with patch("sys.argv", args):
        assert main() == 1

    assert "Bundle index file not found" in capsys.readouterr().err


def test_load_bundle_index_invalid_json(tmp_path: Path):
    index_file = tmp_path / "index.json"
    index_file.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON"):
        load_bundle_index(index_file)


def test_cli_invalid_json_returns_exit_code_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    index_file = tmp_path / "index.json"
    index_file.write_text("{invalid", encoding="utf-8")

    args = ["build_render_inputs.py", "--index-file", str(index_file)]
    with patch("sys.argv", args):
        assert main() == 1

    assert "Invalid JSON" in capsys.readouterr().err


@pytest.mark.parametrize("content", ["[]", '{"other": 1}', '{"bundles": 123}'])
def test_invalid_top_level_bundle_index(tmp_path: Path, content: str):
    index_file = tmp_path / "index.json"
    index_file.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError):
        load_bundle_index(index_file)

    args = ["build_render_inputs.py", "--index-file", str(index_file)]
    with patch("sys.argv", args):
        assert main() == 1


def test_empty_bundles_list_summary_zero(tmp_path: Path):
    summary = build_render_inputs({"bundles": []}, tmp_path / "render_inputs")

    assert summary["inputs_written"] == 0
    assert summary["inputs_skipped"] == 0
    assert summary["bundles_seen"] == 0
    assert summary["bundles_included"] == 0
    assert summary["errors"] == []
    assert not (tmp_path / "render_inputs").exists()


def test_ready_bundle_writes_render_input(tmp_path: Path):
    index_file = tmp_path / "approved" / "index.json"
    output_dir = tmp_path / "render_inputs"
    _write_index(index_file, [_bundle()])

    args = ["build_render_inputs.py", "--index-file", str(index_file), "--output-dir", str(output_dir)]
    with patch("sys.argv", args):
        assert main() == 0

    output_file = output_dir / "post-1.json"
    assert output_file.exists()
    render_input = json.loads(output_file.read_text(encoding="utf-8"))
    assert render_input["schema_version"] == 1
    assert render_input["post_id"] == "post-1"
    assert render_input["source"] == "x"
    assert render_input["render"]["ready"] is True
    assert render_input["render"]["target_formats"] == ["vertical_short"]
    assert render_input["render"]["template"] == "default_news_card"
    assert render_input["render"]["language"] == "en"
    assert render_input["render"]["notes"] == []


def test_not_ready_bundle_skipped_by_default(tmp_path: Path):
    summary = build_render_inputs(
        {"bundles": [_bundle(ready_for_render=False, bundle_errors=["media failed"])]},
        tmp_path / "render_inputs",
    )

    assert summary["inputs_written"] == 0
    assert summary["inputs_skipped"] == 1
    assert summary["bundles_included"] == 0
    assert not (tmp_path / "render_inputs").exists()


def test_include_not_ready_writes_not_ready_input_with_notes(tmp_path: Path):
    output_dir = tmp_path / "render_inputs"
    summary = build_render_inputs(
        {"bundles": [_bundle(ready_for_render=False, bundle_errors=["media failed"])]},
        output_dir,
        include_not_ready=True,
    )

    assert summary["inputs_written"] == 1
    assert summary["bundles_included"] == 1
    render_input = json.loads((output_dir / "post-1.json").read_text(encoding="utf-8"))
    assert render_input["render"]["ready"] is False
    assert "Bundle index ready_for_render is false" in render_input["render"]["notes"]
    assert "Bundle has recorded errors" in render_input["render"]["notes"]


def test_existing_output_skipped_when_overwrite_false(tmp_path: Path):
    output_dir = tmp_path / "render_inputs"
    output_dir.mkdir()
    output_file = output_dir / "post-1.json"
    output_file.write_text('{"old": true}', encoding="utf-8")

    summary = build_render_inputs({"bundles": [_bundle()]}, output_dir, overwrite=False)

    assert summary["inputs_written"] == 0
    assert summary["inputs_skipped"] == 1
    assert summary["skipped_existing"] == 1
    assert json.loads(output_file.read_text(encoding="utf-8")) == {"old": True}


def test_overwrite_true_rewrites_file(tmp_path: Path):
    output_dir = tmp_path / "render_inputs"
    output_dir.mkdir()
    output_file = output_dir / "post-1.json"
    output_file.write_text('{"old": true}', encoding="utf-8")

    summary = build_render_inputs({"bundles": [_bundle(text_prefix="Fresh headline")]}, output_dir, overwrite=True)

    assert summary["inputs_written"] == 1
    render_input = json.loads(output_file.read_text(encoding="utf-8"))
    assert render_input["text"]["headline"] == "Fresh headline"
    assert "old" not in render_input


def test_dry_run_creates_no_directories_or_files(tmp_path: Path):
    output_dir = tmp_path / "render_inputs"

    summary = build_render_inputs({"bundles": [_bundle()]}, output_dir, dry_run=True)

    assert summary["inputs_written"] == 0
    assert summary["bundles_included"] == 1
    assert summary["dry_run"] is True
    assert not output_dir.exists()


def test_invalid_individual_bundle_without_post_id_skipped_with_error(tmp_path: Path):
    summary = build_render_inputs({"bundles": [_bundle(post_id=""), _bundle(post_id="valid")]}, tmp_path / "out")

    assert summary["inputs_written"] == 1
    assert summary["inputs_skipped"] == 1
    assert "missing required 'post_id'" in summary["errors"][0]
    assert (tmp_path / "out" / "valid.json").exists()


def test_deterministic_headline_from_text_prefix():
    text = "  " + ("a" * 120) + "  "

    render_input = build_render_input(_bundle(text_prefix=text))

    assert render_input["text"]["headline"] == "a" * 100
    assert render_input["text"]["body"] == text
    assert render_input["text"]["source_text_prefix"] == text


def test_fallback_headline_untitled():
    assert build_render_input(_bundle(text_prefix="  "))["text"]["headline"] == "Untitled"
    assert build_render_input(_bundle(text_prefix=None))["text"]["headline"] == "Untitled"


def test_media_files_copied_from_bundle_index():
    render_input = build_render_input(_bundle())

    assert render_input["media"]["has_media"] is True
    assert render_input["media"]["files"] == _bundle()["media_files"]


def test_atomic_write_uses_tmp_replace(tmp_path: Path):
    output_file = tmp_path / "render_inputs" / "post-1.json"

    with patch("os.replace", wraps=os.replace) as mock_replace:
        write_render_input_atomically(build_render_input(_bundle()), output_file)

    assert output_file.exists()
    args = mock_replace.call_args[0]
    assert args[0].endswith("post-1.json.tmp")
    assert args[1].endswith("post-1.json")
