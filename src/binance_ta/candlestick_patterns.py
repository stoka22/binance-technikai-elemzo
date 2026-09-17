"""Klasszikus gyertya-alakzat (candlestick pattern) felismerés.

Tiszta geometriai szabályokkal dolgozik (test/lengés arányok, szomszédos
gyertyák viszonya) - ahogy a TA-Lib és a legtöbb charting platform is teszi,
NEM gépi tanulással. Determinisztikus és magyarázható: minden találatnál
pontosan tudni lehet, melyik szabály miatt jelent meg.
"""

from dataclasses import dataclass

import pandas as pd

# Küszöbök (a szakirodalomban/TA-Lib-ben is megszokott, kerekített arányok).
DOJI_BODY_RATIO = 0.05  # test <= a teljes lengés 5%-a
LONG_WICK_RATIO = 2.5  # a domináns lengés legalább a test 2.5x-ese
SMALL_WICK_RATIO = 0.08  # az ellentétes lengés legfeljebb a teljes lengés 8%-a
MARUBOZU_BODY_RATIO = 0.95  # a test a lengés legalább 95%-a (szinte nincs lengés)
STAR_SMALL_BODY_RATIO = 0.5  # a középső gyertya teste az első test legfeljebb fele
TREND_LOOKBACK = 5  # ennyi gyertyát nézünk vissza a trend-kontextushoz

# Volatilitás-szűrő: csak akkor számít "jelentősnek" egy mintában szereplő
# gyertya, ha a teste legalább ennyiszerese az elozo N gyertya átlagos
# tartományának (high-low) - enélkül csendes, alacsony volatilitású
# szakaszokban szinte minden apró gyertya "mintaként" jelenne meg, ami
# zajossá tenné a jelölést a charton.
SIGNIFICANCE_RANGE_RATIO = 0.8
SIGNIFICANCE_LOOKBACK = 14
SOLID_BODY_RATIO = 0.4  # (Three Soldiers/Crows) test/lengés arány minimuma gyertyánként


@dataclass(frozen=True)
class PatternMatch:
    index: int
    name: str
    bullish: bool | None  # True = bullish, False = bearish, None = semleges (pl. Doji)
    description: str


PATTERN_INFO: dict[str, str] = {
    "Doji": "A nyitó és záróár szinte megegyezik - bizonytalanságot, lehetséges fordulót jelez.",
    "Bullish Marubozu": "Végig egy irányba mozgó, lengés nélküli erős emelkedő gyertya.",
    "Bearish Marubozu": "Végig egy irányba mozgó, lengés nélküli erős csökkenő gyertya.",
    "Hammer (Kalapács)": "Csökkenő trend után hosszú alsó lengésű, kis testű gyertya - lehetséges forduló felfelé.",
    "Hanging Man (Akasztott ember)": "Emelkedő trend után hosszú alsó lengésű, kis testű gyertya - lehetséges forduló lefelé.",
    "Inverted Hammer (Fordított kalapács)": "Csökkenő trend után hosszú felső lengésű, kis testű gyertya - lehetséges forduló felfelé.",
    "Shooting Star (Csillagszóró)": "Emelkedő trend után hosszú felső lengésű, kis testű gyertya - lehetséges forduló lefelé.",
    "Bullish Engulfing (Elnyelő minta)": "A második (emelkedő) gyertya teste teljesen befedi az előző (csökkenő) gyertya testét.",
    "Bearish Engulfing (Elnyelő minta)": "A második (csökkenő) gyertya teste teljesen befedi az előző (emelkedő) gyertya testét.",
    "Bullish Harami": "Egy nagy csökkenő gyertya után egy kicsi, a testén belül maradó emelkedő gyertya.",
    "Bearish Harami": "Egy nagy emelkedő gyertya után egy kicsi, a testén belül maradó csökkenő gyertya.",
    "Piercing Line (Átszúró minta)": "Csökkenő gyertya után egy emelkedő gyertya, ami az előző test felénél magasabbra zár.",
    "Dark Cloud Cover (Sötét felhő)": "Emelkedő gyertya után egy csökkenő gyertya, ami az előző test felénél lejjebb zár.",
    "Morning Star (Hajnalcsillag)": "Nagy csökkenő, kicsi bizonytalan, majd nagy emelkedő gyertya - klasszikus alj-forduló.",
    "Evening Star (Alkonycsillag)": "Nagy emelkedő, kicsi bizonytalan, majd nagy csökkenő gyertya - klasszikus csúcs-forduló.",
    "Three White Soldiers (Három fehér katona)": "Három egymást követő, egyre magasabbra záró emelkedő gyertya.",
    "Three Black Crows (Három fekete varjú)": "Három egymást követő, egyre lejjebb záró csökkenő gyertya.",
}


