import pandas as pd

from binance_ta.candlestick_patterns import detect_patterns, dominant_pattern_per_index


def _df_from_rows(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    n = len(rows)
    return pd.DataFrame(
        {
            "open_time": pd.date_range("2024-01-01", periods=n, freq="1h"),
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
            "volume": [100.0] * n,
        }
    )


def _names_at(df, i) -> set[str]:
    return {m.name for m in detect_patterns(df) if m.index == i}


def test_doji_detected_when_open_close_almost_equal():
    rows = [(100.0, 105.0, 95.0, 100.2)]
    df = _df_from_rows(rows)

    assert "Doji" in _names_at(df, 0)


def test_no_doji_for_large_body():
    rows = [(100.0, 110.0, 99.0, 108.0)]
    df = _df_from_rows(rows)

    assert "Doji" not in _names_at(df, 0)


def test_hammer_after_downtrend():
    # 5 gyertyas csokkeno kontextus, majd egy hosszu also lengesu, kis testu gyertya
    downtrend = [(100.0 - i, 100.5 - i, 99.0 - i, 99.5 - i) for i in range(5)]
    hammer = (94.5, 94.8, 90.0, 94.6)  # kicsi test, hosszu also arnyek, alig felso
    df = _df_from_rows(downtrend + [hammer])

    assert "Hammer (Kalapács)" in _names_at(df, 5)


def test_hanging_man_after_uptrend():
    uptrend = [(100.0 + i, 100.5 + i, 99.0 + i, 100.4 + i) for i in range(5)]
    same_shape_as_hammer = (104.5, 104.8, 100.0, 104.6)
    df = _df_from_rows(uptrend + [same_shape_as_hammer])

    assert "Hanging Man (Akasztott ember)" in _names_at(df, 5)


def test_bullish_engulfing():
    rows = [
        (100.0, 100.5, 97.0, 97.5),  # csokkeno (bearish) gyertya
        (97.0, 102.0, 96.5, 101.5),  # emelkedo gyertya, teljesen befedi az elozot
    ]
    df = _df_from_rows(rows)

    assert "Bullish Engulfing (Elnyelő minta)" in _names_at(df, 1)


def test_bearish_engulfing():
    rows = [
        (97.0, 100.5, 96.5, 100.0),  # emelkedo gyertya
        (100.5, 101.0, 95.0, 95.5),  # csokkeno gyertya, teljesen befedi az elozot
    ]
    df = _df_from_rows(rows)

    assert "Bearish Engulfing (Elnyelő minta)" in _names_at(df, 1)


def test_bullish_harami():
    rows = [
        (105.0, 105.5, 95.0, 96.0),  # nagy csokkeno gyertya
        (99.0, 101.0, 98.5, 100.5),  # kicsi emelkedo gyertya, az elozo testen belul
    ]
    df = _df_from_rows(rows)

    assert "Bullish Harami" in _names_at(df, 1)


def test_morning_star():
    rows = [
        (105.0, 105.5, 95.0, 96.0),  # nagy csokkeno
        (95.5, 96.0, 94.5, 95.3),  # kicsi, bizonytalan
        (96.5, 103.0, 96.0, 102.5),  # nagy emelkedo, visszamegy az elso test folebe
    ]
    df = _df_from_rows(rows)

    assert "Morning Star (Hajnalcsillag)" in _names_at(df, 2)


def test_evening_star():
    rows = [
        (96.0, 105.5, 95.5, 105.0),  # nagy emelkedo
        (105.3, 105.8, 104.5, 105.1),  # kicsi, bizonytalan
        (104.5, 105.0, 98.0, 98.5),  # nagy csokkeno, visszamegy az elso test alá
    ]
    df = _df_from_rows(rows)

    assert "Evening Star (Alkonycsillag)" in _names_at(df, 2)


def test_three_white_soldiers():
    rows = [
        (100.0, 104.3, 99.7, 104.0),  # test=4.0, lengés=4.6 (arány ~0.87)
        (103.0, 107.3, 102.7, 107.0),  # test=4.0, lengés=4.6
        (106.0, 111.2, 105.8, 111.0),  # test=5.0, lengés=5.4
    ]
    df = _df_from_rows(rows)

    assert "Three White Soldiers (Három fehér katona)" in _names_at(df, 2)


def test_three_black_crows():
    rows = [
        (111.0, 111.3, 106.7, 107.0),  # test=4.0, lengés=4.6
        (108.0, 108.3, 103.7, 104.0),  # test=4.0, lengés=4.6
        (105.0, 105.2, 99.8, 100.0),  # test=5.0, lengés=5.4
    ]
    df = _df_from_rows(rows)

    assert "Three Black Crows (Három fekete varjú)" in _names_at(df, 2)


def test_bullish_marubozu():
    rows = [(100.0, 110.0, 100.0, 110.0)]  # nyito=low, zaro=high, nincs lenges
    df = _df_from_rows(rows)

    assert "Bullish Marubozu" in _names_at(df, 0)


def test_no_pattern_for_ordinary_candle():
    rows = [(100.0, 102.0, 99.5, 101.0)]
    df = _df_from_rows(rows)

    assert detect_patterns(df) == []


def test_dominant_pattern_per_index_picks_first_matcher_order():
    # egy Doji, ami egyben Harami is lehet - mindket minta illik ra
    rows = [
        (105.0, 105.5, 95.0, 96.0),  # nagy csokkeno
        (100.0, 100.3, 99.8, 100.05),  # kicsi test (doji-szeru), az elozo testen belul (harami)
    ]
    df = _df_from_rows(rows)

    matches = detect_patterns(df)
    dominant = dominant_pattern_per_index(matches)

    assert 1 in dominant
    # a matcher lista sorrendje szerint a Harami elobb van, mint a Doji
    assert dominant[1].name == "Bullish Harami"


def test_insignificant_pattern_is_filtered_in_quiet_market():
    # 20 gyertyas nagyon csendes, apro lengesu szakasz, majd egy technikailag
    # "engulfing alaku" par, de ami a csendes szakaszhoz kepest sem jelentos
    quiet = [(100.0 + (i % 2) * 0.05, 100.15 + (i % 2) * 0.05, 99.95 + (i % 2) * 0.05, 100.05 + (i % 2) * 0.05) for i in range(20)]
    tiny_bearish = (100.05, 100.07, 100.01, 100.02)  # test = 0.03 (jóval a csendes atlag alatt)
    tiny_bullish_engulf = (100.01, 100.09, 100.00, 100.06)  # test = 0.05, technikailag elnyeli az elozot, de apro
    df = _df_from_rows(quiet + [tiny_bearish, tiny_bullish_engulf])

    assert "Bullish Engulfing (Elnyelő minta)" not in _names_at(df, len(df) - 1)


def test_significant_pattern_still_detected_in_quiet_market():
    quiet = [(100.0 + (i % 2) * 0.05, 100.15 + (i % 2) * 0.05, 99.95 + (i % 2) * 0.05, 100.05 + (i % 2) * 0.05) for i in range(20)]
    real_bearish = (101.0, 101.2, 98.0, 98.5)  # jelentős, a csendes szakaszhoz kepest is nagy gyertya
    real_bullish_engulf = (98.0, 102.5, 97.8, 102.0)
    df = _df_from_rows(quiet + [real_bearish, real_bullish_engulf])

    assert "Bullish Engulfing (Elnyelő minta)" in _names_at(df, len(df) - 1)
