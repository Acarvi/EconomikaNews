from __future__ import annotations

import argparse
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from app.settings import DEFAULT_RUNTIME_PATHS, RuntimePaths, ensure_runtime_dirs

X_HOME_URL = "https://x.com/home"
REAL_PROFILE_WARNING = (
    "Using a real browser profile can modify cookies/session/history and may trigger X "
    "account checks. Do not use this for high-volume automation."
)


@dataclass(frozen=True)
class BrowserLaunchOptions:
    user_data_dir: Path
    url: str = X_HOME_URL
    executable_path: Path | None = None
    browser_channel: str | None = None
    uses_external_profile: bool = False


def _wait_for_enter(stop_event: threading.Event) -> None:
    try:
        input("Press Enter here after login, or close the browser window...\n")
    except EOFError:
        return
    stop_event.set()


def _resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def validate_launch_options(
    args: argparse.Namespace,
    paths: RuntimePaths = DEFAULT_RUNTIME_PATHS,
) -> BrowserLaunchOptions:
    paths = ensure_runtime_dirs(paths)
    runtime_root = paths.root.resolve()

    if args.user_data_dir:
        user_data_dir = _resolve_path(args.user_data_dir)
        if not user_data_dir.is_dir():
            raise ValueError(f"--user-data-dir must point to an existing directory: {user_data_dir}")
    else:
        user_data_dir = paths.browser_profile.resolve()

    uses_external_profile = not _is_relative_to(user_data_dir, runtime_root)
    if uses_external_profile and not args.i_understand_profile_risk:
        raise ValueError(
            "--i-understand-profile-risk is required when --user-data-dir points outside runtime/."
        )

    executable_path = None
    if args.executable_path:
        executable_path = _resolve_path(args.executable_path)
        if not executable_path.is_file():
            raise ValueError(f"--executable-path must point to an existing file: {executable_path}")

    return BrowserLaunchOptions(
        user_data_dir=user_data_dir,
        url=args.url,
        executable_path=executable_path,
        browser_channel=args.browser_channel,
        uses_external_profile=uses_external_profile,
    )


def run_login(
    paths: RuntimePaths = DEFAULT_RUNTIME_PATHS,
    options: BrowserLaunchOptions | None = None,
) -> Path:
    paths = ensure_runtime_dirs(paths)
    if options is None:
        options = BrowserLaunchOptions(user_data_dir=paths.browser_profile.resolve())

    from playwright.sync_api import Error, sync_playwright

    screenshot_path = paths.debug / "x_home.png"
    stop_event = threading.Event()
    input_thread = threading.Thread(target=_wait_for_enter, args=(stop_event,), daemon=True)

    with sync_playwright() as playwright:
        launch_kwargs = dict(
            user_data_dir=str(options.user_data_dir),
            headless=False,
            args=["--start-maximized"],
        )
        if options.executable_path is not None:
            launch_kwargs["executable_path"] = str(options.executable_path)
        elif options.browser_channel:
            launch_kwargs["channel"] = options.browser_channel

        if options.uses_external_profile:
            print(REAL_PROFILE_WARNING, file=sys.stderr)

        context = playwright.chromium.launch_persistent_context(
            **launch_kwargs,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(options.url, wait_until="domcontentloaded")

        try:
            page.screenshot(path=str(screenshot_path), full_page=False)
            print(f"Saved debug screenshot to {screenshot_path}")
        except Error as exc:
            print(f"Could not save debug screenshot: {exc}", file=sys.stderr)

        input_thread.start()
        try:
            while not stop_event.is_set():
                try:
                    if not context.pages:
                        break
                    page.wait_for_timeout(500)
                except Error:
                    break
        finally:
            try:
                context.close()
            except Error:
                pass

    return screenshot_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manual X browser login helper using a persistent local Chromium profile."
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open X home in a headed persistent Chromium context for manual login.",
    )
    parser.add_argument(
        "--executable-path",
        help="Path to an installed Chromium-based browser executable, for example Comet.exe.",
    )
    parser.add_argument(
        "--user-data-dir",
        help="Existing browser profile/user data directory to use instead of runtime/browser_profile.",
    )
    parser.add_argument(
        "--browser-channel",
        choices=("chrome", "msedge", "chromium"),
        help="Installed browser channel to launch when --executable-path is not provided.",
    )
    parser.add_argument(
        "--url",
        default=X_HOME_URL,
        help=f"URL to open for manual login. Defaults to {X_HOME_URL}.",
    )
    parser.add_argument(
        "--i-understand-profile-risk",
        action="store_true",
        help="Required when --user-data-dir points outside the repo runtime directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.login:
        parser.print_help()
        return 2

    try:
        options = validate_launch_options(args)
    except ValueError as exc:
        parser.error(str(exc))

    run_login(options=options)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
