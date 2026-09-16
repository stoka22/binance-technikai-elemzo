from pathlib import Path

from binance_ta.settings import Settings


def test_load_returns_defaults_when_file_missing(tmp_path: Path):
    settings = Settings.load(tmp_path / "does_not_exist.json")

    assert settings.theme == "light"
    assert settings.show_tooltips is True
    assert settings.default_symbol == "BTCUSDT"


def test_save_and_load_roundtrip(tmp_path: Path):
    path = tmp_path / "settings.json"
    original = Settings(
        theme="dark",
        show_tooltips=False,
        default_symbol="ETHUSDT",
        default_interval="15m",
        default_limit=500,
        live_refresh_seconds=60,
    )

    original.save(path)
    loaded = Settings.load(path)

    assert loaded == original


def test_load_ignores_unknown_fields_and_corrupt_file(tmp_path: Path):
    path = tmp_path / "settings.json"
    path.write_text('{"theme": "dark", "unknown_field": 123', encoding="utf-8")  # hibás JSON

    settings = Settings.load(path)

    assert settings == Settings()  # visszaesik az alapértelmezettekre
