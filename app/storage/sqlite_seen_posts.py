from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def init_db(db_path: Path) -> None:
    """Ensures the parent directory exists and initializes the seen-posts table."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_posts_seen (
                post_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                account_handle TEXT NOT NULL,
                url TEXT,
                text_prefix TEXT,
                score REAL,
                media_count INTEGER,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
        """)
        conn.commit()


def get_seen_post_ids(db_path: Path, post_ids: list[str]) -> set[str]:
    """Returns a set of post_ids that have already been seen from the provided list."""
    if not post_ids:
        return set()
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        placeholders = ",".join("?" for _ in post_ids)
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT post_id FROM source_posts_seen WHERE post_id IN ({placeholders})",
            post_ids,
        )
        return {row[0] for row in cursor.fetchall()}


def upsert_seen_posts(db_path: Path, candidates: list[dict]) -> None:
    """Upserts candidates into the source_posts_seen table.
    
    If a post already exists, updates last_seen_at, score, media_count,
    url, and text_prefix, preserving first_seen_at.
    """
    if not candidates:
        return
    init_db(db_path)
    now_str = datetime.now(UTC).isoformat()
    with sqlite3.connect(db_path) as conn:
        for c in candidates:
            post_id = c["post_id"]
            source = c.get("source") or "x"
            account_handle = c["account_handle"]
            url = c.get("url")
            text_prefix = c.get("text_prefix")
            score = c.get("score", 0.0)
            media_count = c.get("media_count", 0)

            conn.execute(
                """
                INSERT INTO source_posts_seen (
                    post_id, source, account_handle, url, text_prefix, score, media_count, first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    score = excluded.score,
                    media_count = excluded.media_count,
                    url = COALESCE(excluded.url, source_posts_seen.url),
                    text_prefix = COALESCE(excluded.text_prefix, source_posts_seen.text_prefix)
                """,
                (
                    post_id,
                    source,
                    account_handle,
                    url,
                    text_prefix,
                    score,
                    media_count,
                    now_str,
                    now_str,
                ),
            )
        conn.commit()
