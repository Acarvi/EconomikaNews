from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from scripts.render_text_cards import (
    iter_render_input_files,
    main,
    render_all_cards,
    render_card,
    write_card_atomically,
    build_card_image,
)


def _render_input(**overrides) -> dict:
    payload = {
        "schema_version": 1,
        "post_id": "post-1",
        "source": "x",
        "account_handle": "economika",
        "url": "https://x.com/economika/status/1",
        "text": {
            "headline": "Markets rally after a central bank signal",
            "body": "Markets rally after a central bank signal with more context for the card body.",
        },
        "engagement": {
            "score": 123.0,
            "metrics": {"views": 1000, "likes": 10, "reposts": 2, "replies": 1},
        },
        "media": {"has_media": False, "files": []},
        "render": {"ready": True},
    }
    payload.update(overrides)
    return payload


def _write_render_input(path: Path, payload: dict | list | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")


def test_missing_input_dir_exits_zero_summary(tmp_path: Path):
    summary = render_all_cards(tmp_path / "missing", tmp_path / "renders")

    assert summary["inputs_seen"] == 0
    assert summary["cards_rendered"] == 0
    assert summary["cards_skipped"] == 0
    assert summary["errors"] == []
    assert not (tmp_path / "renders").exists()


def test_empty_input_dir_zero_summary(tmp_path: Path):
    input_dir = tmp_path / "render_inputs"
    input_dir.mkdir()

    summary = render_all_cards(input_dir, tmp_path / "renders")

    assert summary["inputs_seen"] == 0
    assert summary["cards_rendered"] == 0
    assert summary["errors"] == []


def test_iter_render_input_files_ignores_non_json(tmp_path: Path):
    _write_render_input(tmp_path / "render_inputs" / "a.json", _render_input(post_id="a"))
    (tmp_path / "render_inputs" / "notes.txt").write_text("skip", encoding="utf-8")

    files = iter_render_input_files(tmp_path / "render_inputs")

    assert [path.name for path in files] == ["a.json"]


def test_invalid_json_recorded_and_does_not_crash(tmp_path: Path):
    _write_render_input(tmp_path / "render_inputs" / "bad.json", "{invalid")

    summary = render_all_cards(tmp_path / "render_inputs", tmp_path / "renders")

    assert summary["cards_rendered"] == 0
    assert summary["cards_skipped"] == 1
    assert "Invalid JSON" in summary["errors"][0]


def test_top_level_not_object_skipped(tmp_path: Path):
    _write_render_input(tmp_path / "render_inputs" / "bad.json", [])

    summary = render_all_cards(tmp_path / "render_inputs", tmp_path / "renders")

    assert summary["cards_skipped"] == 1
    assert "top-level must be a JSON object" in summary["errors"][0]


def test_missing_post_id_skipped(tmp_path: Path):
    _write_render_input(tmp_path / "render_inputs" / "missing.json", _render_input(post_id=""))

    summary = render_all_cards(tmp_path / "render_inputs", tmp_path / "renders")

    assert summary["cards_skipped"] == 1
    assert "missing 'post_id'" in summary["errors"][0]


def test_render_ready_false_skipped(tmp_path: Path):
    _write_render_input(tmp_path / "render_inputs" / "post-1.json", _render_input(render={"ready": False}))

    summary = render_all_cards(tmp_path / "render_inputs", tmp_path / "renders")

    assert summary["cards_rendered"] == 0
    assert summary["cards_skipped"] == 1
    assert summary["errors"] == []
    assert not (tmp_path / "renders").exists()


def test_valid_render_input_creates_png_with_expected_dimensions(tmp_path: Path):
    _write_render_input(tmp_path / "render_inputs" / "post-1.json", _render_input())

    summary = render_all_cards(tmp_path / "render_inputs", tmp_path / "renders", width=320, height=480)

    output = tmp_path / "renders" / "post-1" / "card.png"
    assert summary["cards_rendered"] == 1
    assert output.exists()
    assert output.stat().st_size > 0
    with Image.open(output) as image:
        assert image.format == "PNG"
        assert image.size == (320, 480)


def test_existing_card_skipped_when_overwrite_false(tmp_path: Path):
    _write_render_input(tmp_path / "render_inputs" / "post-1.json", _render_input())
    output = tmp_path / "renders" / "post-1" / "card.png"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"old")

    summary = render_all_cards(tmp_path / "render_inputs", tmp_path / "renders", overwrite=False)

    assert summary["cards_rendered"] == 0
    assert summary["cards_skipped"] == 1
    assert summary["skipped_existing"] == 1
    assert output.read_bytes() == b"old"