def _shape(row: pd.Series) -> tuple[float, float, float, float, float, float, float, float]:
    o, h, l, c = row["open"], row["high"], row["low"], row["close"]
    rng = h - l
    body = abs(c - o)
    upper = h - max(o, c)
    lower = min(o, c) - l
    return o, h, l, c, rng, body, upper, lower


def _is_bullish(row: pd.Series) -> bool:
    return row["close"] > row["open"]


def _is_bearish(row: pd.Series) -> bool:
    return row["close"] < row["open"]


def _trend_before(df: pd.DataFrame, i: int, lookback: int = TREND_LOOKBACK) -> str | None:
    if i - lookback < 0:
        return None
    start = df["close"].iloc[i - lookback]
    end = df["close"].iloc[i - 1]
    if start <= 0:
        return None
    change = (end - start) / start
    if change < -0.001:
        return "down"
    if change > 0.001:
        return "up"
    return None


def _avg_range(df: pd.DataFrame, i: int, lookback: int = SIGNIFICANCE_LOOKBACK) -> float | None:
    """Az előző `lookback` gyertya átlagos (high-low) tartománya, i-t nem
    beleszámítva - ehhez viszonyítjuk, hogy egy gyertya teste "jelentős"-e."""
    start = max(0, i - lookback)
    if start >= i:
        return None
    window = df.iloc[start:i]
    rng = (window["high"] - window["low"]).mean()
    return rng if rng and rng > 0 else None


def _is_significant(body: float, df: pd.DataFrame, i: int) -> bool:
    """Csendes, alacsony volatilitású szakaszokban egy apró test sem számít
    "jelentősnek" - ez szűri ki a zajt a csendes időszakokból."""
    avg_range = _avg_range(df, i)
    if avg_range is None:
        return True  # nincs elég előtörténet a viszonyításhoz - engedjük át
    return body >= SIGNIFICANCE_RANGE_RATIO * avg_range


def _match_doji(df: pd.DataFrame, i: int) -> PatternMatch | None:
    _o, _h, _l, _c, rng, body, _u, _lo = _shape(df.iloc[i])
    if rng <= 0:
        return None
    if body / rng <= DOJI_BODY_RATIO:
        return PatternMatch(i, "Doji", None, PATTERN_INFO["Doji"])
    return None


def _match_marubozu(df: pd.DataFrame, i: int) -> PatternMatch | None:
    row = df.iloc[i]
    _o, _h, _l, c, rng, body, _u, _lo = _shape(row)
    if rng <= 0:
        return None
    if body / rng >= MARUBOZU_BODY_RATIO:
        bullish = c > row["open"]
        name = "Bullish Marubozu" if bullish else "Bearish Marubozu"
        return PatternMatch(i, name, bullish, PATTERN_INFO[name])
    return None


