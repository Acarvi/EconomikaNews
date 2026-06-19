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
SURFACE_REASON_THRESHOLDS = (
    ("views", 1_000_000, "High-view post"),
    ("reposts", 500, "High repost velocity"),
    ("replies", 500, "High discussion"),
    ("likes", 5000, "Strong engagement"),
)


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


def _metric_number(value: Any) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


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


def _metrics(render_input: dict) -> dict:
    engagement = render_input.get("engagement", {})
    if not isinstance(engagement, dict):
        return {}
    metrics = engagement.get("metrics", {})
    return metrics if isinstance(metrics, dict) else {}


def build_surface_reasons(render_input: dict) -> list[str]:
    metrics = _metrics(render_input)
    reasons = [
        label
        for key, threshold, label in SURFACE_REASON_THRESHOLDS
        if _metric_number(metrics.get(key)) >= threshold
    ]
    return reasons or ["Approved editorial candidate"]


def build_signal_rows(render_input: dict) -> list[tuple[str, str]]:
    account = _clean_text(render_input.get("account_handle")).lstrip("@")
    source = _clean_text(render_input.get("source"), "local")
    engagement = render_input.get("engagement", {})
    if not isinstance(engagement, dict):
        engagement = {}
    media = render_input.get("media", {})
    if not isinstance(media, dict):
        media = {}
    review = render_input.get("review", {})
    if not isinstance(review, dict):
        review = {}

    rows: list[tuple[str, str]] = []
    rows.append(("Account", f"@{account}" if account else source))
    rows.append(("Source", source.upper()))

    score = engagement.get("score")
    if score is not None and score != "":
        rows.append(("Score", format_compact_number(score)))

    metric_parts = [
        f"{format_compact_number(value)} {label.lower()}"
        for label, value in _metric_items(render_input)
    ]
    if metric_parts:
        rows.append(("Metrics", " / ".join(metric_parts)))

    files = media.get("files")
    media_count = len(files) if isinstance(files, list) else 0
    rows.append(("Media", f"Attached ({media_count})" if media.get("has_media") else "Text only"))

    review_status = _clean_text(review.get("status"))
    if review_status:
        rows.append(("Editorial status", review_status.upper()))

    post_id = _clean_text(render_input.get("post_id"))
    if post_id:
        rows.append(("Post ID", post_id))

    return rows


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


def draw_panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    fill: str = "#0D1828",
    outline: str = PANEL_BORDER_COLOR,
    radius: int = 18,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline)


