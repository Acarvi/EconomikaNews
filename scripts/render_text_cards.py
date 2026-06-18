from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont


BACKGROUND_COLORS = {
    "dark": "#07111F",
}
TEXT_COLOR = "#F9FAFB"
MUTED_TEXT_COLOR = "#A8B3C7"
SUBTLE_TEXT_COLOR = "#728098"
ACCENT_COLOR = "#42D3FF"
BADGE_COLOR = "#F8C44F"
PANEL_COLOR = "#101C2E"
PANEL_BORDER_COLOR = "#263650"
ERROR_PLACEHOLDER = "Untitled"
METRIC_LABELS = {
    "views": "Views",
    "likes": "Likes",
    "reposts": "Reposts",
    "replies": "Replies",
}


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


def format_compact_number(value: Any) -> str:
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return _clean_text(value)

    sign = "-" if number < 0 else ""
    number = abs(number)
    if number < 1000:
        if number.is_integer():
            return f"{sign}{int(number)}"
        return f"{sign}{number:g}"
    if number < 1_000_000:
        return f"{sign}{number / 1000:.1f}K"
    if number < 1_000_000_000:
        return f"{sign}{number / 1_000_000:.1f}M"
    return f"{sign}{number / 1_000_000_000:.1f}B"


def extract_domain_or_handle(url: str, account_handle: str | None) -> str:
    handle = _clean_text(account_handle).lstrip("@")
    clean_url = _clean_text(url)

    if clean_url:
        parsed = urlparse(clean_url if "://" in clean_url else f"https://{clean_url}")
        hostname = (parsed.hostname or "").lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        if hostname in {"x.com", "twitter.com"} and handle:
            return f"@{handle}"
        if hostname:
            return hostname

    if handle:
        return f"@{handle}"
    return "local"


def infer_badge(render_input: dict) -> str:
    text = render_input.get("text", {})
    if not isinstance(text, dict):
        text = {}

    combined_text = " ".join(
        _clean_text(text.get(key)) for key in ("headline", "body") if _clean_text(text.get(key))
    )
    if "BREAKING" in combined_text.upper():
        return "BREAKING"

    source = _clean_text(render_input.get("source")).lower()
    url = _clean_text(render_input.get("url")).lower()
    if source == "x" or "://x.com/" in url or "://twitter.com/" in url:
        return "X SIGNAL"

    return "NEWS"


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


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
    max_width: int,
    max_lines: int,
    line_spacing: int,
) -> int:
    x, y = xy
    height = _line_height(font)
    lines = truncate_lines(wrap_text(text, font, max_width), max_lines)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += height + line_spacing
    return y


