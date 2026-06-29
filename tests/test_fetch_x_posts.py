import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scripts.fetch_x_posts import (
    normalize_handle,
    post_id_from_url,
    normalize_metric,
    normalize_post,
    filter_posts,
    write_json_atomically,
    fetch_manual_json,
    fetch_gallery_dl,
    fetch_x_api,
    main
)

def test_normalize_handle():
    assert normalize_handle("@juanrallo") == "juanrallo"
    assert normalize_handle("  @juanrallo  ") == "juanrallo"
    assert normalize_handle("juanrallo") == "juanrallo"
    assert normalize_handle(None) == ""

def test_post_id_from_url():
    assert post_id_from_url("https://x.com/juanrallo/status/12345") == "12345"
    assert post_id_from_url("https://twitter.com/user/status/67890?s=20") == "67890"
    assert post_id_from_url("https://example.com") is None
    assert post_id_from_url(None) is None

def test_normalize_metric():
    assert normalize_metric(None) == 0
    assert normalize_metric(123) == 123
    assert normalize_metric("123") == 123
    assert normalize_metric("1,234") == 1234
    assert normalize_metric("1.5K") == 1500
    assert normalize_metric("2M") == 2000000
    assert normalize_metric("invalid") == 0

def test_filter_posts():
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    old = (now - datetime.timedelta(days=3)).isoformat()
    recent = (now - datetime.timedelta(days=1)).isoformat()
    
    posts = [
        {"post_id": "1", "created_at": old, "text": "Old post"},
        {"post_id": "2", "created_at": recent, "text": "Recent post"},
        {"post_id": "3", "created_at": recent, "text": "@user reply", "raw": {"is_reply": True}},
        {"post_id": "4", "created_at": recent, "text": "RT @user repost", "raw": {"retweeted_status": True}},
        {"post_id": "5", "created_at": recent, "text": "Normal post"}
    ]
    
    # default (include none)
    f1 = filter_posts(posts, days_back=2, include_replies=False, include_reposts=False)
    assert [p["post_id"] for p in f1] == ["2", "5"]
    
    # include replies
    f2 = filter_posts(posts, days_back=2, include_replies=True, include_reposts=False)
    assert [p["post_id"] for p in f2] == ["2", "3", "5"]
    
    # include reposts
    f3 = filter_posts(posts, days_back=2, include_replies=False, include_reposts=True)
    assert [p["post_id"] for p in f3] == ["2", "4", "5"]

def test_write_json_atomically(tmp_path):
    out_file = tmp_path / "out.json"
    data = {"key": "value"}
    write_json_atomically(data, out_file)
    assert out_file.exists()
    assert json.loads(out_file.read_text(encoding="utf-8")) == data
    
    # ensure no tmp files left over
    assert len(list(tmp_path.iterdir())) == 1

def test_manual_json_provider(tmp_path):
    sample = {
        "posts": [
            {"account_handle": "test", "text": "hello", "url": "https://x.com/test/status/111", "like_count": "1K"}
        ]
    }
    sample_file = tmp_path / "sample.json"
    sample_file.write_text(json.dumps(sample))
    
    posts, errors, warnings = fetch_manual_json(str(sample_file))
    assert not errors
    assert len(posts) == 1
    assert posts[0]["post_id"] == "111"
    assert posts[0]["like_count"] == 1000
    
    # test passing a list directly
    sample_list_file = tmp_path / "sample_list.json"
    sample_list_file.write_text(json.dumps([{"account_handle": "test2", "url": "https://x.com/test/status/222"}]))
    posts, errors, warnings = fetch_manual_json(str(sample_list_file))
    assert len(posts) == 1
    assert posts[0]["post_id"] == "222"

