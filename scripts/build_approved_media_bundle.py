from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
import urllib.request


CANDIDATE_MEDIA_KEYS = ("media_url", "media_url_https", "video_url", "preview_image_url")
MEDIA_OBJECT_KEYS = (
    "url",
    "media_url",
    "media_url_https",
    "video_url",
    "preview_image_url",
    "expanded_url",
)
CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "application/octet-stream": ".bin",
}
URL_PATH_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm", ".bin"}


def load_approved_payload(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Approved file not found: {path}")

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to read file {path}: {exc}") from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid payload structure in {path}: top-level must be a JSON object")

    if "candidates" not in payload:
        raise ValueError(f"Invalid payload structure in {path}: missing 'candidates' key")

    if not isinstance(payload["candidates"], list):
        raise ValueError(f"Invalid payload structure in {path}: 'candidates' must be a list")

    return payload


def candidate_bundle_dir(output_dir: Path, post_id: str) -> Path:
    return Path(output_dir) / post_id


def is_supported_direct_media_url(url: str) -> bool:
    if not isinstance(url, str):
        return False

    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    host = parsed.netloc.lower()
    if host == "t.co" or host.endswith(".t.co"):
        return False

    if host == "x.com" or host.endswith(".x.com") or host == "twitter.com" or host.endswith(".twitter.com"):
        path_parts = [part for part in parsed.path.lower().split("/") if part]
        if "status" in path_parts or "statuses" in path_parts:
            return False

    return True


def collect_media_url_entries(candidate: dict) -> list[dict]:
    found: list[dict] = []
    seen = set()

    def add_url(u: str):
        if not isinstance(u, str):
            return
        u = u.strip()
        if not u:
            return
        if u not in seen:
            seen.add(u)
            found.append({"url": u, "supported": is_supported_direct_media_url(u)})

    media = candidate.get("media")
    if isinstance(media, list):
        for item in media:
            if isinstance(item, dict):
                for k in MEDIA_OBJECT_KEYS:
                    val = item.get(k)
                    if val:
                        add_url(val)
            elif isinstance(item, str):
                add_url(item)
    elif isinstance(media, dict):
        for k in MEDIA_OBJECT_KEYS:
            val = media.get(k)
            if val:
                add_url(val)

    for k in CANDIDATE_MEDIA_KEYS:
        val = candidate.get(k)
        if val:
            add_url(val)

    return found


def extract_media_urls(candidate: dict) -> list[dict]:
    return [item for item in collect_media_url_entries(candidate) if item["supported"]]


def infer_media_extension(url: str, content_type: str | None = None) -> str:
    if content_type:
        ct = content_type.lower().split(";")[0].strip()
        if ct in CONTENT_TYPE_EXTENSIONS:
            return CONTENT_TYPE_EXTENSIONS[ct]

    try:
        parsed = urlparse(url)
        path = parsed.path
        if path:
            suffix = Path(path).suffix.lower()
            if suffix in URL_PATH_EXTENSIONS:
                if suffix == ".jpeg":
                    return ".jpg"
                return suffix
    except Exception:
        pass

    return ".bin"


def default_downloader(url: str, dest_path: Path, timeout_seconds: float = 30.0) -> str | None:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
        content_type = response.info().get_content_type()
        dest_path.write_bytes(response.read())
        return content_type


def write_metadata_atomically(metadata_path: Path, data: dict) -> None:
    tmp_path = metadata_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(str(tmp_path), str(metadata_path))


