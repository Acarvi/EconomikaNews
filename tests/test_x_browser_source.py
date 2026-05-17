from pathlib import Path

import pytest

from app.settings import RuntimePaths
import app.discovery.x_browser_source as x_browser_source


def test_x_browser_source_imports_without_launching_browser() -> None:
    assert x_browser_source.X_HOME_URL == "https://x.com/home"
    assert callable(x_browser_source.main)


def test_x_browser_source_parser_accepts_login_flag() -> None:
    args = x_browser_source.build_parser().parse_args(["--login"])

    assert args.login is True


def test_x_browser_source_parser_accepts_user_data_dir() -> None:
    args = x_browser_source.build_parser().parse_args(
        ["--login", "--user-data-dir", "C:\\Path\\To\\User Data"]
    )

    assert args.user_data_dir == "C:\\Path\\To\\User Data"


def test_x_browser_source_parser_accepts_profile_risk_flag() -> None:
    args = x_browser_source.build_parser().parse_args(
        ["--login", "--i-understand-profile-risk"]
    )

    assert args.i_understand_profile_risk is True


def test_validation_rejects_external_user_data_dir_without_risk_flag(tmp_path: Path) -> None:
    paths = RuntimePaths.from_project_root(tmp_path / "repo")
    external_profile = tmp_path / "external" / "User Data"
    external_profile.mkdir(parents=True)
    args = x_browser_source.build_parser().parse_args(
        ["--login", "--user-data-dir", str(external_profile)]
    )

    with pytest.raises(ValueError, match="--i-understand-profile-risk is required"):
        x_browser_source.validate_launch_options(args, paths)


def test_validation_accepts_external_user_data_dir_with_risk_flag(tmp_path: Path) -> None:
    paths = RuntimePaths.from_project_root(tmp_path / "repo")
    external_profile = tmp_path / "external" / "User Data"
    external_profile.mkdir(parents=True)
    args = x_browser_source.build_parser().parse_args(
        [
            "--login",
            "--user-data-dir",
            str(external_profile),
            "--i-understand-profile-risk",
        ]
    )

    options = x_browser_source.validate_launch_options(args, paths)

    assert options.user_data_dir == external_profile.resolve()
    assert options.uses_external_profile is True


def test_validation_accepts_default_runtime_profile_without_risk_flag(tmp_path: Path) -> None:
    paths = RuntimePaths.from_project_root(tmp_path / "repo")
    args = x_browser_source.build_parser().parse_args(["--login"])

    options = x_browser_source.validate_launch_options(args, paths)

    assert options.user_data_dir == paths.browser_profile.resolve()
    assert options.uses_external_profile is False
