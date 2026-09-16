"""Folytonos technikai pontszám (-100% .. +100%) egy szimbólumra.

Ez NEM ár-előrejelzés és NEM befektetési tanács - pusztán azt mutatja meg,
hogy a klasszikus technikai jelzések (RSI, MACD, SMA-trend, Bollinger-pozíció)
éppen mennyire mutatnak egységesen egy irányba, a TradingView "Technical
Rating"-jéhez hasonló (de folytonos, nem +1/0/-1 count-olós) logikával.

A 4 komponens mindegyike -1..+1 tartományba van normalizálva, ezek átlaga
adja az alap-pontszámot, amit a volumen (átlaghoz viszonyítva) enyhén
felerősít vagy tompít - erős kilengés gyenge volumen mellett kevésbé
megbízható jelzésnek számít.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from binance_ta.indicators import add_bollinger_bands, add_macd, add_rsi, add_sma

MIN_ROWS_REQUIRED = 60  # SMA50 + MACD stabilizálódásához kell ennyi gyertya


@dataclass(frozen=True)
class ScoreBreakdown:
    """A négy komponens pontszáma (-1..+1) + a végső, súlyozott eredmény."""

    rsi: float
    macd: float
    trend: float
    bollinger: float
    volume_factor: float
    composite: float  # -1..+1

    @property
    def percent(self) -> float:
        """0-100%: 50% = semleges, 100% = maximálisan bullish, 0% = maximálisan bearish."""
        return (self.composite + 1) / 2 * 100


def _clip(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def compute_score(df: pd.DataFrame) -> ScoreBreakdown | None:
    """Kiszámolja az utolsó gyertyára vonatkozó összetett pontszámot.

    Returns:
        None, ha nincs elég adat (túl rövid előtörténet) a stabil számításhoz.
    """
    if len(df) < MIN_ROWS_REQUIRED:
        return None

    work = df.copy()
    work = add_rsi(work, period=14)
    work = add_macd(work)
    work = add_sma(work, period=20)
    work = add_sma(work, period=50)
    work = add_bollinger_bands(work, period=20)

    last = work.iloc[-1]
    if last[["rsi_14", "macd_hist", "sma_20", "sma_50", "bb_upper_20", "bb_lower_20"]].isna().any():
        return None

    close = last["close"]

    # 1) RSI: 30 alatt túladott (bullish), 70 fölött túlvett (bearish), 50 semleges.
    rsi_score = _clip((50 - last["rsi_14"]) / 30)

    # 2) MACD hisztogram, a saját szórásához (utolsó 50 gyertya) viszonyítva -
    # így minden szimbólumra összemérhető, függetlenül az árszinttől.
    hist_std = work["macd_hist"].tail(50).std()
    macd_score = _clip(last["macd_hist"] / (2 * hist_std)) if hist_std and not np.isnan(hist_std) else 0.0

    # 3) Trend: ár távolsága a SMA20-tól (%), megerősítve, ha a SMA20 a SMA50 fölött van.
    trend_score = _clip((close / last["sma_20"] - 1) * 20)
    if last["sma_20"] < last["sma_50"]:
        trend_score = _clip(trend_score - 0.2)
    else:
        trend_score = _clip(trend_score + 0.2)

    # 4) Bollinger-pozíció: az alsó sávnál bullish (visszapattanás esélye), a felsőnél bearish.
    band_width = last["bb_upper_20"] - last["bb_lower_20"]
    if band_width > 0:
        position = (close - last["bb_lower_20"]) / band_width  # ~0..1
        bollinger_score = _clip((0.5 - position) * 2)
    else:
        bollinger_score = 0.0

    composite = (rsi_score + macd_score + trend_score + bollinger_score) / 4

    # Volumen-megerősítés: átlag feletti volumen felerősíti, átlag alatti tompítja
    # a jelzést (a mozgás "hitelességét" méri, nem ad önálló irányt).
    avg_volume = work["volume"].tail(20).mean()
    volume_factor = 1.0
    if avg_volume and not np.isnan(avg_volume) and avg_volume > 0:
        ratio = last["volume"] / avg_volume
        volume_factor = _clip(0.8 + 0.2 * ratio, 0.7, 1.3)
        composite = _clip(composite * volume_factor)

    return ScoreBreakdown(
        rsi=rsi_score, macd=macd_score, trend=trend_score, bollinger=bollinger_score,
        volume_factor=volume_factor, composite=composite,
    )
