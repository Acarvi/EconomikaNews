import os
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from scripts.make_reels_from_x import calculate_score, extract_titular

@pytest.fixture
def sample_json(tmp_path):
    data = {
        "posts": [
            {
                "post_id": "1",
                "account_handle": "test",
                "text": "This is a test post.",
                "like_count": 10,
                "repost_count": 5,
                "reply_count": 2,
                "quote_count": 1,
                "created_at": "2026-06-28T10:00:00Z"
            },
            {
                "post_id": "2",
                "account_handle": "test",
                "text": "Another test post. With two sentences.",
                "like_count": 100,
                "repost_count": 50,
                "reply_count": 20,
                "quote_count": 10,
                "created_at": "2026-06-28T09:00:00Z"
            }
        ]
    }
    file_path = tmp_path / "test_posts.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return str(file_path)

def test_calculate_score():
    post = {
        "like_count": 10,     # 10
        "repost_count": 5,    # 5 * 4 = 20
        "reply_count": 2,     # 2 * 2 = 4
        "quote_count": 1,     # 1 * 3 = 3
                              # total = 37
    }
    score, sph = calculate_score(post)
    assert score == 37
    # sph depends on age, since no created_at, age_hours is 1
    assert sph == 37.0

def test_extract_titular():
    text = "This is a sentence. And another one. https://t.co/xyz"
    titular = extract_titular(text)
    assert titular == "THIS IS A SENTENCE."

@patch("scripts.make_reels_from_x.generate_mp4")
@patch("scripts.make_reels_from_x.shutil.which")
def test_make_reels_from_x_cli(mock_which, mock_generate_mp4, sample_json, tmp_path):
    mock_which.return_value = "ffmpeg"
    mock_generate_mp4.return_value = True

    # We will import main and mock sys.argv
    from scripts.make_reels_from_x import main
    import sys
    
    out_dir = tmp_path / "out"
    test_args = [
        "make_reels_from_x.py",
        "--input-json", sample_json,
        "--output-dir", str(out_dir),
        "--top", "1",
        "--dry-run"
    ]
    
    with patch.object(sys, 'argv', test_args):
        # Dry run shouldn't create output
        main()
        assert not out_dir.exists()

    test_args = [
        "make_reels_from_x.py",
        "--input-json", sample_json,
        "--output-dir", str(out_dir),
        "--top", "1"
    ]
    with patch.object(sys, 'argv', test_args):
        main()

    # The top post is "2"
    assert out_dir.exists()
    manifest_file = out_dir / "manifest.json"
    assert manifest_file.exists()
    
    with open(manifest_file, "r") as f:
        manifest = json.load(f)
        assert len(manifest["selected_posts"]) == 1
        assert manifest["selected_posts"][0]["post_id"] == "2"

    # Check folders
    date_str = list(out_dir.glob("20*"))[0].name
    post_dir = out_dir / date_str / "2"
    assert post_dir.exists()
    
    assert (post_dir / "card.png").exists()
    assert (post_dir / "caption.txt").exists()
    assert (post_dir / "metadata.json").exists()
    assert (post_dir / "preview_report.md").exists()

@patch("scripts.make_reels_from_x.shutil.which")
def test_missing_ffmpeg(mock_which, sample_json, tmp_path):
    mock_which.return_value = None
    
    from scripts.make_reels_from_x import main
    import sys
    
    out_dir = tmp_path / "out_missing"
    test_args = [
        "make_reels_from_x.py",
        "--input-json", sample_json,
        "--output-dir", str(out_dir),
        "--top", "1"
    ]
    
    with patch.object(sys, 'argv', test_args):
        main()
        
    manifest_file = out_dir / "manifest.json"
    with open(manifest_file, "r") as f:
        manifest = json.load(f)
        assert len(manifest["errors"]) > 0
        assert "ffmpeg not found" in manifest["errors"][0]