def _match_hammer_family(df: pd.DataFrame, i: int) -> PatternMatch | None:
    row = df.iloc[i]
    _o, _h, _l, _c, rng, body, upper, lower = _shape(row)
    if rng <= 0 or body <= 0:
        return None
    if not _is_significant(rng, df, i):  # a teljes lengésnek kell jelentősnek lennie, nem a testnek
        return None
    trend = _trend_before(df, i)

    if lower >= LONG_WICK_RATIO * body and upper <= SMALL_WICK_RATIO * rng:
        if trend == "down":
            return PatternMatch(i, "Hammer (Kalapács)", True, PATTERN_INFO["Hammer (Kalapács)"])
        if trend == "up":
            return PatternMatch(i, "Hanging Man (Akasztott ember)", False, PATTERN_INFO["Hanging Man (Akasztott ember)"])
        return None

    if upper >= LONG_WICK_RATIO * body and lower <= SMALL_WICK_RATIO * rng:
        if trend == "up":
            return PatternMatch(i, "Shooting Star (Csillagszóró)", False, PATTERN_INFO["Shooting Star (Csillagszóró)"])
        if trend == "down":
            return PatternMatch(
                i, "Inverted Hammer (Fordított kalapács)", True, PATTERN_INFO["Inverted Hammer (Fordított kalapács)"]
            )
        return None

    return None


def _match_engulfing(df: pd.DataFrame, i: int) -> PatternMatch | None:
    if i < 1:
        return None
    prev, cur = df.iloc[i - 1], df.iloc[i]
    prev_top, prev_bot = max(prev["open"], prev["close"]), min(prev["open"], prev["close"])
    cur_top, cur_bot = max(cur["open"], cur["close"]), min(cur["open"], cur["close"])
    if prev_top <= prev_bot or not _is_significant(cur_top - cur_bot, df, i):
        return None

    if _is_bearish(prev) and _is_bullish(cur) and cur_bot <= prev_bot and cur_top >= prev_top:
        name = "Bullish Engulfing (Elnyelő minta)"
        return PatternMatch(i, name, True, PATTERN_INFO[name])
    if _is_bullish(prev) and _is_bearish(cur) and cur_bot <= prev_bot and cur_top >= prev_top:
        name = "Bearish Engulfing (Elnyelő minta)"
        return PatternMatch(i, name, False, PATTERN_INFO[name])
    return None


def _match_harami(df: pd.DataFrame, i: int) -> PatternMatch | None:
    if i < 1:
        return None
    prev, cur = df.iloc[i - 1], df.iloc[i]
    prev_top, prev_bot = max(prev["open"], prev["close"]), min(prev["open"], prev["close"])
    cur_top, cur_bot = max(cur["open"], cur["close"]), min(cur["open"], cur["close"])
    if prev_top <= prev_bot or not _is_significant(prev_top - prev_bot, df, i):
        return None
    if cur_top <= prev_top and cur_bot >= prev_bot:
        if _is_bearish(prev) and _is_bullish(cur):
            return PatternMatch(i, "Bullish Harami", True, PATTERN_INFO["Bullish Harami"])
        if _is_bullish(prev) and _is_bearish(cur):
            return PatternMatch(i, "Bearish Harami", False, PATTERN_INFO["Bearish Harami"])
    return None


def _match_piercing_or_darkcloud(df: pd.DataFrame, i: int) -> PatternMatch | None:
    if i < 1:
        return None
    prev, cur = df.iloc[i - 1], df.iloc[i]
    prev_body = abs(prev["close"] - prev["open"])
    if not _is_significant(prev_body, df, i):
        return None
    prev_mid = (prev["open"] + prev["close"]) / 2

    if (
        _is_bearish(prev) and _is_bullish(cur)
        and cur["open"] < prev["close"] and prev_mid < cur["close"] < prev["open"]
    ):
        name = "Piercing Line (Átszúró minta)"
        return PatternMatch(i, name, True, PATTERN_INFO[name])
    if (
        _is_bullish(prev) and _is_bearish(cur)
        and cur["open"] > prev["close"] and prev["open"] < cur["close"] < prev_mid
    ):
        name = "Dark Cloud Cover (Sötét felhő)"
        return PatternMatch(i, name, False, PATTERN_INFO[name])
    return None


