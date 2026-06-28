from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


NO_READY_PACKETS_ERROR = "No ready publish packets found. Run the local pipeline or approve/generate a candidate first."


def path_for_json(path: Path) -> str:
    return path.as_posix()


def run_command(command: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout or "",
            "stderr": completed.stderr or "",
            "error": "",
        }
    except OSError as exc:
        return {
            "command": command,
            "returncode": 1,
            "stdout": "",
            "stderr": "",
            "error": f"Failed to start command: {exc}",
        }


def load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Failed to read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid JSON in {path}: top-level must be an object")
    return payload


def find_ready_packet(manifest: dict, post_id: str | None = None) -> dict | None:
    packets = manifest.get("packets", [])
    if not isinstance(packets, list):
        return None

    for packet in packets:
        if not isinstance(packet, dict):
            continue
        if post_id is not None:
            if str(packet.get("post_id") or "") == post_id and packet.get("packet_ready") is True:
                return packet
            continue
        if packet.get("packet_ready") is True:
            return packet
    return None


def resolve_card_path(post_id: str, render_manifest: dict | None = None) -> Path | None:
    if render_manifest:
        renders = render_manifest.get("renders", [])
        if isinstance(renders, list):
            for render in renders:
                if not isinstance(render, dict):
                    continue
                if str(render.get("post_id") or "") != post_id:
                    continue
                card_value = str(render.get("card_path") or "").strip()
                if card_value:
                    card_path = Path(card_value)
                    if card_path.is_file():
                        return card_path

    conventional_path = Path("runtime") / "renders" / post_id / "card.png"
    return conventional_path if conventional_path.is_file() else None