def build_bundle_for_candidate(
    candidate: dict,
    output_dir: Path,
    downloader,
    overwrite: bool = False,
    dry_run: bool = False,
    timeout_seconds: float = 30.0
) -> dict:
    if not isinstance(candidate, dict):
        return {
            "post_id": None,
            "success": False,
            "media_downloaded": 0,
            "media_skipped": 0,
            "media_failed": 0,
            "errors": ["Candidate must be a dictionary object"],
        }

    post_id = candidate.get("post_id")
    if not post_id:
        return {
            "post_id": None,
            "success": False,
            "media_downloaded": 0,
            "media_skipped": 0,
            "media_failed": 0,
            "errors": ["Candidate is missing required 'post_id'"],
        }

    post_id = str(post_id)
    candidate_dir = candidate_bundle_dir(output_dir, post_id)

    raw_urls = collect_media_url_entries(candidate)

    local_media = []
    index = 1
    media_downloaded = 0
    media_skipped = 0
    media_failed = 0
    bundle_errors = []

    for item in raw_urls:
        url = item["url"]
        if not item["supported"]:
            local_media.append({
                "index": index,
                "source_url": url,
                "local_path": "",
                "filename": "",
                "content_type": None,
                "status": "skipped_unsupported_url"
            })
            index += 1
            continue

        # Check existing files
        if not dry_run:
            existing_files = list(candidate_dir.glob(f"media_{index}.*"))
            existing_files = [f for f in existing_files if f.suffix != ".tmp"]
        else:
            existing_files = []

        if existing_files and not overwrite:
            existing_file = existing_files[0]
            local_media.append({
                "index": index,
                "source_url": url,
                "local_path": str(existing_file),
                "filename": existing_file.name,
                "content_type": None,
                "status": "skipped_existing"
            })
            media_skipped += 1
            index += 1
            continue

        # If dry-run, do not touch fs
        if dry_run:
            index += 1
            continue

        # Real download
        candidate_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = candidate_dir / f"media_{index}.tmp"
        try:
            content_type = downloader(url, tmp_path, timeout_seconds)
            ext = infer_media_extension(url, content_type)
            final_path = candidate_dir / f"media_{index}{ext}"

            # Clean up other existing extensions
            for f in existing_files:
                if f != final_path and f.exists():
                    f.unlink()

            # Atomic replace
            os.replace(str(tmp_path), str(final_path))

            local_media.append({
                "index": index,
                "source_url": url,
                "local_path": str(final_path),
                "filename": final_path.name,
                "content_type": content_type,
                "status": "downloaded"
            })
            media_downloaded += 1
        except Exception as exc:
            err_msg = f"Failed to download media_{index} from {url}: {exc}"
            bundle_errors.append(err_msg)
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            local_media.append({
                "index": index,
                "source_url": url,
                "local_path": "",
                "filename": "",
                "content_type": None,
                "status": "failed",
                "error": str(exc)
            })
            media_failed += 1

        index += 1

    # Prepare metadata dictionary
    metadata = {
        "post_id": candidate.get("post_id"),
        "account_handle": candidate.get("account_handle"),
        "url": candidate.get("url"),
        "text_prefix": candidate.get("text_prefix"),
        "score": candidate.get("score"),
        "metrics": candidate.get("metrics"),
        "media_count": candidate.get("media_count"),
        "source": candidate.get("source"),
        "review_status": candidate.get("review_status"),
        "reviewed_at": candidate.get("reviewed_at"),
        "review_note": candidate.get("review_note"),
        "review_updated_at": candidate.get("review_updated_at"),
        "original_candidate": candidate,
        "local_media": local_media,
        "bundle_errors": bundle_errors,
    }
    if "is_new" in candidate:
        metadata["is_new"] = candidate["is_new"]

    if not dry_run:
        candidate_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = candidate_dir / "metadata.json"
        try:
            write_metadata_atomically(metadata_path, metadata)
        except Exception as exc:
            err_msg = f"Failed to write metadata atomically: {exc}"
            bundle_errors.append(err_msg)
            return {
                "post_id": post_id,
                "success": False,
                "metadata_written": False,
                "media_downloaded": media_downloaded,
                "media_skipped": media_skipped,
                "media_failed": media_failed,
                "errors": [err_msg] + bundle_errors,
            }

    return {
        "post_id": post_id,
        "success": len(bundle_errors) == 0,
        "metadata_written": not dry_run,
        "media_downloaded": media_downloaded,
        "media_skipped": media_skipped,
        "media_failed": media_failed,
        "errors": bundle_errors,
    }


def build_all_bundles(
    payload: dict,
    output_dir: Path,
    downloader,
    overwrite: bool = False,
    dry_run: bool = False,
    timeout_seconds: float = 30.0
) -> dict:
    candidates = payload.get("candidates", [])

    approved_count = len(candidates)
    bundled_count = 0
    media_downloaded = 0
    media_skipped = 0
    media_failed = 0
    errors = []

    for idx, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            errors.append(f"Candidate at index {idx} is not a JSON object")
            continue

        post_id = candidate.get("post_id")
        if not post_id:
            errors.append(f"Candidate at index {idx} is missing required 'post_id'")
            continue

        res = build_bundle_for_candidate(
            candidate=candidate,
            output_dir=output_dir,
            downloader=downloader,
            overwrite=overwrite,
            dry_run=dry_run,
            timeout_seconds=timeout_seconds,
        )

        # Count as bundled even if there are single media download failures,
        # but only if the candidate was structurally valid and metadata could be written.
        # Wait, if res["success"] is False due to bundle_errors, we still created metadata.json
        # and downloaded what we could, so it is "bundled". Let's check:
        # "Failed single media download: record error, continue candidate"
        # Let's count it as bundled if a folder was created and metadata written,
        # which is true if we had a valid post_id and didn't fail at metadata write.
        if res.get("post_id") is not None:
            bundled_count += 1

        if res["errors"]:
            errors.extend([f"Candidate {post_id}: {err}" for err in res["errors"]])

        media_downloaded += res["media_downloaded"]
        media_skipped += res["media_skipped"]
        media_failed += res["media_failed"]

    return {
        "approved_count": approved_count,
        "bundled_count": bundled_count,
        "media_downloaded": media_downloaded,
        "media_skipped": media_skipped,
        "media_failed": media_failed,
        "errors": errors,
        "output_dir": str(output_dir),
        "dry_run": dry_run,
        "overwrite": overwrite,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build approved media bundles.")
    parser.add_argument("--approved-file", default="runtime/outputs/approved_candidates.json")
    parser.add_argument("--output-dir", default="runtime/approved")
    parser.add_argument("--overwrite", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    approved_file = Path(args.approved_file)
    output_dir = Path(args.output_dir)

    try:
        payload = load_approved_payload(approved_file)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error loading approved candidates: {exc}", file=sys.stderr)
        return 1

    summary = build_all_bundles(
        payload=payload,
        output_dir=output_dir,
        downloader=default_downloader,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
        timeout_seconds=args.timeout_seconds,
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
