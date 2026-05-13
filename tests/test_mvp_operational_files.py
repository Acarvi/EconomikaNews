from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mvp_launcher_files_exist():
    assert (ROOT / "EconomikaNoticias.bat").is_file()
    assert (ROOT / "scripts" / "start_economika.ps1").is_file()
    assert (ROOT / "scripts" / "diagnose_mvp.ps1").is_file()


def test_gitignore_contains_unsafe_runtime_patterns():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    required_patterns = [
        ".env",
        ".env.*",
        "!.env.example",
        "__pycache__/",
        "*.pyc",
        ".pytest_cache/",
        "debug/",
        "debug_x_response.txt",
        "config/x.com_cookies*.json",
        "config/x.com_cookies*.txt",
        "user_data_scraper/",
        "*.pickle",
        "client_secrets.json",
    ]

    for pattern in required_patterns:
        assert pattern in gitignore


def test_readme_contains_quick_start_mvp():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Quick Start MVP" in readme
    assert "Manual URLs" in readme
    assert "X Viral Scout" in readme
