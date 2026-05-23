from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

VALID_REVIEW_STATUSES = {"pending", "approved", "rejected"}


def init_review_db(db_path: Path) -> None:
    """Ensures the review-state table exists."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_review_state (
                post_id TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected')),
                reviewed_at TEXT,
                note TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def get_review_states(db_path: Path, post_ids: list[str]) -> dict[str, dict]:
    """Returns stored review states for the provided post IDs."""
    if not post_ids:
        return {}

    init_review_db(db_path)
    unique_post_ids = list(dict.fromkeys(post_ids))
    placeholders = ",".join("?" for _ in unique_post_ids)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT post_id, status, reviewed_at, note, updated_at
            FROM candidate_review_state
            WHERE post_id IN ({placeholders})
            """,
            unique_post_ids,
        )
        return {
            row[0]: {
                "post_id": row[0],
                "status": row[1],
                "reviewed_at": row[2],
                "note": row[3],
                "updated_at": row[4],
            }
            for row in cursor.fetchall()
        }


def set_review_status(db_path: Path, post_id: str, status: str, note: str | None = None) -> None:
    """Creates or updates a review-state row for a candidate."""
    if status not in VALID_REVIEW_STATUSES:
        raise ValueError(f"Invalid review status: {status}")

    init_review_db(db_path)
    now_str = datetime.now(UTC).isoformat()
    normalized_note = note.strip() if isinstance(note, str) else None
    if not normalized_note:
        normalized_note = None
    reviewed_at = now_str if status in {"approved", "rejected"} else None

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO candidate_review_state (
                post_id, status, reviewed_at, note, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(post_id) DO UPDATE SET
                status = excluded.status,
                reviewed_at = excluded.reviewed_at,
                note = excluded.note,
                updated_at = excluded.updated_at
            """,
            (post_id, status, reviewed_at, normalized_note, now_str),
        )
        conn.commit()
