from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RuntimePaths:
    root: Path
    browser_profile: Path
    debug: Path

    @classmethod
    def from_project_root(cls, project_root: Path = PROJECT_ROOT) -> "RuntimePaths":
        runtime_root = project_root / "runtime"
        return cls(
            root=runtime_root,
            browser_profile=runtime_root / "browser_profile",
            debug=runtime_root / "debug",
        )


DEFAULT_RUNTIME_PATHS = RuntimePaths.from_project_root()


def ensure_runtime_dirs(paths: RuntimePaths = DEFAULT_RUNTIME_PATHS) -> RuntimePaths:
    paths.browser_profile.mkdir(parents=True, exist_ok=True)
    paths.debug.mkdir(parents=True, exist_ok=True)
    return paths
