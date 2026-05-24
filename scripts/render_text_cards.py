from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


BACKGROUND_COLORS = {
    "dark": "#111827",
}
TEXT_COLOR = "#F9FAFB"
MUTED_TEXT_COLOR = "#CBD5E1"
ACCENT_COLOR = "#38BDF8"
PANEL_COLOR = "#1F2937"
ERROR_PLACEHOLDER = "Untitled"


def path_for_json(path: Path) -> str:
    return path.as_posix()


def load_render_input(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to read {path}: {exc}") from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid render input in {path}: top-level must be a JSON object")

    return payload


def iter_render_input_files(input_dir: Path) -> list[Path]:
    if not input_dir.exists() or not input_dir.is_dir():
        return []

    return sorted(path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".json")


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue

    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _text_width(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
    if not text:
        return 0
    left, _top, right, _bottom = font.getbbox(text)
    return right - left


def _line_height(font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
    left, top, right, bottom = font.getbbox("Ag")
    return max(1, bottom - top)


def _clean_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return " ".join(text.split()) or fallback


def _ellipsize(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int) -> str:
    if _text_width(text, font) <= max_width:
        return text

    suffix = "..."
    available = max(0, max_width - _text_width(suffix, font))
    trimmed = ""
    for char in text:
        if _text_width(trimmed + char, font) > available:
            break
        trimmed += char
    return trimmed.rstrip() + suffix


def wrap_text(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int) -> list[str]:
    clean = _clean_text(text)
    if not clean:
        return []

    lines: list[str] = []
    current = ""
    for word in clean.split(" "):
        candidate = word if not current else f"{current} {word}"
        if _text_width(candidate, font) <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
            current = ""

        if _text_width(word, font) <= max_width:
            current = word
            continue

        chunk = ""
        for char in word:
            if _text_width(chunk + char, font) <= max_width:
                chunk += char
            else:
                if chunk:
                    lines.append(chunk)
                chunk = char
        current = chunk

    if current:
        lines.append(current)
    return lines


def truncate_lines(lines: list[str], max_lines: int) -> list[str]:
    if max_lines <= 0:
        return []
    if len(lines) <= max_lines:
        return lines
    truncated = lines[:max_lines]
    truncated[-1] = truncated[-1].rstrip() + "..."
    return truncated


def _draw_lines(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    lines: list[str],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
    line_spacing: int,
) -> int:
    x, y = xy
    height = _line_height(font)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += height + line_spacing
    return y


def _metrics_line(render_input: dict) -> str:
    metrics = render_input.get("engagement", {}).get("metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}

    parts = []
    for key in ("views", "likes", "reposts", "replies"):
        value = metrics.get(key)
        if value is not None and value != "":
            parts.append(f"{key}: {value}")
    return " / ".join(parts)


def _media_label(render_input: dict) -> str:
    media = render_input.get("media", {})
    if not isinstance(media, dict) or not media.get("has_media"):
        return ""

    files = media.get("files")
    count = len(files) if isinstance(files, list) else 0
    return f"Media attached: {count}"


def _validate_render_input(render_input: dict, path: Path) -> str:
    if render_input.get("schema_version") != 1:
        raise ValueError(f"Invalid render input in {path}: schema_version must be 1")
    if not render_input.get("post_id"):
        raise ValueError(f"Invalid render input in {path}: missing 'post_id'")

    render = render_input.get("render", {})
    if render is not None and not isinstance(render, dict):
        raise ValueError(f"Invalid render input in {path}: 'render' must be a JSON object")

    ready = render.get("ready", True) if isinstance(render, dict) else True
    if ready is not True:
        raise ValueError("NOT_READY")

    return str(render_input["post_id"])


def build_card_image(render_input: dict, width: int, height: int, background: str = "dark") -> Image.Image:
    bg = BACKGROUND_COLORS.get(background, BACKGROUND_COLORS["dark"])
    image = Image.new("RGB", (width, height), color=bg)
    draw = ImageDraw.Draw(image)

    margin = max(48, width // 15)
    max_width = width - (margin * 2)
    top_font = _font(max(28, width // 30))
    headline_font = _font(max(54, width // 13))
    body_font = _font(max(34, width // 27))
    small_font = _font(max(26, width // 36))

    source = _clean_text(render_input.get("account_handle") or render_input.get("source"), "local")
    headline = _clean_text(render_input.get("text", {}).get("headline"), ERROR_PLACEHOLDER)
    body = _clean_text(render_input.get("text", {}).get("body"))
    url = _clean_text(render_input.get("url"))
    post_id = _clean_text(render_input.get("post_id"))

    y = margin
    draw.text((margin, y), source.upper(), font=top_font, fill=ACCENT_COLOR)
    y += _line_height(top_font) + 70

    headline_lines = truncate_lines(wrap_text(headline, headline_font, max_width), 8)
    y = _draw_lines(draw, (margin, y), headline_lines, headline_font, TEXT_COLOR, 18)

    body_to_draw = body if body and body != headline else ""
    if body_to_draw:
        y += 50
        body_lines = truncate_lines(wrap_text(body_to_draw, body_font, max_width), 12)
        y = _draw_lines(draw, (margin, y), body_lines, body_font, MUTED_TEXT_COLOR, 14)

    media_label = _media_label(render_input)
    metrics = _metrics_line(render_input)
    label_lines = [line for line in (media_label, metrics) if line]
    if label_lines:
        y += 60
        box_height = (len(label_lines) * (_line_height(small_font) + 14)) + 28
        draw.rounded_rectangle(
            (margin, y, width - margin, y + box_height),
            radius=10,
            fill=PANEL_COLOR,
            outline="#334155",
        )
        label_y = y + 18
        for line in label_lines:
            draw.text((margin + 24, label_y), _ellipsize(line, small_font, max_width - 48), font=small_font, fill=TEXT_COLOR)
            label_y += _line_height(small_font) + 14

    footer = url or f"post_id: {post_id}"
    footer = _ellipsize(footer, small_font, max_width)
    footer_y = height - margin - _line_height(small_font)
    draw.text((margin, footer_y), footer, font=small_font, fill=MUTED_TEXT_COLOR)

    return image


def write_card_atomically(image: Image.Image, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name("card.tmp.png")
    image.save(tmp_path, format="PNG")
    os.replace(str(tmp_path), str(output_path))


def render_card(
    render_input_path: Path,
    output_dir: Path,
    overwrite: bool = False,
    dry_run: bool = False,
    width: int = 1080,
    height: int = 1920,
    background: str = "dark",
) -> dict:
    result = {
        "path": path_for_json(render_input_path),
        "post_id": "",
        "rendered": False,
        "skipped": False,
        "skipped_existing": False,
        "error": "",
    }

    try:
        render_input = load_render_input(render_input_path)
        post_id = _validate_render_input(render_input, render_input_path)
        result["post_id"] = post_id
    except ValueError as exc:
        if str(exc) == "NOT_READY":
            result["skipped"] = True
            return result
        result["skipped"] = True
        result["error"] = str(exc)
        return result

    output_path = output_dir / post_id / "card.png"
    if output_path.exists() and not overwrite:
        result["skipped"] = True
        result["skipped_existing"] = True
        return result

    if dry_run:
        return result

    try:
        image = build_card_image(render_input, width=width, height=height, background=background)
        write_card_atomically(image, output_path)
    except Exception as exc:
        result["skipped"] = True
        result["error"] = f"Failed to write {output_path}: {exc}"
        return result

    result["rendered"] = True
    return result


def render_all_cards(
    input_dir: Path,
    output_dir: Path,
    overwrite: bool = False,
    dry_run: bool = False,
    width: int = 1080,
    height: int = 1920,
    background: str = "dark",
    limit: int | None = None,
) -> dict:
    files = iter_render_input_files(input_dir)
    if limit is not None:
        files = files[:limit]

    summary = {
        "input_dir": path_for_json(input_dir),
        "output_dir": path_for_json(output_dir),
        "inputs_seen": len(files),
        "cards_rendered": 0,
        "cards_skipped": 0,
        "skipped_existing": 0,
        "errors": [],
        "dry_run": dry_run,
        "overwrite": overwrite,
    }

    for path in files:
        result = render_card(
            path,
            output_dir,
            overwrite=overwrite,
            dry_run=dry_run,
            width=width,
            height=height,
            background=background,
        )
        if result["rendered"]:
            summary["cards_rendered"] += 1
        if result["skipped"]:
            summary["cards_skipped"] += 1
        if result["skipped_existing"]:
            summary["skipped_existing"] += 1
        if result["error"]:
            summary["errors"].append(result["error"])

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Render local static PNG text cards from render input JSON files.")
    parser.add_argument("--input-dir", default="runtime/render_inputs")
    parser.add_argument("--output-dir", default="runtime/renders")
    parser.add_argument("--overwrite", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--background", default="dark")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    summary = render_all_cards(
        Path(args.input_dir),
        Path(args.output_dir),
        overwrite=args.overwrite,
        dry_run=args.dry_run,
        width=args.width,
        height=args.height,
        background=args.background,
        limit=args.limit,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
