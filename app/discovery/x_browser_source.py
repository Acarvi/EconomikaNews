from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

from app.settings import DEFAULT_RUNTIME_PATHS, RuntimePaths, ensure_runtime_dirs

X_HOME_URL = "https://x.com/home"


def _wait_for_enter(stop_event: threading.Event) -> None:
    try:
        input("Press Enter here after login, or close the browser window...\n")
    except EOFError:
        return
    stop_event.set()


def run_login(paths: RuntimePaths = DEFAULT_RUNTIME_PATHS) -> Path:
    paths = ensure_runtime_dirs(paths)

    from playwright.sync_api import Error, sync_playwright

    screenshot_path = paths.debug / "x_home.png"
    stop_event = threading.Event()
    input_thread = threading.Thread(target=_wait_for_enter, args=(stop_event,), daemon=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(paths.browser_profile),
            headless=False,
            args=["--start-maximized"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(X_HOME_URL, wait_until="domcontentloaded")

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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.login:
        parser.print_help()
        return 2

    run_login()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
