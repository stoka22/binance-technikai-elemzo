"""Pivot-alapú chart-alakzat (chart pattern) felismerés.

Először megkeressük a helyi csúcsokat/mélypontokat (pivot pontok, "fraktál"
módszerrel: egy gyertya akkor pivot-csúcs, ha a magassága a szomszédos N
gyertyához képest a legmagasabb), majd ezekre geometriai szabályokat
illesztünk - ahogy pl. az Autochartist/TrendSpider is teszi, NEM gépi
tanulással.
"""

from dataclasses import dataclass

import pandas as pd

PIVOT_LOOKBACK = 3  # ennyi gyertyát nézünk mindkét irányban a pivot-kereséshez
PEAK_SIMILARITY_TOLERANCE = 0.02  # két csúcs/mélypont "hasonló magasságú", ha ezen belül van
TROUGH_DEPTH_RATIO = 0.02  # a köztes mélypont/csúcs legalább ennyivel térjen el
SHOULDER_SIMILARITY_TOLERANCE = 0.035  # a fej-váll "vállai" ennél lazábban hasonlíthatnak
HEAD_PROMINENCE_RATIO = 0.015  # a "fej" legalább ennyivel emelkedjen ki a vállak fölé/alá


@dataclass(frozen=True)
class ChartPatternMatch:
    indices: tuple[int, ...]  # az alakzatot alkotó pivot-pontok indexei, időrendben
    prices: tuple[float, ...]  # a megfelelő ár-értékek (ugyanabban a sorrendben)
    name: str
    bullish: bool
    description: str


CHART_PATTERN_INFO: dict[str, str] = {
    "Dupla csúcs (Double Top)": (
        "Két, hasonló magasságú csúcs egy köztes visszaeséssel - klasszikus "
        "csúcs-forduló jelzés, gyakran \"M\" alakúnak írják le."
    ),
    "Dupla alj (Double Bottom)": (
        "Két, hasonló mélységű alj egy köztes visszapattanással - klasszikus "
        "alj-forduló jelzés, gyakran \"W\" alakúnak írják le."
    ),
    "Fej-váll alakzat (Head & Shoulders)": (
        "Három csúcs, a középső (\"fej\") egyértelműen magasabb, mint a két "
        "szélső (\"váll\") - az egyik legismertebb csúcs-forduló alakzat."
    ),
    "Fordított fej-váll (Inverse Head & Shoulders)": (
        "Három mélypont, a középső (\"fej\") egyértelműen mélyebb, mint a két "
        "szélső (\"váll\") - az egyik legismertebb alj-forduló alakzat."
    ),
}


def find_pivots(df: pd.DataFrame, lookback: int = PIVOT_LOOKBACK) -> tuple[list[int], list[int]]:
    """Helyi csúcs- és mélypontok ("fraktál" pivotok) megkeresése.

    Egy gyertya pivot-csúcs, ha a magassága szigorúan a legnagyobb a
    +-`lookback` gyertyás környezetében (hasonlóan a pivot-aljra).
    """
    highs = df["high"]
    lows = df["low"]
    n = len(df)
    pivot_highs: list[int] = []
    pivot_lows: list[int] = []

    for i in range(lookback, n - lookback):
        window_high = highs.iloc[i - lookback: i + lookback + 1]
        if highs.iloc[i] == window_high.max() and (window_high == highs.iloc[i]).sum() == 1:
            pivot_highs.append(i)

        window_low = lows.iloc[i - lookback: i + lookback + 1]
        if lows.iloc[i] == window_low.min() and (window_low == lows.iloc[i]).sum() == 1:
            pivot_lows.append(i)

    return pivot_highs, pivot_lows


def _match_double_extremes(
    pivots: list[int], other_pivots: list[int], df: pd.DataFrame, use_high: bool, name: str, bullish: bool
) -> list[ChartPatternMatch]:
    """Dupla csúcs: két hasonló magasságú pivot-csúcs (`pivots`) között egy
    mélyebb pivot-alj (`other_pivots`-ból a legmélyebb). Dupla alj: mindez
    fordítva (`use_high=False`)."""
    price_col = "high" if use_high else "low"
    between_col = "low" if use_high else "high"
    between_picker = min if use_high else max  # dupla csúcsnál a legmélyebb pont kell köztük, dupla aljnál a legmagasabb
    matches = []
    for a, b in zip(pivots, pivots[1:]):
        between = [p for p in other_pivots if a < p < b]
        if not between:
            continue
        trough = between_picker(between, key=lambda p: df[between_col].iloc[p])
        price_a = df[price_col].iloc[a]
        price_b = df[price_col].iloc[b]
        trough_price = df[between_col].iloc[trough]
        if price_a <= 0 or price_b <= 0:
            continue

        similarity = abs(price_a - price_b) / max(price_a, price_b)
        if use_high:
            depth = (min(price_a, price_b) - trough_price) / price_a
        else:
            depth = (trough_price - max(price_a, price_b)) / price_a

        if similarity <= PEAK_SIMILARITY_TOLERANCE and depth >= TROUGH_DEPTH_RATIO:
            matches.append(
                ChartPatternMatch((a, trough, b), (price_a, trough_price, price_b), name, bullish, CHART_PATTERN_INFO[name])
            )
    return matches


def _match_head_and_shoulders(
    pivots: list[int], df: pd.DataFrame, use_high: bool, name: str, bullish: bool
) -> list[ChartPatternMatch]:
    price_col = "high" if use_high else "low"
    matches = []
    for left, head, right in zip(pivots, pivots[1:], pivots[2:]):
        left_price = df[price_col].iloc[left]
        head_price = df[price_col].iloc[head]
        right_price = df[price_col].iloc[right]
        if left_price <= 0 or right_price <= 0:
            continue

        is_head_extreme = (head_price > left_price and head_price > right_price) if use_high else (
            head_price < left_price and head_price < right_price
        )
        if not is_head_extreme:
            continue

        shoulder_similarity = abs(left_price - right_price) / max(left_price, right_price)
        if use_high:
            head_prominence_left = (head_price - left_price) / left_price
            head_prominence_right = (head_price - right_price) / right_price
        else:
            head_prominence_left = (left_price - head_price) / left_price
            head_prominence_right = (right_price - head_price) / right_price

        if (
            shoulder_similarity <= SHOULDER_SIMILARITY_TOLERANCE
            and head_prominence_left >= HEAD_PROMINENCE_RATIO
            and head_prominence_right >= HEAD_PROMINENCE_RATIO
        ):
            matches.append(
                ChartPatternMatch(
                    (left, head, right), (left_price, head_price, right_price), name, bullish, CHART_PATTERN_INFO[name]
                )
            )
    return matches


def detect_chart_patterns(df: pd.DataFrame, lookback: int = PIVOT_LOOKBACK) -> list[ChartPatternMatch]:
    """Végigmegy a df pivot-pontjain, és összegyűjti a felismert chart-alakzatokat."""
    pivot_highs, pivot_lows = find_pivots(df, lookback)

    matches: list[ChartPatternMatch] = []
    matches += _match_double_extremes(pivot_highs, pivot_lows, df, True, "Dupla csúcs (Double Top)", False)
    matches += _match_double_extremes(pivot_lows, pivot_highs, df, False, "Dupla alj (Double Bottom)", True)
    matches += _match_head_and_shoulders(pivot_highs, df, True, "Fej-váll alakzat (Head & Shoulders)", False)
    matches += _match_head_and_shoulders(pivot_lows, df, False, "Fordított fej-váll (Inverse Head & Shoulders)", True)

    matches.sort(key=lambda m: m.indices[-1])
    return matches
