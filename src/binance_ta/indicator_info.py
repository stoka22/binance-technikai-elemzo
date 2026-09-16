"""Rövid, magyar nyelvű indikátor-leírások a Súgó menühöz és az info
gombokhoz - tanulási céllal, hogy a felhasználó megértse, mit néz."""

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
}
