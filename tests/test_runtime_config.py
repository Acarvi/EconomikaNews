from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

from app.config.runtime_config import (
    RuntimeConfig,
    XInternalRuntimeConfig,
    apply_runtime_config_to_env,
    load_runtime_config,
)


def test_x_internal_example_config_exists_and_uses_placeholders_only() -> None:
    path = Path("config/x_internal.example.yaml")
    assert path.exists()

    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)

    assert data == {
        "x_internal": {
            "headers_file": "runtime/secrets/x_headers.json",
            "timeline_template_url": "PASTE_USER_TWEETS_TEMPLATE_URL_HERE",
            "user_lookup_template_url": "PASTE_USER_BY_SCREEN_NAME_TEMPLATE_URL_HERE",
            "user_id": None,
        },
        "paths": {
            "accounts_file": "runtime/config/accounts.local.yaml",
            "db_path": "runtime/economika_news.db",
            "output_json": "runtime/outputs/x_candidates.json",
        },
    }

    forbidden = [
        "x.com/i/api/graphql",
        "auth_token",
        "ct0",
        "bearer",
        "cookie",
        "authorization",
    ]
    lowered = text.lower()
    for value in forbidden:
        assert value not in lowered


def test_load_runtime_config_valid_config_and_missing_sections(tmp_path: Path) -> None:
    config_path = tmp_path / "x_internal.local.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "x_internal": {
                    "headers_file": "runtime/secrets/x_headers.json",
                    "timeline_template_url": "timeline-template",
                    "user_lookup_template_url": "lookup-template",
                    "user_id": 123,
                    "ignored": "ok",
                },
                "paths": {
                    "accounts_file": "runtime/config/accounts.local.yaml",
                    "db_path": "runtime/test.db",
                    "output_json": "runtime/outputs/test.json",
                    "ignored": "ok",
                },
                "ignored": {"ok": True},
            }
        ),
        encoding="utf-8",
    )

    config = load_runtime_config(config_path)

    assert config.x_internal.headers_file == "runtime/secrets/x_headers.json"
    assert config.x_internal.timeline_template_url == "timeline-template"
    assert config.x_internal.user_lookup_template_url == "lookup-template"
    assert config.x_internal.user_id == "123"
    assert config.paths.accounts_file == "runtime/config/accounts.local.yaml"
    assert config.paths.db_path == "runtime/test.db"
    assert config.paths.output_json == "runtime/outputs/test.json"

    empty_path = tmp_path / "empty.yaml"
    empty_path.write_text("unknown: true\n", encoding="utf-8")
    empty_config = load_runtime_config(empty_path)

    assert empty_config.x_internal == XInternalRuntimeConfig()
    assert empty_config.paths.accounts_file is None


def test_load_runtime_config_errors_are_clear(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        load_runtime_config(tmp_path / "missing.yaml")

    invalid_yaml = tmp_path / "invalid.yaml"
    invalid_yaml.write_text("x_internal: [", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid YAML"):
        load_runtime_config(invalid_yaml)

    non_dict = tmp_path / "non_dict.yaml"
    non_dict.write_text("- item\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a dict"):
        load_runtime_config(non_dict)

    bad_section = tmp_path / "bad_section.yaml"
    bad_section.write_text("x_internal: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="x_internal"):
        load_runtime_config(bad_section)


def test_apply_runtime_config_sets_missing_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [
        "X_INTERNAL_HEADERS_FILE",
        "X_INTERNAL_TIMELINE_TEMPLATE_URL",
        "X_INTERNAL_USER_LOOKUP_TEMPLATE_URL",
        "X_INTERNAL_USER_ID",
    ]:
        monkeypatch.delenv(name, raising=False)

    config = RuntimeConfig(
        x_internal=XInternalRuntimeConfig(
            headers_file="headers.json",
            timeline_template_url="timeline",
            user_lookup_template_url="lookup",
            user_id="123",
        ),
        paths=load_runtime_config(Path("config/x_internal.example.yaml")).paths,
    )

    apply_runtime_config_to_env(config)

    assert os.environ["X_INTERNAL_HEADERS_FILE"] == "headers.json"
    assert os.environ["X_INTERNAL_TIMELINE_TEMPLATE_URL"] == "timeline"
    assert os.environ["X_INTERNAL_USER_LOOKUP_TEMPLATE_URL"] == "lookup"
    assert os.environ["X_INTERNAL_USER_ID"] == "123"


def test_apply_runtime_config_does_not_overwrite_existing_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("X_INTERNAL_HEADERS_FILE", "")
    monkeypatch.setenv("X_INTERNAL_TIMELINE_TEMPLATE_URL", "env-timeline")
    monkeypatch.setenv("X_INTERNAL_USER_LOOKUP_TEMPLATE_URL", "env-lookup")
    monkeypatch.setenv("X_INTERNAL_USER_ID", "env-user")

    config = RuntimeConfig(
        x_internal=XInternalRuntimeConfig(
            headers_file="config-headers",
            timeline_template_url="config-timeline",
            user_lookup_template_url="config-lookup",
            user_id="config-user",
        ),
        paths=load_runtime_config(Path("config/x_internal.example.yaml")).paths,
    )

    apply_runtime_config_to_env(config)

    assert os.environ["X_INTERNAL_HEADERS_FILE"] == ""
    assert os.environ["X_INTERNAL_TIMELINE_TEMPLATE_URL"] == "env-timeline"
    assert os.environ["X_INTERNAL_USER_LOOKUP_TEMPLATE_URL"] == "env-lookup"
    assert os.environ["X_INTERNAL_USER_ID"] == "env-user"


@pytest.mark.parametrize("user_id", [None, ""])
def test_apply_runtime_config_skips_empty_user_id(
    monkeypatch: pytest.MonkeyPatch,
    user_id: str | None,
) -> None:
    monkeypatch.delenv("X_INTERNAL_USER_ID", raising=False)

    apply_runtime_config_to_env(
        RuntimeConfig(
            x_internal=XInternalRuntimeConfig(user_id=user_id),
            paths=load_runtime_config(Path("config/x_internal.example.yaml")).paths,
        )
    )

    assert "X_INTERNAL_USER_ID" not in os.environ


def test_no_local_runtime_config_or_secret_files_tracked() -> None:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "runtime",
            "*/x_headers.json",
            "x_headers.json",
            ".env",
            ".env.*",
            "*.db",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == ""
