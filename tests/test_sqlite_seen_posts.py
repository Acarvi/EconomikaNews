from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from datetime import UTC, datetime

import pytest

from app.storage.sqlite_seen_posts import (
    get_seen_post_ids,
    init_db,
    upsert_seen_posts,
)


def test_init_db_creates_table(tmp_path: Path) -> None:
    db_path = tmp_path / "test_seen_posts.db"
    assert not db_path.exists()

    init_db(db_path)
    assert db_path.exists()

    # Query sqlite_master to verify table exists
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='source_posts_seen'")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "source_posts_seen"


def test_get_seen_post_ids_empty_list(tmp_path: Path) -> None:
    db_path = tmp_path / "test_seen_posts.db"
    assert get_seen_post_ids(db_path, []) == set()


def test_upsert_and_get_seen_posts(tmp_path: Path) -> None:
    db_path = tmp_path / "test_seen_posts.db"

    candidates = [
        {
            "post_id": "post1",
            "source": "x",
            "account_handle": "wallstwolverine",
            "url": "https://x.com/status/1",
            "text_prefix": "Hello world",
            "score": 10.5,
            "media_count": 1,
        },
        {
            "post_id": "post2",
            "source": "x",
            "account_handle": "juanrallo",
            "url": "https://x.com/status/2",
            "text_prefix": "Hello Spain",
            "score": 20.0,
            "media_count": 0,
        },
    ]

    # Before upsert, they should not be seen
    assert get_seen_post_ids(db_path, ["post1", "post2", "post3"]) == set()

    # Upsert
    upsert_seen_posts(db_path, candidates)

    # Now post1 and post2 should be marked seen
    seen_ids = get_seen_post_ids(db_path, ["post1", "post2", "post3"])
    assert seen_ids == {"post1", "post2"}


def test_upsert_preserves_first_seen_at_but_updates_last_seen_at(tmp_path: Path) -> None:
    db_path = tmp_path / "test_seen_posts.db"

    candidate = {
        "post_id": "post1",
        "source": "x",
        "account_handle": "wallstwolverine",
        "url": "https://x.com/status/1",
        "text_prefix": "Original text",
        "score": 10.5,
        "media_count": 1,
    }

    # First upsert
    upsert_seen_posts(db_path, [candidate])

    # Fetch timestamps
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT first_seen_at, last_seen_at, score, text_prefix FROM source_posts_seen WHERE post_id='post1'")
        first_row = cursor.fetchone()
        assert first_row is not None
        first_seen_1, last_seen_1, score_1, text_1 = first_row
        assert score_1 == 10.5
        assert text_1 == "Original text"

    # Sleep slightly to ensure timestamp change
    time.sleep(0.01)

    # Second upsert with modified score, text_prefix, and media_count
    updated_candidate = {
        "post_id": "post1",
        "source": "x",
        "account_handle": "wallstwolverine",
        "url": "https://x.com/status/1",
        "text_prefix": "Updated text",
        "score": 55.0,
        "media_count": 2,
    }

    upsert_seen_posts(db_path, [updated_candidate])

    # Fetch timestamps again
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT first_seen_at, last_seen_at, score, text_prefix, media_count FROM source_posts_seen WHERE post_id='post1'")
        second_row = cursor.fetchone()
        assert second_row is not None
        first_seen_2, last_seen_2, score_2, text_2, media_count_2 = second_row

        # first_seen_at must remain exactly the same
        assert first_seen_1 == first_seen_2
        # last_seen_at must be updated (greater or different)
        assert last_seen_1 != last_seen_2
        assert score_2 == 55.0
        assert text_2 == "Updated text"
        assert media_count_2 == 2
