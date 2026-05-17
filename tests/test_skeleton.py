from pathlib import Path

import app.main


ROOT = Path(__file__).resolve().parents[1]


def test_main_is_callable() -> None:
    assert callable(app.main.main)


def test_product_blueprint_exists() -> None:
    assert (ROOT / "PRODUCT_BLUEPRINT.md").is_file()


def test_config_examples_exist() -> None:
    assert (ROOT / "config" / "accounts.example.yaml").is_file()
    assert (ROOT / "config" / "settings.example.yaml").is_file()
