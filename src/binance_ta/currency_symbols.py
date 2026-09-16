"""Néhány jól ismert kripto- és fiat-pénznem nemzetközi (Unicode) jele.

A Binance API nem ad vissza sem teljes nevet, sem hivatalos szimbólumot a
legtöbb (kisebb) kriptovalutához. Csak azoknál mutatunk jelet, amelyeknek
ténylegesen van elterjedt, egyértelmű Unicode karaktere - a többinél a
ticker rövidítés marad látható, nehogy hamis/kitalált jelet mutassunk."""

CURRENCY_SYMBOLS: dict[str, str] = {
    "BTC": "₿",
    "ETH": "Ξ",
    "USDT": "$", "USDC": "$", "USD": "$", "BUSD": "$", "FDUSD": "$", "USDP": "$",
    "EUR": "€", "EURI": "€",
    "GBP": "£",
    "TRY": "₺",
    "INR": "₹",
    "JPY": "¥",
    "RUB": "₽",
    "UAH": "₴",
    "NGN": "₦",
    "KRW": "₩",
    "BRL": "R$",
    "VND": "₫",
    "THB": "฿",
    "ZAR": "R",
    "PLN": "zł",
}


def symbol_for(asset: str) -> str | None:
    """Az eszköz nemzetközi szimbóluma, ha ismert - egyébként None."""
    return CURRENCY_SYMBOLS.get(asset.upper())


def format_pair_glyph(base_asset: str, quote_asset: str) -> str:
    """"₿/$" stílusú rövid megjelenítés - ismeretlen eszközöknél a ticker marad."""
    base = symbol_for(base_asset) or base_asset
    quote = symbol_for(quote_asset) or quote_asset
    return f"{base}/{quote}"
