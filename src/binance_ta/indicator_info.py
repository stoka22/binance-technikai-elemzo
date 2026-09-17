"""Rövid, magyar nyelvű indikátor-leírások a Súgó menühöz és az info
gombokhoz - tanulási céllal, hogy a felhasználó megértse, mit néz."""

from binance_ta.candlestick_patterns import PATTERN_INFO
from binance_ta.chart_patterns import CHART_PATTERN_INFO

INDICATOR_INFO: dict[str, str] = {
    "SMA": (
        "SMA - Simple Moving Average (egyszerű mozgóátlag)\n\n"
        "Az utolsó N gyertya záróárának átlaga. Simítja az árgörbét, így "
        "könnyebben látható a fő trend iránya. Ha az ár a mozgóátlag fölé "
        "kerül, az gyakran emelkedő trendet jelez, alatta csökkenőt."
    ),
    "Bollinger": (
        "Bollinger szalagok\n\n"
        "Egy mozgóátlag (középvonal) köré rajzolt sáv, aminek szélessége az "
        "árfolyam szórásától (volatilitásától) függ. Ha az ár a felső "
        "szalaghoz közelít, túlvettnek, ha az alsóhoz, túladottnak "
        "tekinthető - erős trendben azonban ez hosszan fennállhat."
    ),
    "RSI": (
        "RSI - Relative Strength Index\n\n"
        "0-100 közötti oszcillátor, ami az elmúlt N gyertya emelkedéseit és "
        "eséseit hasonlítja össze. 70 fölött tipikusan túlvett, 30 alatt "
        "túladott állapotot jelez."
    ),
    "MACD": (
        "MACD - Moving Average Convergence Divergence\n\n"
        "Két exponenciális mozgóátlag (12 és 26 periódus) különbsége (MACD "
        "vonal), és ennek 9 periódusos mozgóátlaga (szignálvonal). Ha a "
        "MACD vonal a szignálvonal fölé keresztez, azt vételi, ha alá, "
        "eladási jelzésnek szokták tekinteni."
    ),
    "Volumen": (
        "Volumen\n\n"
        "Az adott gyertya alatt lebonyolított kereskedési mennyiség. Magas "
        "volumen melletti árelmozdulás megbízhatóbb jelzésnek számít, mint "
        "alacsony volumen mellett."
    ),
    "Jelzések": (
        "Javasolt be-/kilépési jelzések\n\n"
        "Ugyanaz a folytonos technikai pontszám (0-100%) áll mögötte, mint a "
        "Piac-szűrő eszközé: RSI, MACD, SMA-trend és Bollinger-pozíció "
        "átlaga, volumennel súlyozva - rögzített, standard paraméterekkel "
        "(RSI14, SMA20/50, Bollinger20), függetlenül attól, mit állítottál "
        "be a fenti indikátor-dobozokban.\n\n"
        "A zöld ▲ ott jelenik meg, ahol a pontszám átlépi felfelé a "
        "Beállításokban megadott küszöböt (alapból 90%), a piros ▼ ott, "
        "ahol lefelé lépi át a tükrözött (100-küszöb) szintet - csak az "
        "átlépés pillanatában, nem minden gyertyán, amíg a szint fölött/"
        "alatt marad.\n\n"
        "Ez egy tanulási célú, visszatekintő jelzésrendszer - NEM "
        "befektetési tanács és nem garantál semmit a jövőre nézve."
    ),
    "Alakzatok": (
        "Gyertya-alakzatok (candlestick pattern) felismerése\n\n"
        "Tiszta geometriai szabályokkal (test/lengés arányok, szomszédos "
        "gyertyák viszonya) - ahogy a legtöbb charting platform is teszi, "
        "NEM gépi tanulással. Bekapcsolva a charton színes pont jelöli a "
        "felismert alakzatokat (zöld=bullish, piros=bearish, szürke=semleges) "
        "- vidd az egeret a jelölt gyertyára a pontos névért.\n\n"
        + "\n\n".join(f"{name}\n{desc}" for name, desc in PATTERN_INFO.items())
    ),
    "Formációk": (
        "Chart-alakzatok (chart pattern) felismerése\n\n"
        "Előbb megkeressük a helyi csúcsokat/mélypontokat (pivot pontokat), "
        "majd ezekre illesztünk geometriai szabályokat - ahogy pl. az "
        "Autochartist is teszi, NEM gépi tanulással. Bekapcsolva egy vékony "
        "vonal köti össze az alakzat pontjait a charton (zöld=bullish, "
        "piros=bearish), rövid felirattal.\n\n"
        + "\n\n".join(f"{name}\n{desc}" for name, desc in CHART_PATTERN_INFO.items())
    ),
}