def draw_chip(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    *,
    fill: str = PANEL_COLOR,
    outline: str = PANEL_BORDER_COLOR,
    text_fill: str = TEXT_COLOR,
    radius: int = 12,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline)
    left, top, right, bottom = box
    text_width = _text_width(text, font)
    text_height = _line_height(font)
    draw.text(
        (left + max(0, ((right - left) - text_width) // 2), top + max(0, ((bottom - top) - text_height) // 2) - 1),
        text,
        font=font,
        fill=text_fill,
    )


def _metric_items(render_input: dict) -> list[tuple[str, str]]:
    metrics = render_input.get("engagement", {}).get("metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}

    parts: list[tuple[str, str]] = []
    for key in ("views", "likes", "reposts", "replies"):
        value = metrics.get(key)
        if value is not None and value != "":
            parts.append((METRIC_LABELS[key], format_compact_number(value)))
    return parts


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

    margin = max(34, width // 16)
    max_width = width - (margin * 2)
    brand_font = _font(max(34, width // 24))
    label_font = _font(max(22, width // 42))
    headline_font = _font(max(48, width // 14))
    body_font = _font(max(28, width // 32))
    metric_font = _font(max(24, width // 38))
    small_font = _font(max(22, width // 44))

    raw_account = _clean_text(render_input.get("account_handle"))
    source = _clean_text(raw_account or render_input.get("source"), "local")
    source_label = f"@{raw_account.lstrip('@')}" if raw_account else source
    headline = _clean_text(render_input.get("text", {}).get("headline"), ERROR_PLACEHOLDER)
    body = _clean_text(render_input.get("text", {}).get("body"))
    footer_identity = extract_domain_or_handle(_clean_text(render_input.get("url")), source)
    post_id = _clean_text(render_input.get("post_id"))
    badge = infer_badge(render_input)

    y = margin
    draw.rectangle((0, 0, width, max(6, height // 180)), fill=ACCENT_COLOR)

    brand = "ECONOMIKA"
    draw.text((margin, y), brand, font=brand_font, fill=TEXT_COLOR)
    brand_width = _text_width(brand, brand_font)
    draw.text(
        (margin + brand_width + 18, y + max(2, _line_height(brand_font) // 4)),
        source_label.upper(),
        font=label_font,
        fill=MUTED_TEXT_COLOR,
    )

    chip_width = min(max(150, _text_width(badge, label_font) + 48), max_width // 2)
    chip_height = max(36, _line_height(label_font) + 18)
    draw_chip(
        draw,
        (width - margin - chip_width, y + 2, width - margin, y + 2 + chip_height),
        badge,
        label_font,
        fill="#17263A",
        outline="#39516C",
        text_fill=BADGE_COLOR,
        radius=chip_height // 2,
    )
    y += max(_line_height(brand_font), chip_height) + max(56, height // 26)

    accent_x = margin
    accent_y = y + 4
    draw.rounded_rectangle((accent_x, accent_y, accent_x + 8, min(height - margin * 2, accent_y + 210)), radius=4, fill=ACCENT_COLOR)
    text_x = margin + 28
    text_width = width - text_x - margin

    max_headline_lines = 7 if height >= 900 else 5
    y = draw_wrapped_text(draw, (text_x, y), headline, headline_font, TEXT_COLOR, text_width, max_headline_lines, max(10, height // 150))

    body_to_draw = body if body and body != headline else ""
    if body_to_draw:
        y += max(28, height // 60)
        max_body_lines = 6 if height >= 900 else 3
        y = draw_wrapped_text(
            draw,
            (text_x, y),
            body_to_draw,
            body_font,
            MUTED_TEXT_COLOR,
            text_width,
            max_body_lines,
            max(8, height // 180),
        )

    media_label = _media_label(render_input)
    metric_items = _metric_items(render_input)
    score = render_input.get("engagement", {}).get("score")
    chips: list[tuple[str, str]] = metric_items.copy()
    if score is not None and score != "":
        chips.append(("Score", format_compact_number(score)))

    if chips or media_label:
        y += max(44, height // 32)
        chip_gap = max(10, width // 90)
        chip_height = max(70, _line_height(metric_font) + _line_height(small_font) + 30)
        columns = 2 if width < 760 else 4
        chip_width = (max_width - (chip_gap * (columns - 1))) // columns
        chip_y = y
        for index, (label, value) in enumerate(chips):
            row = index // columns
            col = index % columns
            left = margin + col * (chip_width + chip_gap)
            top = chip_y + row * (chip_height + chip_gap)
            draw.rounded_rectangle(
                (left, top, left + chip_width, top + chip_height),
                radius=14,
                fill=PANEL_COLOR,
                outline=PANEL_BORDER_COLOR,
            )
            draw.text((left + 18, top + 13), label.upper(), font=small_font, fill=SUBTLE_TEXT_COLOR)
            draw.text((left + 18, top + 13 + _line_height(small_font) + 7), value, font=metric_font, fill=TEXT_COLOR)

        rows = (len(chips) + columns - 1) // columns if chips else 0
        y = chip_y + rows * chip_height + max(0, rows - 1) * chip_gap

        if media_label:
            y += chip_gap
            draw_chip(
                draw,
                (margin, y, width - margin, y + chip_height // 2),
                media_label,
                small_font,
                fill="#132235",
                outline=PANEL_BORDER_COLOR,
                text_fill=MUTED_TEXT_COLOR,
                radius=12,
            )

    footer = f"{post_id} / {footer_identity}"
    footer = _ellipsize(footer, small_font, max_width)
    footer_y = height - margin - _line_height(small_font)
    draw.line((margin, footer_y - 24, width - margin, footer_y - 24), fill="#1B2A3E", width=2)
    draw.text((margin, footer_y), footer, font=small_font, fill=SUBTLE_TEXT_COLOR)

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
