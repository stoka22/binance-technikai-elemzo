import numpy as np
import pandas as pd

from binance_ta.scoring import MIN_ROWS_REQUIRED, compute_score


def _make_df(closes, volumes=None) -> pd.DataFrame:
    n = len(closes)
    closes = pd.Series(closes, dtype=float)
    opens = closes.shift(1).fillna(closes.iloc[0])
    volumes = pd.Series(volumes if volumes is not None else [100.0] * n)
    return pd.DataFrame(
        {
            "open_time": pd.date_range("2024-01-01", periods=n, freq="1h"),
            "open": opens,
            "high": closes * 1.001,
            "low": closes * 0.999,
            "close": closes,
            "volume": volumes,
        }
    )


def test_returns_none_for_insufficient_data():
    df = _make_df([100.0] * (MIN_ROWS_REQUIRED - 1))
    assert compute_score(df) is None


def test_flat_market_is_near_neutral():
    rng = np.random.default_rng(42)
    closes = [100.0 + n for n in rng.normal(0, 0.15, size=90)]
    df = _make_df(closes)

    result = compute_score(df)

    assert result is not None
    assert 35 <= result.percent <= 65


def test_strong_decline_flags_oversold_and_bearish_trend():
    closes = [100.0 - i * 0.8 for i in range(90)]
    df = _make_df(closes)

    result = compute_score(df)

    assert result is not None
    assert result.rsi > 0.3, "hosszú esés után az RSI túladott -> bullish (mean-reversion) jelzés"
    assert result.trend < 0, "az ár a mozgóátlagok alatt van, csökkenő trendben"
    assert result.macd < 0, "lefelé mutató momentum"


def test_strong_rally_flags_overbought_and_bullish_trend():
    closes = [100.0 + i * 0.8 for i in range(90)]
    df = _make_df(closes)

    result = compute_score(df)

    assert result is not None
    assert result.rsi < -0.3, "hosszú emelkedés után az RSI túlvett -> bearish (mean-reversion) jelzés"
    assert result.trend > 0, "az ár a mozgóátlagok fölött van, emelkedő trendben"
    assert result.macd > 0, "felfelé mutató momentum"


def test_percent_stays_within_bounds():
    closes = [100.0 - i * 0.8 for i in range(90)]
    df = _make_df(closes)

    result = compute_score(df)

    assert result is not None
    assert 0 <= result.percent <= 100


def test_high_volume_amplifies_composite_magnitude():
    closes = [100.0 - i * 0.8 for i in range(90)]
    low_volume_df = _make_df(closes, volumes=[100.0] * 89 + [100.0])
    high_volume_df = _make_df(closes, volumes=[100.0] * 89 + [500.0])

    low = compute_score(low_volume_df)
    high = compute_score(high_volume_df)

    assert low is not None and high is not None
    assert abs(high.composite) >= abs(low.composite)
