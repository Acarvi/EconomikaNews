from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class XInternalRuntimeConfig:
    headers_file: str | None = None
    timeline_template_url: str | None = None
    user_lookup_template_url: str | None = None
    user_id: str | None = None

@dataclass(frozen=True)
class PathsRuntimeConfig:
    accounts_file: str | None = None
    db_path: str | None = None
    output_json: str | None = None

@dataclass(frozen=True)
class RuntimeConfig:
    x_internal: XInternalRuntimeConfig
    paths: PathsRuntimeConfig


def load_runtime_config(path: Path) -> RuntimeConfig:
    """Loads a runtime configuration from a YAML file.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the YAML structure is invalid or not dict-like.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in config file {path}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Could not read config file {path}: {exc}") from exc

    if data is None:
        data = {}

    if not isinstance(data, dict):
        raise ValueError("Configuration YAML must be a dict-like structure")

    x_internal_data = data.get("x_internal")
    if x_internal_data is None:
        x_internal_data = {}
    if not isinstance(x_internal_data, dict):
        raise ValueError("'x_internal' key must be a dictionary")

    paths_data = data.get("paths")
    if paths_data is None:
        paths_data = {}
    if not isinstance(paths_data, dict):
        raise ValueError("'paths' key must be a dictionary")

    x_internal = XInternalRuntimeConfig(
        headers_file=_optional_string(x_internal_data.get("headers_file")),
        timeline_template_url=_optional_string(x_internal_data.get("timeline_template_url")),
        user_lookup_template_url=_optional_string(
            x_internal_data.get("user_lookup_template_url")
        ),
        user_id=_optional_string(x_internal_data.get("user_id")),
    )

    paths = PathsRuntimeConfig(
        accounts_file=_optional_string(paths_data.get("accounts_file")),
        db_path=_optional_string(paths_data.get("db_path")),
        output_json=_optional_string(paths_data.get("output_json")),
    )

    return RuntimeConfig(x_internal=x_internal, paths=paths)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def apply_runtime_config_to_env(config: RuntimeConfig) -> None:
    """Sets env vars only if not already set:
      X_INTERNAL_HEADERS_FILE
      X_INTERNAL_TIMELINE_TEMPLATE_URL
      X_INTERNAL_USER_LOOKUP_TEMPLATE_URL
      X_INTERNAL_USER_ID (if present and non-empty)
    """
    x_cfg = config.x_internal

    if x_cfg.headers_file and "X_INTERNAL_HEADERS_FILE" not in os.environ:
        os.environ["X_INTERNAL_HEADERS_FILE"] = str(x_cfg.headers_file)

    if (
        x_cfg.timeline_template_url
        and "X_INTERNAL_TIMELINE_TEMPLATE_URL" not in os.environ
    ):
        os.environ["X_INTERNAL_TIMELINE_TEMPLATE_URL"] = str(x_cfg.timeline_template_url)

    if (
        x_cfg.user_lookup_template_url
        and "X_INTERNAL_USER_LOOKUP_TEMPLATE_URL" not in os.environ
    ):
        os.environ["X_INTERNAL_USER_LOOKUP_TEMPLATE_URL"] = str(x_cfg.user_lookup_template_url)

    if x_cfg.user_id and "X_INTERNAL_USER_ID" not in os.environ:
        os.environ["X_INTERNAL_USER_ID"] = str(x_cfg.user_id)
