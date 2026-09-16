"""Technikai indikátorok: SMA, RSI, MACD, Bollinger szalagok."""

import pandas as pd


def add_sma(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.DataFrame:
    """Egyszerű mozgóátlag (Simple Moving Average) hozzáadása."""
    df[f"sma_{period}"] = df[column].rolling(window=period).mean()
    return df


def add_rsi(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.DataFrame:
    """RSI (Relative Strength Index) számítása Wilder-féle simítással."""
    delta = df[column].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    df[f"rsi_{period}"] = 100 - (100 / (1 + rs))
    return df


def add_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    column: str = "close",
) -> pd.DataFrame:
    """MACD vonal, szignálvonal és hisztogram hozzáadása."""
    ema_fast = df[column].ewm(span=fast, adjust=False).mean()
    ema_slow = df[column].ewm(span=slow, adjust=False).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()

    df["macd"] = macd_line
    df["macd_signal"] = signal_line
    df["macd_hist"] = macd_line - signal_line
    return df


def add_bollinger_bands(
    df: pd.DataFrame,
    period: int = 20,
    num_std: float = 2.0,
    column: str = "close",
) -> pd.DataFrame:
    """Bollinger szalagok (középvonal + felső/alsó szórássáv) hozzáadása."""
    sma = df[column].rolling(window=period).mean()
    std = df[column].rolling(window=period).std()

    df[f"bb_mid_{period}"] = sma
    df[f"bb_upper_{period}"] = sma + num_std * std
    df[f"bb_lower_{period}"] = sma - num_std * std
    return df