def _match_star(df: pd.DataFrame, i: int) -> PatternMatch | None:
    if i < 2:
        return None
    first, second, third = df.iloc[i - 2], df.iloc[i - 1], df.iloc[i]
    first_body = abs(first["close"] - first["open"])
    second_body = abs(second["close"] - second["open"])
    if first_body <= 0 or second_body > first_body * STAR_SMALL_BODY_RATIO:
        return None
    if not _is_significant(first_body, df, i):
        return None
    first_mid = (first["open"] + first["close"]) / 2

    if _is_bearish(first) and _is_bullish(third) and third["close"] > first_mid:
        name = "Morning Star (Hajnalcsillag)"
        return PatternMatch(i, name, True, PATTERN_INFO[name])
    if _is_bullish(first) and _is_bearish(third) and third["close"] < first_mid:
        name = "Evening Star (Alkonycsillag)"
        return PatternMatch(i, name, False, PATTERN_INFO[name])
    return None


def _has_solid_body(row: pd.Series) -> bool:
    """A test legyen a gyertya lengésének érdemi része (ne egy hajszálnyi,
    hosszú lengésű "épphogy zöld/piros" gyertya)."""
    _o, _h, _l, _c, rng, body, _u, _lo = _shape(row)
    return rng > 0 and body / rng >= SOLID_BODY_RATIO


def _match_three_soldiers_or_crows(df: pd.DataFrame, i: int) -> PatternMatch | None:
    if i < 2:
        return None
    a, b, c = df.iloc[i - 2], df.iloc[i - 1], df.iloc[i]
    if not (_has_solid_body(a) and _has_solid_body(b) and _has_solid_body(c)):
        return None
    min_body = min(abs(a["close"] - a["open"]), abs(b["close"] - b["open"]), abs(c["close"] - c["open"]))
    if not _is_significant(min_body, df, i):
        return None

    if _is_bullish(a) and _is_bullish(b) and _is_bullish(c):
        if b["open"] > a["open"] and b["close"] > a["close"] and c["open"] > b["open"] and c["close"] > b["close"]:
            name = "Three White Soldiers (Három fehér katona)"
            return PatternMatch(i, name, True, PATTERN_INFO[name])
    if _is_bearish(a) and _is_bearish(b) and _is_bearish(c):
        if b["open"] < a["open"] and b["close"] < a["close"] and c["open"] < b["open"] and c["close"] < b["close"]:
            name = "Three Black Crows (Három fekete varjú)"
            return PatternMatch(i, name, False, PATTERN_INFO[name])
    return None


# Sorrend: a specifikusabb (több gyertyás) mintákat előbb keressük, hogy egy
# adott gyertyához az összes találatot megkapjuk (egy index több mintának is
# megfelelhet - pl. Doji és Harami egyszerre).
_PATTERN_MATCHERS = [
    _match_three_soldiers_or_crows,
    _match_star,
    _match_engulfing,
    _match_harami,
    _match_piercing_or_darkcloud,
    _match_hammer_family,
    _match_marubozu,
    _match_doji,
]


def detect_patterns(df: pd.DataFrame) -> list[PatternMatch]:
    """Végigmegy a df minden gyertyáján, és összegyűjti az összes felismert alakzatot."""
    matches: list[PatternMatch] = []
    for i in range(len(df)):
        for matcher in _PATTERN_MATCHERS:
            result = matcher(df, i)
            if result is not None:
                matches.append(result)
    return matches


def dominant_pattern_per_index(matches: list[PatternMatch]) -> dict[int, PatternMatch]:
    """Ha egy gyertyára több minta is illik, a `_PATTERN_MATCHERS` sorrendje
    szerinti elsőt (a specifikusabbat) választjuk ki a chart-jelöléshez."""
    result: dict[int, PatternMatch] = {}
    for match in matches:
        if match.index not in result:
            result[match.index] = match
    return result
