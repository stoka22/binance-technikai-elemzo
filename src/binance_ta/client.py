"""Binance publikus REST API kliens: gyertyaadatok és szimbólumlista lekérése.

Robusztussági szempontok:
- automatikus újrapróbálkozás (retry) exponenciális backoff-fal átmeneti
  hálózati hibákra és 429/5xx státuszkódokra,
- explicit timeout minden híváson,
- egységes ``BinanceAPIError`` kivétel, amit a hívó (pl. a GUI) egyszerűen
  el tud kapni és meg tud jeleníteni a felhasználónak,
- ``logging`` a print helyett, hogy a hibák fájlba is kerüljenek.
"""

import logging
from dataclasses import dataclass

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

BASE_URL = "https://api.binance.com"
KLINES_ENDPOINT = f"{BASE_URL}/api/v3/klines"
EXCHANGE_INFO_ENDPOINT = f"{BASE_URL}/api/v3/exchangeInfo"

# A Binance /klines végpontja egy oszloplistát ad vissza, ezek a nevei sorrendben:
KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_asset_volume", "num_trades",
    "taker_buy_base", "taker_buy_quote", "ignore",
]

REQUEST_TIMEOUT = 10  # másodperc


class BinanceAPIError(RuntimeError):
    """A Binance API-val kapcsolatos hiba (hálózati vagy válasz szintű)."""


def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,  # 0.5s, 1s, 2s várakozás a próbálkozások között
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_session = _build_session()
_symbol_info_cache: list["SymbolInfo"] | None = None


@dataclass(frozen=True)
class SymbolInfo:
    """Egy kereskedhető pár a Binance-en, a base/quote eszközökre bontva."""

    symbol: str
    base_asset: str
    quote_asset: str

    @property
    def display(self) -> str:
        """Olvasható forma, pl. "BTC/USDT" - ezt mutatjuk a szimbólum-választóban."""
        return f"{self.base_asset}/{self.quote_asset}"


def fetch_klines(symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
    """Gyertyák (OHLCV) lekérése a Binance API-ról.

    Raises:
        BinanceAPIError: ha a kérés hálózati hiba vagy hibás státuszkód miatt
            nem sikerül (pl. érvénytelen szimbólum, rate limit túllépés).
    """
    symbol = symbol.upper()
    logger.info("Gyertyák lekérése: %s interval=%s limit=%s", symbol, interval, limit)

    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        response = _session.get(KLINES_ENDPOINT, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("Hiba a gyertyák lekérésekor (%s)", symbol)
        raise BinanceAPIError(f"Nem sikerült lekérni az árfolyamadatokat ({symbol}): {exc}") from exc

    raw = response.json()
    df = pd.DataFrame(raw, columns=KLINE_COLUMNS)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

    numeric_cols = ["open", "high", "low", "close", "volume"]
    df[numeric_cols] = df[numeric_cols].astype(float)

    logger.debug("Sikeres lekérés: %s sor érkezett (%s)", len(df), symbol)
    return df[["open_time", "open", "high", "low", "close", "volume", "close_time"]]


def get_tradable_symbols(force_refresh: bool = False) -> list[SymbolInfo]:
    """A Binance-en jelenleg kereskedhető (TRADING státuszú) párok, base/quote bontással.

    Az eredményt memóriában gyorsítótárazza, mert ez a lista ritkán változik,
    így nem kell minden GUI-indításkor/kereséskor újra lekérni.
    """
    global _symbol_info_cache
    if _symbol_info_cache is not None and not force_refresh:
        return _symbol_info_cache

    logger.info("Szimbólumlista lekérése a Binance-ről...")
    try:
        response = _session.get(EXCHANGE_INFO_ENDPOINT, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("Hiba a szimbólumlista lekérésekor")
        raise BinanceAPIError(f"Nem sikerült lekérni a szimbólumlistát: {exc}") from exc

    data = response.json()
    infos = sorted(
        (
            SymbolInfo(entry["symbol"], entry["baseAsset"], entry["quoteAsset"])
            for entry in data.get("symbols", [])
            if entry.get("status") == "TRADING"
        ),
        key=lambda info: info.symbol,
    )
    _symbol_info_cache = infos
    logger.debug("Szimbólumlista betöltve: %s elem", len(infos))
    return infos


def get_exchange_symbols(force_refresh: bool = False) -> list[str]:
    """A kereskedhető szimbólumok neve egyszerű listaként (pl. validációhoz)."""
    return [info.symbol for info in get_tradable_symbols(force_refresh)]
