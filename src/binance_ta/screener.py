"""Piac-szintű szűrés: a megadott szimbólumokra korlátozott párhuzamossággal
lekéri az adatokat és kiszámolja a technikai pontszámot, hogy ne lépjük túl
a Binance rate limitjét (~1370 szimbólum egyszerre, szekvenciálisan
percekig tartana és könnyen 429-be futna)."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

from binance_ta.client import BinanceAPIError, fetch_klines
from binance_ta.scoring import ScoreBreakdown, compute_score

logger = logging.getLogger(__name__)

DEFAULT_MAX_WORKERS = 5
DEFAULT_SCAN_LIMIT = 100  # gyertyák száma szimbólumonként - elég a SMA50/MACD stabilizálásához


@dataclass(frozen=True)
class ScanResult:
    symbol: str
    display: str
    last_price: float
    score: ScoreBreakdown


def scan_market(
    symbols: list[tuple[str, str]],
    interval: str,
    progress_callback: Callable[[int, int], None],
    should_stop: threading.Event,
    max_workers: int = DEFAULT_MAX_WORKERS,
    limit: int = DEFAULT_SCAN_LIMIT,
) -> list[ScanResult]:
    """Lefuttatja a pontozást minden (symbol, display) páron.

    A `should_stop` esemény bármikor beállítható másik szálból a megszakításhoz -
    a már folyamatban lévő kérések befejeződnek, de új nem indul.
    """
    total = len(symbols)
    done = 0
    results: list[ScanResult] = []

    def process(symbol_display: tuple[str, str]) -> ScanResult | None:
        symbol, display = symbol_display
        if should_stop.is_set():
            return None
        try:
            df = fetch_klines(symbol, interval, limit)
        except BinanceAPIError as exc:
            logger.debug("Kihagyva (%s): %s", symbol, exc)
            return None

        score = compute_score(df)
        if score is None:
            return None
        return ScanResult(symbol=symbol, display=display, last_price=float(df["close"].iloc[-1]), score=score)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process, sd) for sd in symbols}
        for future in as_completed(futures):
            done += 1
            progress_callback(done, total)
            try:
                result = future.result()
            except Exception:
                logger.exception("Váratlan hiba a piac-szűrés közben")
                continue
            if result is not None:
                results.append(result)

    results.sort(key=lambda r: r.score.percent, reverse=True)
    return results
