"""Klasszikus, széles körben tanított kereskedési alapszabályok, amikhez a
gyakorló-módban rögzített ügyleteket automatikusan hasonlítjuk, hogy
látszódjanak az ismétlődő hibák - ezek alapján lehet később saját,
automata szűrő-szabályokat felállítani (pl. a Piac-szűrőben).

Ez nem kimerítő szabálykönyv, hanem néhány olyan, gyakorlatilag minden
tankönyvben/oktatóanyagban megjelenő alapelv, amit objektíven, a historikus
adatból ellenőrizni lehet."""

from dataclasses import dataclass

import pandas as pd

from binance_ta.indicators import add_rsi, add_sma
from binance_ta.trade_journal import Trade

RSI_PERIOD = 14
TREND_SMA_PERIOD = 50
LARGE_LOSS_THRESHOLD_PERCENT = -5.0
EARLY_EXIT_LOOKAHEAD_CANDLES = 20
EARLY_EXIT_MIN_MISSED_PERCENT = 2.0

RULEBOOK: dict[str, str] = {
    "trend": (
        "Ne kereskedj a fő trend ellen.\n\n"
        "Ha az ár a hosszabb távú mozgóátlag (itt SMA50) alatt van, az "
        "inkább csökkenő trendet jelez - long pozíciót ilyenkor nyitni "
        "a trenddel szembemegy. (Fordítva ugyanez shortra.)"
    ),
    "rsi_chase": (
        "Ne lépj be már túlvett/túladott állapotban.\n\n"
        "Ha az RSI(14) már 70 fölött van, a felfelé mozgás nagy része "
        "valószínűleg megtörtént - a késői belépés korrekció kockázatát "
        "hordozza. Ugyanez fordítva: 30 alatti RSI-nél shortolni."
    ),
    "no_stop_loss": (
        "Vágd rövidre a veszteséget (használj stop-losst).\n\n"
        "Ha egy pozíció nagy mínuszba fordul, és nincs előre meghatározott "
        "kiszállási szint, könnyen tovább nő a veszteség. A legtöbb "
        "kereskedési alapszabály szerint egy ügylet vesztesége eleve "
        "korlátozva legyen (pl. néhány százalékra)."
    ),
    "early_exit": (
        "Hagyd futni a nyereséget.\n\n"
        "Ha egy nyerő pozíciót nagyon korán zársz le, és az ár utána "
        "sokkal tovább mozgott a kedvező irányba, azt jelezheti, hogy "
        "túl korán realizáltad a nyereséget."
    ),
}


@dataclass(frozen=True)
class RuleViolation:
    rule_id: str
    message: str


def _row_at_or_before(df: pd.DataFrame, time: pd.Timestamp) -> pd.Series | None:
    idx = int(df["open_time"].searchsorted(time, side="right")) - 1
    if idx < 0 or idx >= len(df):
        return None
    return df.iloc[idx]


def evaluate_trade(df: pd.DataFrame, trade: Trade) -> list[RuleViolation]:
    """A megadott ügyletet a RULEBOOK szabályaihoz hasonlítja.

    `df` a szimbólum historikus OHLCV adata (legalább az ügylet ideje körüli
    tartományt lefedve) - ebből számoljuk ki a belépéskori RSI/SMA értékeket,
    és szükség esetén a kilépés utáni árfolyam-alakulást.
    """
    violations: list[RuleViolation] = []
    if trade.exit_price is None or trade.exit_time is None:
        return violations

    work = df.copy()
    work = add_rsi(work, RSI_PERIOD)
    work = add_sma(work, TREND_SMA_PERIOD)

    entry_row = _row_at_or_before(work, pd.Timestamp(trade.entry_time))
    rsi_col = f"rsi_{RSI_PERIOD}"
    sma_col = f"sma_{TREND_SMA_PERIOD}"

    if entry_row is not None and pd.notna(entry_row.get(rsi_col)) and pd.notna(entry_row.get(sma_col)):
        price = entry_row["close"]
        rsi = entry_row[rsi_col]
        sma = entry_row[sma_col]

        if trade.direction == "long":
            if price < sma:
                violations.append(RuleViolation("trend", "Trend ellen léptél be: az ár a SMA50 alatt volt vételkor."))
            if rsi > 70:
                violations.append(RuleViolation("rsi_chase", f"Túlvett állapotban (RSI={rsi:.0f}) léptél be."))
        else:
            if price > sma:
                violations.append(RuleViolation("trend", "Trend ellen léptél be: az ár a SMA50 fölött volt shortoláskor."))
            if rsi < 30:
                violations.append(RuleViolation("rsi_chase", f"Túladott állapotban (RSI={rsi:.0f}) shortoltál."))

    pnl = trade.pnl_percent
    if pnl is not None and pnl < LARGE_LOSS_THRESHOLD_PERCENT:
        violations.append(
            RuleViolation("no_stop_loss", f"Nagy veszteséget ({pnl:.1f}%) hagytál futni - érdemes lett volna stop-losst használni.")
        )

    if pnl is not None and pnl > 0:
        exit_idx = int(work["open_time"].searchsorted(pd.Timestamp(trade.exit_time), side="right"))
        lookahead = work.iloc[exit_idx: exit_idx + EARLY_EXIT_LOOKAHEAD_CANDLES]
        if not lookahead.empty:
            if trade.direction == "long":
                missed_percent = (lookahead["high"].max() - trade.exit_price) / trade.exit_price * 100
            else:
                missed_percent = (trade.exit_price - lookahead["low"].min()) / trade.exit_price * 100
            if missed_percent > max(pnl * 1.5, EARLY_EXIT_MIN_MISSED_PERCENT):
                violations.append(
                    RuleViolation("early_exit", f"Korán zártál: kilépés után még kb. {missed_percent:.1f}%-ot mozgott volna kedvezően.")
                )

    return violations
