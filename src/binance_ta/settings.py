"""Felhasználói beállítások: betöltés/mentés JSON fájlba, hogy a
preferenciák (téma, tooltipek, alapértelmezett szimbólum stb.) megmaradjanak
az alkalmazás újraindítása után is."""

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

SETTINGS_DIR = Path.home() / ".binance_ta"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"


@dataclass
class Settings:
    theme: str = "light"  # "light" | "dark"
    show_tooltips: bool = True
    default_symbol: str = "BTCUSDT"
    default_interval: str = "1h"
    default_limit: int = 300
    live_refresh_seconds: int = 30

    @classmethod
    def load(cls, path: Path = SETTINGS_FILE) -> "Settings":
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                known_fields = {f for f in cls.__dataclass_fields__}
                filtered = {k: v for k, v in data.items() if k in known_fields}
                return cls(**{**asdict(cls()), **filtered})
            except (json.JSONDecodeError, TypeError, OSError) as exc:
                logger.warning("Hibás beállítások fájl, alapértelmezettek használata: %s", exc)
        return cls()

    def save(self, path: Path = SETTINGS_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
