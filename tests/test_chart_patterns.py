import pandas as pd

from binance_ta.chart_patterns import detect_chart_patterns, find_pivots


def _zigzag_df(points: list[float], segment_len: int = 5) -> pd.DataFrame:
    """Szakaszonként lineárisan interpolált "cikcakk" árfolyam - a `points`
    lista minden eleme pontosan egyszer jelenik meg egyetlen gyertyaként
    (a szakaszhatáron), monoton emelkedéssel/csökkenéssel a szomszédjai felé,
    így tiszta, egyértelmű pivot-pontokat ad."""
    prices: list[float] = []
    for start, end in zip(points, points[1:]):
        for step in range(segment_len):
            t = step / segment_len
            prices.append(start + (end - start) * t)
    prices.append(points[-1])

    n = len(prices)
    return pd.DataFrame(
        {
            "open_time": pd.date_range("2024-01-01", periods=n, freq="1h"),
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": [100.0] * n,
        }
    )


def _names(df) -> set[str]:
    return {m.name for m in detect_chart_patterns(df)}


def test_find_pivots_detects_single_peak_and_trough():
    df = _zigzag_df([90, 100, 90], segment_len=5)

    pivot_highs, pivot_lows = find_pivots(df)

    assert 5 in pivot_highs
    assert pivot_lows == []


def test_double_top_detected():
    df = _zigzag_df([90, 100, 92, 100.5, 88], segment_len=5)

    matches = detect_chart_patterns(df)
    names = {m.name for m in matches}

    assert "Dupla csúcs (Double Top)" in names
    match = next(m for m in matches if m.name == "Dupla csúcs (Double Top)")
    assert match.bullish is False
    assert match.indices == (5, 10, 15)


def test_double_bottom_detected():
    df = _zigzag_df([110, 100, 108, 99.5, 112], segment_len=5)

    matches = detect_chart_patterns(df)
    names = {m.name for m in matches}

    assert "Dupla alj (Double Bottom)" in names
    match = next(m for m in matches if m.name == "Dupla alj (Double Bottom)")
    assert match.bullish is True


def test_head_and_shoulders_detected():
    df = _zigzag_df([90, 98, 91, 105, 91, 98.5, 88], segment_len=5)

    matches = detect_chart_patterns(df)
    names = {m.name for m in matches}

    assert "Fej-váll alakzat (Head & Shoulders)" in names
    match = next(m for m in matches if m.name == "Fej-váll alakzat (Head & Shoulders)")
    assert match.bullish is False
    assert match.indices == (5, 15, 25)


def test_inverse_head_and_shoulders_detected():
    df = _zigzag_df([110, 102, 109, 95, 109, 101.5, 112], segment_len=5)

    matches = detect_chart_patterns(df)
    names = {m.name for m in matches}

    assert "Fordított fej-váll (Inverse Head & Shoulders)" in names
    match = next(m for m in matches if m.name == "Fordított fej-váll (Inverse Head & Shoulders)")
    assert match.bullish is True


def test_dissimilar_peaks_not_flagged_as_double_top():
    # a masodik csucs sokkal magasabb, mint az elso -> nem "hasonlo magassagu"
    df = _zigzag_df([90, 100, 92, 115, 88], segment_len=5)

    assert "Dupla csúcs (Double Top)" not in _names(df)


def test_shallow_trough_not_flagged_as_double_top():
    # a ket csucs kozott alig van visszaeses -> nem szamit valodi dupla csucsnak
    df = _zigzag_df([90, 100, 99.5, 100.2, 88], segment_len=5)

    assert "Dupla csúcs (Double Top)" not in _names(df)


def test_flat_series_has_no_patterns():
    df = _zigzag_df([100.0, 100.0, 100.0, 100.0], segment_len=5)

    assert detect_chart_patterns(df) == []
