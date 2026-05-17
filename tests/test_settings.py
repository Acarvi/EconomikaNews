from pathlib import Path

from app.settings import DEFAULT_RUNTIME_PATHS, PROJECT_ROOT, RuntimePaths, ensure_runtime_dirs


def test_default_runtime_paths_are_under_runtime() -> None:
    assert DEFAULT_RUNTIME_PATHS.root == PROJECT_ROOT / "runtime"
    assert DEFAULT_RUNTIME_PATHS.browser_profile == PROJECT_ROOT / "runtime" / "browser_profile"
    assert DEFAULT_RUNTIME_PATHS.debug == PROJECT_ROOT / "runtime" / "debug"


def test_ensure_runtime_dirs_creates_required_dirs(tmp_path: Path) -> None:
    paths = RuntimePaths.from_project_root(tmp_path)

    returned_paths = ensure_runtime_dirs(paths)

    assert returned_paths == paths
    assert paths.browser_profile.is_dir()
    assert paths.debug.is_dir()
