from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from scripts.build_render_manifest import (
    build_render_manifest,
    collect_manifest_errors,
    main,
    write_manifest_atomically,
)


def _render_input(**overrides) -> dict:
    payload = {
        "schema_version": 1,
        "post_id": "post-1",
        "account_handle": "economika",
        "url": "https://x.com/economika/status/1",
        "render": {
            "ready": True,
            "target_formats": ["vertical_short"],
            "template": "default_news_card",
        },
    }
    payload.update(overrides)
    return payload


def _write_json(path: Path, payload: dict | list | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")


def _write_png(path: Path, size: tuple[int, int] = (320, 480)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color="#111827").save(path, format="PNG")


def test_missing_renders_dir_creates_empty_manifest_and_cli_exits_zero(tmp_path: Path, capsys):
    output_json = tmp_path / "renders" / "manifest.json"
    args = [
        "build_render_manifest.py",
        "--renders-dir",
        str(tmp_path / "missing"),
        "--render-inputs-dir",
        str(tmp_path / "render_inputs"),
        "--output-json",
        str(output_json),
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    manifest = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["render_count"] == 0
    assert summary["invalid_render_count"] == 0
    assert manifest["renders"] == []


def test_empty_renders_dir_creates_empty_manifest(tmp_path: Path):
    renders_dir = tmp_path / "renders"
    renders_dir.mkdir()

    manifest = build_render_manifest(renders_dir, tmp_path / "render_inputs")

    assert manifest["render_count"] == 0
    assert manifest["invalid_render_count"] == 0
    assert manifest["renders"] == []


def test_valid_card_and_matching_render_input_creates_manifest_entry(tmp_path: Path):
    _write_png(tmp_path / "renders" / "post-1" / "card.png", size=(1080, 1920))
    _write_json(tmp_path / "render_inputs" / "post-1.json", _render_input())

    manifest = build_render_manifest(tmp_path / "renders", tmp_path / "render_inputs")

    assert manifest["render_count"] == 1
    render = manifest["renders"][0]
    assert render["post_id"] == "post-1"
    assert render["card_path"].endswith("renders/post-1/card.png")
    assert render["render_input_path"].endswith("render_inputs/post-1.json")
    assert render["width"] == 1080
    assert render["height"] == 1920
    assert render["file_size_bytes"] > 0
    assert render["account_handle"] == "economika"
    assert render["url"] == "https://x.com/economika/status/1"
    assert render["template"] == "default_news_card"
    assert render["target_formats"] == ["vertical_short"]
    assert render["ready_for_publish"] is True
    assert render["render_errors"] == []


def test_missing_card_counted_invalid(tmp_path: Path):
    (tmp_path / "renders" / "post-1").mkdir(parents=True)

    manifest = build_render_manifest(tmp_path / "renders", tmp_path / "render_inputs", include_invalid=True)

    assert manifest["render_count"] == 0
    assert manifest["invalid_render_count"] == 1
    assert manifest["invalid_renders"][0]["error"] == "card.png missing"


def test_unreadable_card_counted_invalid(tmp_path: Path):
    card = tmp_path / "renders" / "post-1" / "card.png"
    card.parent.mkdir(parents=True)
    card.write_text("not a png", encoding="utf-8")

    manifest = build_render_manifest(tmp_path / "renders", tmp_path / "render_inputs", include_invalid=True)

    assert manifest["render_count"] == 0
    assert manifest["invalid_render_count"] == 1
    assert "Unreadable PNG" in manifest["invalid_renders"][0]["error"]


def test_missing_render_input_keeps_render_not_ready(tmp_path: Path):
    _write_png(tmp_path / "renders" / "post-1" / "card.png")

    manifest = build_render_manifest(tmp_path / "renders", tmp_path / "render_inputs")

    render = manifest["renders"][0]
    assert render["ready_for_publish"] is False
    assert render["render_errors"] == ["Render input missing"]


def test_render_input_post_id_mismatch_keeps_render_not_ready(tmp_path: Path):
    _write_png(tmp_path / "renders" / "post-1" / "card.png")
    _write_json(tmp_path / "render_inputs" / "post-1.json", _render_input(post_id="other"))

    manifest = build_render_manifest(tmp_path / "renders", tmp_path / "render_inputs")

    render = manifest["renders"][0]
    assert render["ready_for_publish"] is False
    assert "Render input post_id mismatch" in render["render_errors"][0]


def test_render_ready_false_keeps_render_not_ready(tmp_path: Path):
    _write_png(tmp_path / "renders" / "post-1" / "card.png")
    _write_json(tmp_path / "render_inputs" / "post-1.json", _render_input(render={"ready": False}))

    manifest = build_render_manifest(tmp_path / "renders", tmp_path / "render_inputs")

    render = manifest["renders"][0]
    assert render["ready_for_publish"] is False
    assert "Render input render.ready is not true" in render["render_errors"]


def test_dimensions_and_file_size_captured(tmp_path: Path):
    _write_png(tmp_path / "renders" / "post-1" / "card.png", size=(640, 360))
    _write_json(tmp_path / "render_inputs" / "post-1.json", _render_input())

    render = build_render_manifest(tmp_path / "renders", tmp_path / "render_inputs")["renders"][0]

    assert render["width"] == 640
    assert render["height"] == 360
    assert render["file_size_bytes"] == (tmp_path / "renders" / "post-1" / "card.png").stat().st_size


def test_renders_sorted_by_created_at_desc_then_post_id_asc(tmp_path: Path):
    for post_id in ("post-b", "post-a", "post-old"):
        _write_png(tmp_path / "renders" / post_id / "card.png")
        _write_json(tmp_path / "render_inputs" / f"{post_id}.json", _render_input(post_id=post_id))

    old_time = 1_700_000_000
    new_time = 1_800_000_000
    os.utime(tmp_path / "renders" / "post-old" / "card.png", (old_time, old_time))
    os.utime(tmp_path / "renders" / "post-a" / "card.png", (new_time, new_time))
    os.utime(tmp_path / "renders" / "post-b" / "card.png", (new_time, new_time))

    manifest = build_render_manifest(tmp_path / "renders", tmp_path / "render_inputs")

    assert [render["post_id"] for render in manifest["renders"]] == [
        "post-a",
        "post-b",
        "post-old",
    ]


def test_direct_files_inside_renders_dir_ignored(tmp_path: Path):
    renders_dir = tmp_path / "renders"
    renders_dir.mkdir()
    (renders_dir / "notes.txt").write_text("ignore", encoding="utf-8")
    (renders_dir / "manifest.json").write_text("{}", encoding="utf-8")

    manifest = build_render_manifest(renders_dir, tmp_path / "render_inputs", include_invalid=True)

    assert manifest["render_count"] == 0
    assert manifest["invalid_render_count"] == 0


def test_include_invalid_controls_invalid_render_details(tmp_path: Path):
    (tmp_path / "renders" / "post-1").mkdir(parents=True)

    hidden = build_render_manifest(tmp_path / "renders", tmp_path / "render_inputs", include_invalid=False)
    detailed = build_render_manifest(tmp_path / "renders", tmp_path / "render_inputs", include_invalid=True)

    assert hidden["invalid_render_count"] == 1
    assert hidden["invalid_renders"] == []
    assert detailed["invalid_renders"][0]["render_dir"].endswith("renders/post-1")


def test_collect_manifest_errors_includes_invalid_and_render_errors(tmp_path: Path):
    (tmp_path / "renders" / "missing-card").mkdir(parents=True)
    _write_png(tmp_path / "renders" / "missing-input" / "card.png")

    manifest = build_render_manifest(tmp_path / "renders", tmp_path / "render_inputs", include_invalid=True)

    errors = collect_manifest_errors(manifest)
    assert any(error.endswith("missing-card: card.png missing") for error in errors)
    assert "missing-input: Render input missing" in errors


def test_atomic_write_uses_tmp_replace(tmp_path: Path):
    output_json = tmp_path / "renders" / "manifest.json"

    with patch("os.replace", wraps=os.replace) as mock_replace:
        write_manifest_atomically({"renders": []}, output_json)

    assert output_json.exists()
    args = mock_replace.call_args[0]
    assert args[0].endswith("manifest.json.tmp")
    assert args[1].endswith("manifest.json")


def test_cli_summary_printed(tmp_path: Path, capsys):
    _write_png(tmp_path / "renders" / "post-1" / "card.png")
    _write_json(tmp_path / "render_inputs" / "post-1.json", _render_input())
    args = [
        "build_render_manifest.py",
        "--renders-dir",
        str(tmp_path / "renders"),
        "--render-inputs-dir",
        str(tmp_path / "render_inputs"),
        "--output-json",
        str(tmp_path / "renders" / "manifest.json"),
        "--pretty",
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["render_count"] == 1
    assert summary["invalid_render_count"] == 0
    assert summary["errors"] == []


def test_cli_summary_includes_invalid_render_errors_when_excluded_from_manifest(tmp_path: Path, capsys):
    (tmp_path / "renders" / "post-1").mkdir(parents=True)
    output_json = tmp_path / "renders" / "manifest.json"
    args = [
        "build_render_manifest.py",
        "--renders-dir",
        str(tmp_path / "renders"),
        "--render-inputs-dir",
        str(tmp_path / "render_inputs"),
        "--output-json",
        str(output_json),
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    manifest = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["errors"][0].endswith("post-1: card.png missing")
    assert manifest["invalid_render_count"] == 1
    assert manifest["invalid_renders"] == []


def test_cli_summary_includes_render_errors_when_render_input_missing(tmp_path: Path, capsys):
    _write_png(tmp_path / "renders" / "post-1" / "card.png")
    output_json = tmp_path / "renders" / "manifest.json"
    args = [
        "build_render_manifest.py",
        "--renders-dir",
        str(tmp_path / "renders"),
        "--render-inputs-dir",
        str(tmp_path / "render_inputs"),
        "--output-json",
        str(output_json),
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    manifest = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["errors"] == ["post-1: Render input missing"]
    assert manifest["renders"][0]["ready_for_publish"] is False
    assert manifest["renders"][0]["render_errors"] == ["Render input missing"]


def test_cli_include_invalid_true_writes_invalid_details(tmp_path: Path, capsys):
    (tmp_path / "renders" / "post-1").mkdir(parents=True)
    output_json = tmp_path / "renders" / "manifest.json"
    args = [
        "build_render_manifest.py",
        "--renders-dir",
        str(tmp_path / "renders"),
        "--output-json",
        str(output_json),
        "--include-invalid",
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    manifest = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["errors"][0].endswith("post-1: card.png missing")
    assert manifest["invalid_renders"][0]["error"] == "card.png missing"


def test_cli_write_failure_returns_exit_code_1(tmp_path: Path, capsys):
    args = [
        "build_render_manifest.py",
        "--renders-dir",
        str(tmp_path / "missing"),
        "--output-json",
        str(tmp_path / "renders" / "manifest.json"),
    ]

    with (
        patch("sys.argv", args),
        patch("scripts.build_render_manifest.write_manifest_atomically", side_effect=OSError("disk full")),
    ):
        assert main() == 1

    assert "failed to write manifest" in capsys.readouterr().err
