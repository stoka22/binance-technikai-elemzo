from pathlib import Path

from binance_ta.trade_journal import Trade, TradeJournal


def test_open_and_close_trade_roundtrip(tmp_path: Path):
    journal = TradeJournal(tmp_path / "trades.json")

    trade = journal.open_trade("BTCUSDT", "1h", "long", "2024-01-01T00:00:00", 100.0)
    assert trade.is_open
    assert journal.open_trade_for("BTCUSDT") is trade

    journal.close_trade(trade, "2024-01-02T00:00:00", 110.0)
    assert not trade.is_open
    assert trade.pnl_percent == 10.0
    assert journal.open_trade_for("BTCUSDT") is None


def test_short_trade_pnl_is_inverted():
    trade = Trade(
        symbol="BTCUSDT", interval="1h", direction="short",
        entry_time="2024-01-01T00:00:00", entry_price=100.0,
        exit_time="2024-01-02T00:00:00", exit_price=90.0,
    )
    assert trade.pnl_percent == 10.0  # short + ar esett -> nyereseg


def test_journal_persists_across_instances(tmp_path: Path):
    path = tmp_path / "trades.json"
    journal = TradeJournal(path)
    trade = journal.open_trade("ETHUSDT", "4h", "long", "2024-01-01T00:00:00", 2000.0)
    journal.close_trade(trade, "2024-01-01T04:00:00", 2100.0)

    reloaded = TradeJournal(path)
    assert len(reloaded.trades) == 1
    assert reloaded.trades[0].symbol == "ETHUSDT"
    assert reloaded.trades[0].pnl_percent == 5.0


def test_delete_removes_trade(tmp_path: Path):
    journal = TradeJournal(tmp_path / "trades.json")
    trade = journal.open_trade("BTCUSDT", "1h", "long", "2024-01-01T00:00:00", 100.0)

    journal.delete(trade.id)

    assert journal.trades == []


def test_closed_trades_excludes_open_positions(tmp_path: Path):
    journal = TradeJournal(tmp_path / "trades.json")
    open_trade = journal.open_trade("BTCUSDT", "1h", "long", "2024-01-01T00:00:00", 100.0)
    closed_trade = journal.open_trade("ETHUSDT", "1h", "long", "2024-01-01T00:00:00", 100.0)
    journal.close_trade(closed_trade, "2024-01-01T01:00:00", 105.0)

    result = journal.closed_trades()

    assert result == [closed_trade]
    assert open_trade not in result
