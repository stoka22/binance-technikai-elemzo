import numpy as np
import pandas as pd

from binance_ta.indicators import add_rsi, add_sma
from binance_ta.rule_config import SEVERITY_VIOLATION, SEVERITY_WARNING, RuleConfig, _default_rules
from binance_ta.trade_journal import Trade
from binance_ta.trade_rules import evaluate_trade


def _make_df(closes, start="2024-01-01", freq="1h") -> pd.DataFrame:
    n = len(closes)
    closes = pd.Series(closes, dtype=float)
    times = pd.date_range(start, periods=n, freq=freq)
    return pd.DataFrame(
        {
            "open_time": times,
            "open": closes.shift(1).fillna(closes.iloc[0]),
            "high": closes * 1.001,
            "low": closes * 0.999,
            "close": closes,
            "volume": [100.0] * n,
        }
    )


def _rule_ids(violations) -> set[str]:
    return {v.rule_id for v in violations}


def test_long_entry_against_downtrend_flags_trend_rule():
    closes = [100.0 - i * 0.6 for i in range(90)]
    df = _make_df(closes)
    trade = Trade(
        symbol="TESTUSDT", interval="1h", direction="long",
        entry_time=df["open_time"].iloc[-1].isoformat(), entry_price=closes[-1],
        exit_time=df["open_time"].iloc[-1].isoformat(), exit_price=closes[-1] * 1.001,
    )

    violations = evaluate_trade(df, trade, _default_rules())

    assert "builtin_trend" in _rule_ids(violations)
    trend_violation = next(v for v in violations if v.rule_id == "builtin_trend")
    assert trend_violation.severity == SEVERITY_WARNING


def test_long_entry_while_overbought_flags_rsi_chase_rule():
    closes = [100.0 + i * 0.6 for i in range(90)]
    df = _make_df(closes)
    trade = Trade(
        symbol="TESTUSDT", interval="1h", direction="long",
        entry_time=df["open_time"].iloc[-1].isoformat(), entry_price=closes[-1],
        exit_time=df["open_time"].iloc[-1].isoformat(), exit_price=closes[-1] * 1.001,
    )

    violations = evaluate_trade(df, trade, _default_rules())

    assert "builtin_rsi_extreme" in _rule_ids(violations)
    assert "builtin_trend" not in _rule_ids(violations)  # emelkedő trendben a long NEM trend-ellenes


def test_large_loss_flags_no_stop_loss_rule():
    closes = [100.0 + (i % 3) * 0.05 for i in range(90)]  # kb. semleges, apró ingadozás
    df = _make_df(closes)
    entry_price = closes[-1]
    trade = Trade(
        symbol="TESTUSDT", interval="1h", direction="long",
        entry_time=df["open_time"].iloc[-1].isoformat(), entry_price=entry_price,
        exit_time=df["open_time"].iloc[-1].isoformat(), exit_price=entry_price * 0.90,  # -10%
    )

    violations = evaluate_trade(df, trade, _default_rules())

    assert "builtin_no_stop_loss" in _rule_ids(violations)
    loss_violation = next(v for v in violations if v.rule_id == "builtin_no_stop_loss")
    assert loss_violation.severity == SEVERITY_VIOLATION


def test_early_exit_flags_when_price_continues_favorably_afterwards():
    flat = [100.0 + (i % 3) * 0.05 for i in range(90)]
    continuation = [flat[-1] * (1 + 0.01 * i) for i in range(1, 25)]  # eros folytatodo emelkedes
    closes = flat + continuation
    df = _make_df(closes)

    entry_idx = 89
    exit_idx = 90  # egy gyertyaval a belepes utan, minimalis nyereseggel zarva
    trade = Trade(
        symbol="TESTUSDT", interval="1h", direction="long",
        entry_time=df["open_time"].iloc[entry_idx].isoformat(), entry_price=closes[entry_idx],
        exit_time=df["open_time"].iloc[exit_idx].isoformat(), exit_price=closes[exit_idx],
    )

    violations = evaluate_trade(df, trade, _default_rules())

    assert "builtin_early_exit" in _rule_ids(violations)


def test_open_trade_without_exit_has_no_violations():
    closes = [100.0 - i * 0.6 for i in range(90)]
    df = _make_df(closes)
    trade = Trade(
        symbol="TESTUSDT", interval="1h", direction="long",
        entry_time=df["open_time"].iloc[-1].isoformat(), entry_price=closes[-1],
    )

    assert evaluate_trade(df, trade, _default_rules()) == []


def test_clean_trade_has_no_violations():
    # apró, driftmentes random ingadozás egy szint körül - ez ad valódi
    # ki-be mozgást (az RSI ténylegesen bejárja a semleges sávot is), és a
    # kis amplitúdó miatt sem a trend, sem a "korai zárás" szabály nem
    # aktiválódhat véletlenül a keresett ponton.
    rng = np.random.default_rng(7)
    closes = [100.0 + n for n in rng.normal(0, 0.2, size=150)]
    df = _make_df(closes)

    probe = add_sma(add_rsi(df.copy(), 14), 50)
    candidate_idx = next(
        i for i in range(60, 150)
        if 45 <= probe["rsi_14"].iloc[i] <= 55 and probe["close"].iloc[i] > probe["sma_50"].iloc[i]
    )

    entry_price = closes[candidate_idx]
    entry_time = df["open_time"].iloc[candidate_idx].isoformat()
    trade = Trade(
        symbol="TESTUSDT", interval="1h", direction="long",
        entry_time=entry_time, entry_price=entry_price,
        exit_time=entry_time, exit_price=entry_price * 1.001,
    )

    assert evaluate_trade(df, trade, _default_rules()) == []


