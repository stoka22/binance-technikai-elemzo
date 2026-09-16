"""Központi logging konfiguráció (fájlba forgatva + konzolra)."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_LOG_DIR = Path.home() / ".binance_ta"
LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging(log_dir: Path | None = None, level: int = logging.INFO) -> Path:
    """Beállítja a root loggert: forgó fájl handler + konzol handler.

    Returns:
        A használt log fájl elérési útja.
    """
    log_dir = log_dir or DEFAULT_LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "binance_ta.log"

    root = logging.getLogger()
    root.setLevel(level)

    # Ismételt configure_logging() hívás (pl. teszteknél) ne duplikálja a handlereket.
    if root.handlers:
        return log_file

    formatter = logging.Formatter(LOG_FORMAT)

    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    return log_file
