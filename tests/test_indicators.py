import pandas as pd
import pytest

from binance_ta.indicators import add_bollinger_bands, add_macd, add_rsi, add_sma


def test_add_sma_basic():
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0]})
    result = add_sma(df.copy(), period=2)

    assert pd.isna(result["sma_2"].iloc[0])
    assert result["sma_2"].iloc[1:].tolist() == pytest.approx([1.5, 2.5, 3.5, 4.5])


def test_add_rsi_all_gains_approaches_100():
    df = pd.DataFrame({"close": [float(x) for x in range(1, 21)]})  # monoton növekvő
    result = add_rsi(df.copy(), period=14)

    assert result["rsi_14"].iloc[-1] == pytest.approx(100.0)


def test_add_rsi_all_losses_approaches_0():
    df = pd.DataFrame({"close": [float(x) for x in range(20, 0, -1)]})  # monoton csökkenő
    result = add_rsi(df.copy(), period=14)

    assert result["rsi_14"].iloc[-1] == pytest.approx(0.0)


def test_add_macd_columns_present():
    df = pd.DataFrame({"close": [float(x) for x in range(1, 60)]})
    result = add_macd(df.copy())

    assert {"macd", "macd_signal", "macd_hist"}.issubset(result.columns)
    expected_hist = (result["macd"] - result["macd_signal"]).to_numpy()
    assert result["macd_hist"].to_numpy() == pytest.approx(expected_hist)


def test_add_bollinger_bands_ordering():
    df = pd.DataFrame({"close": [10, 12, 11, 13, 15, 14, 16, 18, 17, 19]})
    result = add_bollinger_bands(df.copy(), period=5)

    valid = result.dropna(subset=["bb_upper_5", "bb_lower_5"])
    assert not valid.empty
    assert (valid["bb_upper_5"] >= valid["bb_mid_5"]).all()
    assert (valid["bb_mid_5"] >= valid["bb_lower_5"]).all()