def test_disabled_rule_does_not_fire():
    closes = [100.0 - i * 0.6 for i in range(90)]
    df = _make_df(closes)
    trade = Trade(
        symbol="TESTUSDT", interval="1h", direction="long",
        entry_time=df["open_time"].iloc[-1].isoformat(), entry_price=closes[-1],
        exit_time=df["open_time"].iloc[-1].isoformat(), exit_price=closes[-1] * 1.001,
    )

    rules = _default_rules()
    for rule in rules:
        if rule.id == "builtin_trend":
            rule.enabled = False

    violations = evaluate_trade(df, trade, rules)

    assert "builtin_trend" not in _rule_ids(violations)


def test_custom_rule_with_adjusted_parameters_changes_trigger_point():
    closes = [100.0 - i * 0.6 for i in range(90)]
    df = _make_df(closes)
    trade = Trade(
        symbol="TESTUSDT", interval="1h", direction="long",
        entry_time=df["open_time"].iloc[-1].isoformat(), entry_price=closes[-1],
        exit_time=df["open_time"].iloc[-1].isoformat(), exit_price=closes[-1] * 1.001,
    )

    # a beepitett trend szabaly SMA200-ra allitva mar biztosan nem sertodik
    # meg (nincs eleg elotortenet SMA200-hoz 90 gyertyaval)
    rules = _default_rules()
    for rule in rules:
        if rule.id == "builtin_trend":
            rule.params["sma_period"] = 200

    violations = evaluate_trade(df, trade, rules)

    assert "builtin_trend" not in _rule_ids(violations)


def test_custom_compare_rule_fires_for_matching_direction_only():
    closes = [100.0 + i * 0.6 for i in range(90)]  # eros emelkedes -> magas RSI
    df = _make_df(closes)
    long_trade = Trade(
        symbol="TESTUSDT", interval="1h", direction="long",
        entry_time=df["open_time"].iloc[-1].isoformat(), entry_price=closes[-1],
        exit_time=df["open_time"].iloc[-1].isoformat(), exit_price=closes[-1] * 1.001,
    )
    short_trade = Trade(
        symbol="TESTUSDT", interval="1h", direction="short",
        entry_time=df["open_time"].iloc[-1].isoformat(), entry_price=closes[-1],
        exit_time=df["open_time"].iloc[-1].isoformat(), exit_price=closes[-1] * 0.999,
    )

    custom_rule = RuleConfig(
        id="custom_1", name="Extra magas RSI", kind="custom_compare",
        severity=SEVERITY_WARNING, enabled=True, builtin=False,
        params={"metric": "rsi", "period": 14, "comparator": "above", "threshold": 80.0, "applies_to": "long"},
    )

    long_violations = evaluate_trade(df, long_trade, [custom_rule])
    short_violations = evaluate_trade(df, short_trade, [custom_rule])

    assert "custom_1" in _rule_ids(long_violations)
    assert "custom_1" not in _rule_ids(short_violations)  # applies_to="long", short-ra nem ervenyes


def test_custom_compare_price_vs_sma_metric():
    closes = [100.0 - i * 0.6 for i in range(90)]  # ar SMA20 alatt
    df = _make_df(closes)
    trade = Trade(
        symbol="TESTUSDT", interval="1h", direction="long",
        entry_time=df["open_time"].iloc[-1].isoformat(), entry_price=closes[-1],
        exit_time=df["open_time"].iloc[-1].isoformat(), exit_price=closes[-1] * 1.001,
    )

    custom_rule = RuleConfig(
        id="custom_2", name="Ár messze SMA20 alatt", kind="custom_compare",
        severity=SEVERITY_VIOLATION, enabled=True, builtin=False,
        params={"metric": "price_vs_sma", "period": 20, "comparator": "below", "threshold": -1.0, "applies_to": "both"},
    )

    violations = evaluate_trade(df, trade, [custom_rule])

    assert "custom_2" in _rule_ids(violations)
    assert violations[0].severity == SEVERITY_VIOLATION


def test_empty_rule_list_yields_no_violations():
    closes = [100.0 - i * 0.6 for i in range(90)]
    df = _make_df(closes)
    trade = Trade(
        symbol="TESTUSDT", interval="1h", direction="long",
        entry_time=df["open_time"].iloc[-1].isoformat(), entry_price=closes[-1],
        exit_time=df["open_time"].iloc[-1].isoformat(), exit_price=closes[-1] * 0.5,  # nagy veszteseg is
    )

    assert evaluate_trade(df, trade, []) == []
