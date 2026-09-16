"""Gyakorló kereskedési napló: a felhasználó a történeti charton kattintással
jelöl ki belépési és záró pontokat, ezeket itt rögzítjük (perzisztálva),
hogy utólag kimutatás/statisztika készülhessen róluk."""

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

TRADES_DIR = Path.home() / ".binance_ta"
TRADES_FILE = TRADES_DIR / "trades.json"


@dataclass
class Trade:
    symbol: str
    interval: str
    direction: str  # "long" | "short"
    entry_time: str  # ISO 8601
    entry_price: float
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    exit_time: str | None = None
    exit_price: float | None = None

    @property
    def is_open(self) -> bool:
        return self.exit_time is None

    @property
    def pnl_percent(self) -> float | None:
        if self.exit_price is None:
            return None
        if self.direction == "long":
            return (self.exit_price - self.entry_price) / self.entry_price * 100
        return (self.entry_price - self.exit_price) / self.entry_price * 100


class TradeJournal:
    """A gyakorló ügyletek betöltése/mentése JSON fájlba."""

    def __init__(self, path: Path = TRADES_FILE):
        self.path = path
        self.trades: list[Trade] = self._load()

    def _load(self) -> list[Trade]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            known_fields = {f for f in Trade.__dataclass_fields__}
            return [Trade(**{k: v for k, v in item.items() if k in known_fields}) for item in data]
        except (json.JSONDecodeError, TypeError, OSError) as exc:
            logger.warning("Hibás kereskedési napló fájl, üres napló használata: %s", exc)
            return []

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([asdict(t) for t in self.trades], indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def open_trade_for(self, symbol: str) -> Trade | None:
        for trade in reversed(self.trades):
            if trade.symbol == symbol and trade.is_open:
                return trade
        return None

    def open_trade(self, symbol: str, interval: str, direction: str, entry_time: str, entry_price: float) -> Trade:
        trade = Trade(
            symbol=symbol, interval=interval, direction=direction,
            entry_time=entry_time, entry_price=entry_price,
        )
        self.trades.append(trade)
        self.save()
        return trade

    def close_trade(self, trade: Trade, exit_time: str, exit_price: float) -> None:
        trade.exit_time = exit_time
        trade.exit_price = exit_price
        self.save()

    def delete(self, trade_id: str) -> None:
        self.trades = [t for t in self.trades if t.id != trade_id]
        self.save()

    def closed_trades(self) -> list[Trade]:
        return [t for t in self.trades if not t.is_open]