def copy_file(source_path: Path, output_path: Path, overwrite: bool) -> tuple[bool, str]:
    if output_path.exists() and not overwrite:
        return False, f"Skipped existing file without --overwrite: {output_path.as_posix()}"
    if not source_path.is_file():
        raise ValueError(f"Required source file missing: {source_path.as_posix()}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(f"{output_path.name}.tmp")
    try:
        shutil.copyfile(source_path, tmp_path)
        os.replace(str(tmp_path), str(output_path))
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return True, ""


def copy_preview_artifacts(
    packet: dict,
    preview_dir: Path,
    card_path: Path | None,
    overwrite: bool,
) -> dict[str, Any]:
    warnings: list[str] = []
    outputs = {
        "reel_mp4": preview_dir / "reel.mp4",
        "caption_txt": preview_dir / "caption.txt",
        "metadata_json": preview_dir / "metadata.json",
        "card_png": preview_dir / "card.png",
    }
    sources = {
        "reel_mp4": Path(str(packet.get("video_path") or "")),
        "caption_txt": Path(str(packet.get("caption_path") or "")),
        "metadata_json": Path(str(packet.get("metadata_path") or "")),
    }

    preview_dir.mkdir(parents=True, exist_ok=True)
    for key, source_path in sources.items():
        _, warning = copy_file(source_path, outputs[key], overwrite=overwrite)
        if warning:
            warnings.append(warning)

    if card_path is None:
        warnings.append("Card path not found; preview card.png was not copied.")
    else:
        _, warning = copy_file(card_path, outputs["card_png"], overwrite=overwrite)
        if warning:
            warnings.append(warning)

    return {
        "outputs": outputs,
        "warnings": warnings,
    }


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _display(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "n/a"
    text = str(value or "").strip()
    return text or "n/a"


def build_preview_report(
    *,
    packet: dict,
    preview_dir: Path,
    reel_mp4: Path,
    caption_txt: Path,
    metadata_json: Path,
    card_png: Path | None,
    report_path: Path,
) -> None:
    post_id = str(packet.get("post_id") or "")
    source_handle = packet.get("source_account_handle")
    source_url = packet.get("source_url")
    platforms = packet.get("platforms", [])
    caption = _read_text(caption_txt)
    lines = [
        "# Preview Reel",
        "",
        f"* Post ID: {_display(post_id)}",
        f"* Source handle: {_display(source_handle)}",
        f"* Source URL: {_display(source_url)}",
        f"* Platforms: {_display(platforms)}",
        f"* Final video path: `{path_for_json(reel_mp4)}`",
        f"* Caption path: `{path_for_json(caption_txt)}`",
        f"* Metadata path: `{path_for_json(metadata_json)}`",
        f"* Card path: `{path_for_json(card_png)}`" if card_png else "* Card path: n/a",
        f"* Upload readiness: {_display(packet.get('packet_ready') is True)}",
        "* Manual next steps: watch the reel, copy the caption, upload manually, then record publish status.",
        "",
        "## Caption",
        "",
        caption,
        "",
        "## Upload Checklist",
        "",
        "* [ ] Watch reel.mp4",
        "* [ ] Copy caption.txt",
        "* [ ] Upload manually to TikTok",
        "* [ ] Upload manually to Instagram Reels",
        "* [ ] Upload manually to YouTube Shorts",
        "* [ ] Record publish status with update_publish_status.py",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def open_path(path: Path) -> tuple[bool, str]:
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
            return True, ""

        command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            return False, detail or f"opener exited with code {completed.returncode}"
        return True, ""
    except OSError as exc:
        return False, str(exc)


def _command_error(label: str, result: dict[str, Any]) -> str:
    detail = str(result.get("error") or result.get("stderr") or result.get("stdout") or "").strip()
    if len(detail) > 1000:
        detail = f"{detail[:1000].rstrip()}..."
    message = f'{label} failed with exit code {result["returncode"]}'
    return f"{message}: {detail}" if detail else message


def _build_pipeline_command(args: argparse.Namespace) -> list[str]:
    command = [
        args.python_executable,
        "scripts/run_local_pipeline.py",
        "--summary-json",
        "runtime/reports/preview_reel_pipeline_summary.json",
        "--python-executable",
        args.python_executable,
    ]
    if args.overwrite:
        command.append("--overwrite")
    if args.continue_on_error:
        command.append("--continue-on-error")
    if args.duration_seconds is not None:
        command.extend(["--duration-seconds", str(args.duration_seconds)])
    return command


def _base_summary(post_id: str, preview_dir: Path) -> dict[str, Any]:
    return {
        "success": False,
        "post_id": post_id,
        "preview_dir": path_for_json(preview_dir),
        "reel_mp4": path_for_json(preview_dir / "reel.mp4"),
        "card_png": path_for_json(preview_dir / "card.png"),
        "caption_txt": path_for_json(preview_dir / "caption.txt"),
        "metadata_json": path_for_json(preview_dir / "metadata.json"),
        "preview_report_md": path_for_json(preview_dir / "preview_report.md"),
        "opened_video": False,
        "opened_folder": False,
        "errors": [],
        "warnings": [],
    }


def generate_preview_reel(args: argparse.Namespace) -> dict[str, Any]:
    preview_root = Path(args.preview_dir)
    post_id = str(args.post_id or "").strip()
    summary = _base_summary(post_id, preview_root / (post_id or "_pending"))

    pipeline_result = run_command(_build_pipeline_command(args))
    if pipeline_result["returncode"] != 0:
        summary["errors"].append(_command_error("Pipeline", pipeline_result))
        if not args.continue_on_error:
            return summary
        summary["warnings"].append("Continuing after pipeline failure because --continue-on-error was provided.")

    try:
        publish_manifest = load_json(Path("runtime/publish_queue/manifest.json"))
    except ValueError as exc:
        summary["errors"].append(str(exc))
        return summary

    packet = find_ready_packet(publish_manifest, post_id or None)
    if packet is None:
        if post_id:
            summary["errors"].append(f"Ready publish packet not found for post_id: {post_id}")
        else:
            summary["errors"].append(NO_READY_PACKETS_ERROR)
        return summary

    post_id = str(packet.get("post_id") or "").strip()
    preview_dir = preview_root / post_id
    summary = _base_summary(post_id, preview_dir)

    render_manifest = None
    render_manifest_path = Path("runtime/renders/manifest.json")
    if render_manifest_path.is_file():
        try:
            render_manifest = load_json(render_manifest_path)
        except ValueError as exc:
            summary["warnings"].append(str(exc))
    else:
        summary["warnings"].append(f"Render manifest not found: {render_manifest_path.as_posix()}")

    card_path = resolve_card_path(post_id, render_manifest)

    try:
        copied = copy_preview_artifacts(packet, preview_dir, card_path, overwrite=args.overwrite)
    except ValueError as exc:
        summary["errors"].append(str(exc))
        return summary

    summary["warnings"].extend(copied["warnings"])
    outputs = copied["outputs"]
    report_path = preview_dir / "preview_report.md"
    build_preview_report(
        packet=packet,
        preview_dir=preview_dir,
        reel_mp4=outputs["reel_mp4"],
        caption_txt=outputs["caption_txt"],
        metadata_json=outputs["metadata_json"],
        card_png=outputs["card_png"] if outputs["card_png"].is_file() else None,
        report_path=report_path,
    )

    if args.open:
        if not args.no_open_video:
            opened, error = open_path(outputs["reel_mp4"])
            summary["opened_video"] = opened
            if not opened:
                summary["warnings"].append(f"Failed to open video {outputs['reel_mp4'].as_posix()}: {error}")
        if not args.no_open_folder:
            opened, error = open_path(preview_dir)
            summary["opened_folder"] = opened
            if not opened:
                summary["warnings"].append(f"Failed to open preview folder {preview_dir.as_posix()}: {error}")

    summary["success"] = outputs["reel_mp4"].is_file()
    if not summary["success"]:
        summary["errors"].append(f"Final preview reel missing: {outputs['reel_mp4'].as_posix()}")
    return summary


def write_summary_atomically(summary: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(f"{output_path.name}.tmp")
    try:
        tmp_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(str(tmp_path), str(output_path))
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a ready-to-watch local preview reel MP4.")
    parser.add_argument("--post-id", default=None)
    parser.add_argument("--overwrite", action="store_true", default=False)
    parser.add_argument("--open", action="store_true", default=False)
    parser.add_argument("--no-open-video", action="store_true", default=False)
    parser.add_argument("--no-open-folder", action="store_true", default=False)
    parser.add_argument("--preview-dir", default="runtime/preview_reels")
    parser.add_argument("--summary-json", default=None)
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--continue-on-error", action="store_true", default=False)
    parser.add_argument("--duration-seconds", type=float, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = generate_preview_reel(args)
    if args.summary_json:
        try:
            write_summary_atomically(summary, Path(args.summary_json))
        except OSError as exc:
            message = f"Failed to write summary JSON {args.summary_json}: {exc}"
            summary["success"] = False
            summary["errors"].append(message)
            print(f"Error: {message}", file=sys.stderr)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