@patch("scripts.fetch_x_posts.shutil_which")
@patch("scripts.fetch_x_posts.subprocess.run")
def test_gallery_dl_provider(mock_run, mock_which):
    mock_which.return_value = "/bin/gallery-dl"
    
    # mock success
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = json.dumps([
        2, 
        {"tweet_url": "https://x.com/user/status/123", "text": "hello", "favorite_count": 5}
    ]) + "\n"
    mock_run.return_value = mock_res
    
    posts, errors, warnings = fetch_gallery_dl(["test_account"], 10, None)
    assert not errors
    assert len(posts) == 1
    assert posts[0]["post_id"] == "123"
    assert posts[0]["like_count"] == 5

@patch("scripts.fetch_x_posts.shutil_which")
def test_gallery_dl_missing(mock_which):
    mock_which.return_value = None
    posts, errors, warnings = fetch_gallery_dl(["test_account"], 10, None)
    assert errors
    assert "not found" in errors[0]

@patch("scripts.fetch_x_posts.urllib.request.urlopen")
def test_x_api_provider(mock_urlopen):
    # mock user lookup then tweets lookup
    mock_user_res = MagicMock()
    mock_user_res.read.return_value = json.dumps({"data": {"id": "12345"}}).encode("utf-8")
    mock_user_cm = MagicMock()
    mock_user_cm.__enter__.return_value = mock_user_res
    
    mock_tweets_res = MagicMock()
    mock_tweets_res.read.return_value = json.dumps({
        "data": [
            {"id": "555", "text": "api tweet", "public_metrics": {"like_count": 10}}
        ]
    }).encode("utf-8")
    mock_tweets_cm = MagicMock()
    mock_tweets_cm.__enter__.return_value = mock_tweets_res
    
    mock_urlopen.side_effect = [mock_user_cm, mock_tweets_cm]
    
    posts, errors, warnings = fetch_x_api(["test_account"], 10, "fake_token")
    assert not errors
    assert len(posts) == 1
    assert posts[0]["post_id"] == "555"
    assert posts[0]["like_count"] == 10

def test_main_manual_json(tmp_path):
    sample = {"posts": [{"account_handle": "test", "url": "https://x.com/test/status/999"}]}
    sample_file = tmp_path / "sample.json"
    sample_file.write_text(json.dumps(sample))
    
    out_file = tmp_path / "out.json"
    
    with patch("sys.argv", ["fetch_x_posts.py", "--provider", "manual-json", "--input-json", str(sample_file), "--output-json", str(out_file)]):
        main()
        
    assert out_file.exists()
    out_data = json.loads(out_file.read_text())
    assert out_data["provider"] == "manual-json"
    assert len(out_data["posts"]) == 1
    assert out_data["posts"][0]["post_id"] == "999"

@patch("scripts.fetch_x_posts.os.environ.get")
@patch("scripts.fetch_x_posts.shutil_which")
@patch("scripts.fetch_x_posts.fetch_gallery_dl")
def test_main_auto_gallery_dl(mock_fetch, mock_which, mock_env, tmp_path):
    mock_env.return_value = None # no token
    mock_which.return_value = "/bin/gallery-dl"
    mock_fetch.return_value = ([{"post_id": "111", "account_handle": "test", "url": "http"}], [], [])
    
    out_file = tmp_path / "out.json"
    with patch("sys.argv", ["fetch_x_posts.py", "--accounts", "test", "--output-json", str(out_file)]):
        main()
        
    assert out_file.exists()
    out_data = json.loads(out_file.read_text())
    assert out_data["provider"] == "gallery-dl"
    
@patch("scripts.fetch_x_posts.os.environ.get")
@patch("scripts.fetch_x_posts.fetch_x_api")
def test_main_auto_x_api(mock_fetch, mock_env, tmp_path):
    mock_env.return_value = "secret" # has token
    mock_fetch.return_value = ([{"post_id": "222", "account_handle": "test", "url": "http"}], [], [])
    
    out_file = tmp_path / "out.json"
    with patch("sys.argv", ["fetch_x_posts.py", "--accounts", "test", "--output-json", str(out_file)]):
        main()
        
    assert out_file.exists()
    out_data = json.loads(out_file.read_text())
    assert out_data["provider"] == "x-api"