def test_overwrite_true_rewrites_card(tmp_path: Path):
    _write_render_input(tmp_path / "render_inputs" / "post-1.json", _render_input())
    output = tmp_path / "renders" / "post-1" / "card.png"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"old")

    summary = render_all_cards(tmp_path / "render_inputs", tmp_path / "renders", overwrite=True, width=320, height=480)

    assert summary["cards_rendered"] == 1
    with Image.open(output) as image:
        assert image.format == "PNG"


def test_dry_run_creates_no_directories_or_files(tmp_path: Path):
    _write_render_input(tmp_path / "render_inputs" / "post-1.json", _render_input())

    summary = render_all_cards(tmp_path / "render_inputs", tmp_path / "renders", dry_run=True)

    assert summary["dry_run"] is True
    assert summary["cards_rendered"] == 0
    assert not (tmp_path / "renders").exists()


def test_long_headline_and_body_do_not_crash(tmp_path: Path):
    long_text = " ".join(["centralbankpolicyshock"] * 200)
    _write_render_input(
        tmp_path / "render_inputs" / "post-1.json",
        _render_input(text={"headline": long_text, "body": long_text}),
    )

    summary = render_all_cards(tmp_path / "render_inputs", tmp_path / "renders", width=320, height=480)

    assert summary["cards_rendered"] == 1
    assert (tmp_path / "renders" / "post-1" / "card.png").exists()


def test_media_has_media_still_renders_card(tmp_path: Path):
    _write_render_input(
        tmp_path / "render_inputs" / "post-1.json",
        _render_input(media={"has_media": True, "files": [{"filename": "media_1.jpg"}]}),
    )

    summary = render_all_cards(tmp_path / "render_inputs", tmp_path / "renders", width=320, height=480)

    assert summary["cards_rendered"] == 1


def test_summary_json_printed_by_cli(tmp_path: Path, capsys):
    _write_render_input(tmp_path / "render_inputs" / "post-1.json", _render_input())
    args = [
        "render_text_cards.py",
        "--input-dir",
        str(tmp_path / "render_inputs"),
        "--output-dir",
        str(tmp_path / "renders"),
        "--width",
        "320",
        "--height",
        "480",
    ]

    with patch("sys.argv", args):
        assert main() == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["cards_rendered"] == 1
    assert summary["inputs_seen"] == 1


def test_atomic_write_uses_tmp_replace(tmp_path: Path):
    image = build_card_image(_render_input(), width=320, height=480)
    output = tmp_path / "renders" / "post-1" / "card.png"

    with patch("os.replace", wraps=os.replace) as mock_replace:
        write_card_atomically(image, output)

    assert output.exists()
    args = mock_replace.call_args[0]
    assert args[0].endswith("card.tmp.png")
    assert args[1].endswith("card.png")


def test_render_card_write_failure_recorded_and_continues(tmp_path: Path):
    _write_render_input(tmp_path / "render_inputs" / "post-1.json", _render_input())

    with patch("scripts.render_text_cards.write_card_atomically", side_effect=OSError("disk full")):
        result = render_card(tmp_path / "render_inputs" / "post-1.json", tmp_path / "renders")

    assert result["skipped"] is True
    assert "disk full" in result["error"]
