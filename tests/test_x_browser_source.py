import app.discovery.x_browser_source as x_browser_source


def test_x_browser_source_imports_without_launching_browser() -> None:
    assert x_browser_source.X_HOME_URL == "https://x.com/home"
    assert callable(x_browser_source.main)


def test_x_browser_source_parser_accepts_login_flag() -> None:
    args = x_browser_source.build_parser().parse_args(["--login"])

    assert args.login is True