def draw_key_value_rows(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    rows: list[tuple[str, str]],
    label_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    value_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    *,
    max_rows: int = 6,
) -> None:
    left, top, right, bottom = box
    row_gap = max(8, (bottom - top) // 42)
    y = top
    label_width = max(72, min((right - left) // 2, max((_text_width(label, label_font) for label, _ in rows), default=0) + 12))
    line_height = max(_line_height(label_font), _line_height(value_font))

    for label, value in rows[:max_rows]:
        if y + line_height > bottom:
            break
        draw.text((left, y), label.upper(), font=label_font, fill=SUBTLE_TEXT_COLOR)
        clean_value = _ellipsize(_clean_text(value), value_font, max(1, right - left - label_width))
        draw.text((left + label_width, y), clean_value, font=value_font, fill=TEXT_COLOR)
        y += line_height + row_gap


def _metric_items(render_input: dict) -> list[tuple[str, str]]:
    metrics = _metrics(render_input)

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
    micro_font = _font(max(18, width // 52))

    raw_account = _clean_text(render_input.get("account_handle"))
    source = _clean_text(raw_account or render_input.get("source"), "local")
    source_label = f"@{raw_account.lstrip('@')}" if raw_account else source
    headline = _clean_text(render_input.get("text", {}).get("headline"), ERROR_PLACEHOLDER)
    body = _clean_text(render_input.get("text", {}).get("body"))
    footer_identity = extract_domain_or_handle(_clean_text(render_input.get("url")), source)
    post_id = _clean_text(render_input.get("post_id"))
    badge = infer_badge(render_input)

    footer_y = height - margin - _line_height(small_font)
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

    lower_panel_height = min(max(170, height // 4), max(120, footer_y - margin - 120))
    lower_panel_top = max(margin + 120, footer_y - 32 - lower_panel_height)
    max_headline_lines = 6 if height >= 900 else 4
    y = draw_wrapped_text(draw, (text_x, y), headline, headline_font, TEXT_COLOR, text_width, max_headline_lines, max(10, height // 150))

    body_to_draw = body if body and body != headline else ""
    if body_to_draw:
        y += max(28, height // 60)
        max_body_lines = 4 if height >= 900 else 2
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
        y += max(36, height // 36)
        middle_anchor = int(height * 0.43)
        metrics_available_bottom = lower_panel_top - max(24, height // 72)
        if y < middle_anchor and metrics_available_bottom > middle_anchor:
            y = middle_anchor
        chip_gap = max(10, width // 90)
        chip_height = max(66, _line_height(metric_font) + _line_height(small_font) + 28)
        columns = 2 if width < 760 else 4
        chip_width = (max_width - (chip_gap * (columns - 1))) // columns
        chip_rows = (len(chips) + columns - 1) // columns if chips else 0
        metrics_height = chip_rows * chip_height + max(0, chip_rows - 1) * chip_gap
        if media_label:
            metrics_height += chip_gap + chip_height // 2
        if y + metrics_height > metrics_available_bottom:
            y = max(margin, metrics_available_bottom - metrics_height)
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

        rows = chip_rows
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

    panel_gap = max(16, height // 96)
    if y + panel_gap > lower_panel_top:
        lower_panel_top = min(footer_y - 32 - lower_panel_height, y + panel_gap)
    lower_panel_top = max(margin + 120, lower_panel_top)
    lower_panel_bottom = min(footer_y - 32, lower_panel_top + lower_panel_height)
    draw_panel(draw, (margin, lower_panel_top, width - margin, lower_panel_bottom))

    panel_pad = max(18, width // 42)
    panel_left = margin + panel_pad
    panel_right = width - margin - panel_pad
    panel_top = lower_panel_top + panel_pad
    panel_bottom = lower_panel_bottom - panel_pad
    panel_title_font = small_font
    draw.text((panel_left, panel_top), "POST SIGNAL", font=panel_title_font, fill=ACCENT_COLOR)
    approved_label = ""
    review = render_input.get("review", {})
    if isinstance(review, dict) and _clean_text(review.get("status")).lower() == "approved":
        approved_label = "Editorial status: APPROVED"
        approved_width = min(_text_width(approved_label, micro_font) + 34, max(120, panel_right - panel_left))
        draw_chip(
            draw,
            (panel_right - approved_width, panel_top - 4, panel_right, panel_top + max(32, _line_height(micro_font) + 16)),
            approved_label,
            micro_font,
            fill="#173024",
            outline="#315F46",
            text_fill="#9BE7B2",
            radius=14,
        )

    section_top = panel_top + _line_height(panel_title_font) + max(18, height // 90)
    reasons = build_surface_reasons(render_input)
    reason_label = "WHY THIS SURFACED"
    draw.text((panel_left, section_top), reason_label, font=micro_font, fill=SUBTLE_TEXT_COLOR)
    reason_y = section_top + _line_height(micro_font) + max(10, height // 160)
    reason_gap = max(8, width // 110)
    chip_x = panel_left
    chip_h = max(32, _line_height(micro_font) + 16)
    max_reason_y = reason_y
    for reason in reasons[:4]:
        reason_text = _ellipsize(reason, micro_font, panel_right - panel_left)
        reason_w = min(_text_width(reason_text, micro_font) + 30, panel_right - panel_left)
        if chip_x + reason_w > panel_right:
            chip_x = panel_left
            reason_y += chip_h + reason_gap
        if reason_y + chip_h > panel_bottom:
            break
        draw_chip(
            draw,
            (chip_x, reason_y, chip_x + reason_w, reason_y + chip_h),
            reason_text,
            micro_font,
            fill="#132235",
            outline="#29415F",
            text_fill=TEXT_COLOR,
            radius=chip_h // 2,
        )
        chip_x += reason_w + reason_gap
        max_reason_y = max(max_reason_y, reason_y + chip_h)

    rows_top = max_reason_y + max(18, height // 90)
    if rows_top < panel_bottom:
        signal_title = "SOURCE SIGNAL"
        draw.text((panel_left, rows_top), signal_title, font=micro_font, fill=SUBTLE_TEXT_COLOR)
        draw_key_value_rows(
            draw,
            (panel_left, rows_top + _line_height(micro_font) + max(10, height // 160), panel_right, panel_bottom),
            build_signal_rows(render_input),
            micro_font,
            small_font,
            max_rows=6 if height >= 900 else 4,
        )

    footer = f"{post_id} / {footer_identity}"
    footer = _ellipsize(footer, small_font, max_width)
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
