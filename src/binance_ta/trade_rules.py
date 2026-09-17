"""Konfigurálható szabályok szerinti ügylet-kiértékelés.

A tényleges szabálylistát (beépített + felhasználó által létrehozott,
szerkesztett, ki/bekapcsolt) a `rule_config.RuleConfigStore` adja - ez a
modul csak a kiértékelő logikát tartalmazza `kind` szerint elágazva."""

from dataclasses import dataclass

import pandas as pd

from binance_ta.indicators import add_rsi, add_sma
from binance_ta.rule_config import (
    KIND_CUSTOM_COMPARE,
    KIND_EARLY_EXIT,
    KIND_LOSS_THRESHOLD,
    KIND_RSI_EXTREME,
    KIND_TREND,
    RuleConfig,
)
from binance_ta.trade_journal import Trade


@dataclass(frozen=True)
class RuleViolation:
    rule_id: str
    name: str
    message: str
    severity: str


def _row_at_or_before(df: pd.DataFrame, time: pd.Timestamp) -> pd.Series | None:
    idx = int(df["open_time"].searchsorted(time, side="right")) - 1
    if idx < 0 or idx >= len(df):
        return None
    return df.iloc[idx]


def evaluate_trade(df: pd.DataFrame, trade: Trade, rules: list[RuleConfig]) -> list[RuleViolation]:
    """A megadott ügyletet a (bekapcsolt) szabályokhoz hasonlítja.

    `df` a szimbólum historikus OHLCV adata (legalább az ügylet ideje körüli
    tartományt lefedve) - ebből számoljuk ki a belépéskori RSI/SMA értékeket,
    és szükség esetén a kilépés utáni árfolyam-alakulást.
    """
    violations: list[RuleViolation] = []
    if trade.exit_price is None or trade.exit_time is None:
        return violations

    active_rules = [r for r in rules if r.enabled]
    if not active_rules:
        return violations

    work = df.copy()

    rsi_periods = {r.params.get("rsi_period", 14) for r in active_rules if r.kind == KIND_RSI_EXTREME}
    rsi_periods |= {
        r.params.get("period", 14) for r in active_rules
        if r.kind == KIND_CUSTOM_COMPARE and r.params.get("metric") == "rsi"
    }
    sma_periods = {r.params.get("sma_period", 50) for r in active_rules if r.kind == KIND_TREND}
    sma_periods |= {
        r.params.get("period", 50) for r in active_rules
        if r.kind == KIND_CUSTOM_COMPARE and r.params.get("metric") == "price_vs_sma"
    }

    for period in rsi_periods:
        work = add_rsi(work, period=period)
    for period in sma_periods:
        work = add_sma(work, period=period)

    entry_row = _row_at_or_before(work, pd.Timestamp(trade.entry_time))
    pnl = trade.pnl_percent

    for rule in active_rules:
        message = _evaluate_single_rule(rule, work, entry_row, trade, pnl)
        if message:
            violations.append(RuleViolation(rule.id, rule.name, message, rule.severity))

    return violations


def _evaluate_single_rule(rule: RuleConfig, work: pd.DataFrame, entry_row, trade: Trade, pnl: float | None) -> str | None:
    if rule.kind == KIND_TREND:
        return _eval_trend(rule, entry_row, trade)
    if rule.kind == KIND_RSI_EXTREME:
        return _eval_rsi_extreme(rule, entry_row, trade)
    if rule.kind == KIND_LOSS_THRESHOLD:
        return _eval_loss_threshold(rule, pnl)
    if rule.kind == KIND_EARLY_EXIT:
        return _eval_early_exit(rule, work, trade, pnl)
    if rule.kind == KIND_CUSTOM_COMPARE:
        return _eval_custom_compare(rule, entry_row, trade)
    return None


def _eval_trend(rule: RuleConfig, entry_row, trade: Trade) -> str | None:
    period = rule.params.get("sma_period", 50)
    col = f"sma_{period}"
    if entry_row is None or pd.isna(entry_row.get(col)):
        return None
    price = entry_row["close"]
    sma = entry_row[col]
    if trade.direction == "long" and price < sma:
        return f"Trend ellen léptél be: az ár a SMA{period} alatt volt vételkor."
    if trade.direction == "short" and price > sma:
        return f"Trend ellen léptél be: az ár a SMA{period} fölött volt shortoláskor."
    return None


def _eval_rsi_extreme(rule: RuleConfig, entry_row, trade: Trade) -> str | None:
    period = rule.params.get("rsi_period", 14)
    overbought = rule.params.get("overbought", 70)
    oversold = rule.params.get("oversold", 30)
    col = f"rsi_{period}"
    if entry_row is None or pd.isna(entry_row.get(col)):
        return None
    rsi = entry_row[col]
    if trade.direction == "long" and rsi > overbought:
        return f"Túlvett állapotban (RSI={rsi:.0f}) léptél be."
    if trade.direction == "short" and rsi < oversold:
        return f"Túladott állapotban (RSI={rsi:.0f}) shortoltál."
    return None


def _eval_loss_threshold(rule: RuleConfig, pnl: float | None) -> str | None:
    threshold = rule.params.get("loss_percent", -5.0)
    if pnl is not None and pnl < threshold:
        return f"Nagy veszteséget ({pnl:.1f}%) hagytál futni - érdemes lett volna stop-losst használni."
    return None


def _eval_early_exit(rule: RuleConfig, work: pd.DataFrame, trade: Trade, pnl: float | None) -> str | None:
    if pnl is None or pnl <= 0:
        return None
    lookahead_n = rule.params.get("lookahead_candles", 20)
    min_missed = rule.params.get("min_missed_percent", 2.0)
    exit_idx = int(work["open_time"].searchsorted(pd.Timestamp(trade.exit_time), side="right"))
    lookahead = work.iloc[exit_idx: exit_idx + lookahead_n]
    if lookahead.empty:
        return None
    if trade.direction == "long":
        missed = (lookahead["high"].max() - trade.exit_price) / trade.exit_price * 100
    else:
        missed = (trade.exit_price - lookahead["low"].min()) / trade.exit_price * 100
    if missed > max(pnl * 1.5, min_missed):
        return f"Korán zártál: kilépés után még kb. {missed:.1f}%-ot mozgott volna kedvezően."
    return None


def _eval_custom_compare(rule: RuleConfig, entry_row, trade: Trade) -> str | None:
    applies_to = rule.params.get("applies_to", "both")
    if applies_to != "both" and applies_to != trade.direction:
        return None
    if entry_row is None:
        return None

    metric = rule.params.get("metric", "rsi")
    period = rule.params.get("period", 14)
    comparator = rule.params.get("comparator", "above")
    threshold = rule.params.get("threshold", 0.0)

    if metric == "rsi":
        col = f"rsi_{period}"
        if pd.isna(entry_row.get(col)):
            return None
        value = entry_row[col]
        value_text = f"RSI({period})={value:.1f}"
    else:  # price_vs_sma
        col = f"sma_{period}"
        if pd.isna(entry_row.get(col)):
            return None
        value = (entry_row["close"] / entry_row[col] - 1) * 100
        value_text = f"ár SMA{period}-től való távolsága={value:.1f}%"

    fired = value > threshold if comparator == "above" else value < threshold
    if not fired:
        return None

    if rule.description:
        return rule.description
    comparator_text = "nagyobb" if comparator == "above" else "kisebb"
    return f"{rule.name}: {value_text}, ami {comparator_text}, mint a küszöb ({threshold})."
