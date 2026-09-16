import pandas as pd
import pytest
import requests

from binance_ta import client


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


def _sample_kline_row(open_time_ms: int) -> list:
    return [
        open_time_ms, "100.0", "110.0", "90.0", "105.0", "10.5",
        open_time_ms + 3_600_000 - 1, "1000.0", 42, "5.0", "500.0", "0",
    ]


@pytest.fixture(autouse=True)
def _reset_symbol_cache():
    client._symbols_cache = None
    yield
    client._symbols_cache = None


def test_fetch_klines_parses_dataframe(monkeypatch):
    rows = [_sample_kline_row(1_700_000_000_000 + i * 3_600_000) for i in range(3)]

    def fake_get(url, params=None, timeout=None):
        assert "klines" in url
        assert params["symbol"] == "BTCUSDT"
        return FakeResponse(rows)

    monkeypatch.setattr(client._session, "get", fake_get)

    df = client.fetch_klines("btcusdt", "1h", limit=3)

    assert len(df) == 3
    assert list(df.columns) == ["open_time", "open", "high", "low", "close", "volume", "close_time"]
    assert df["close"].iloc[0] == pytest.approx(105.0)
    assert pd.api.types.is_datetime64_any_dtype(df["open_time"])


def test_fetch_klines_raises_binance_error_on_http_failure(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        return FakeResponse({"code": -1121, "msg": "Invalid symbol."}, status_code=400)

    monkeypatch.setattr(client._session, "get", fake_get)

    with pytest.raises(client.BinanceAPIError):
        client.fetch_klines("NOTREAL", "1h")


def test_get_exchange_symbols_filters_trading_and_caches(monkeypatch):
    payload = {
        "symbols": [
            {"symbol": "BTCUSDT", "status": "TRADING"},
            {"symbol": "OLDCOIN", "status": "BREAK"},
            {"symbol": "ETHUSDT", "status": "TRADING"},
        ]
    }
    call_count = {"n": 0}

    def fake_get(url, params=None, timeout=None):
        call_count["n"] += 1
        return FakeResponse(payload)

    monkeypatch.setattr(client._session, "get", fake_get)

    symbols = client.get_exchange_symbols()
    assert symbols == ["BTCUSDT", "ETHUSDT"]

    # második hívás gyorsítótárból jön, nincs újabb HTTP kérés
    client.get_exchange_symbols()
    assert call_count["n"] == 1
