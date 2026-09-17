"""Konfigurálható szabályok a gyakorló ügyletek kiértékeléséhez.

Több súlyossági szint (info/figyelmeztetés/szabálysértés), a beépített
szabályok ki/bekapcsolhatók és paraméterezhetők, saját szabályok pedig
biztonságos, előre definiált építőelemekből hozhatók létre (indikátor +
összehasonlítás + érték + irány) - nincs szabad szöveges képlet/kódfuttatás,
hogy ne lehessen véletlenül (vagy szándékosan) tetszőleges kódot futtatni.
"""

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

RULES_DIR = Path.home() / ".binance_ta"
RULES_FILE = RULES_DIR / "rules.json"

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_VIOLATION = "violation"
SEVERITIES = [SEVERITY_INFO, SEVERITY_WARNING, SEVERITY_VIOLATION]

SEVERITY_ICONS = {SEVERITY_INFO: "ℹ️", SEVERITY_WARNING: "⚠️", SEVERITY_VIOLATION: "❌"}
SEVERITY_LABELS = {SEVERITY_INFO: "Info", SEVERITY_WARNING: "Figyelmeztetés", SEVERITY_VIOLATION: "Szabálysértés"}

KIND_TREND = "trend"
KIND_RSI_EXTREME = "rsi_extreme"
KIND_LOSS_THRESHOLD = "loss_threshold"
KIND_EARLY_EXIT = "early_exit"
KIND_CUSTOM_COMPARE = "custom_compare"

KIND_LABELS = {
    KIND_TREND: "Trend",
    KIND_RSI_EXTREME: "RSI szélsőség",
    KIND_LOSS_THRESHOLD: "Veszteség küszöb",
    KIND_EARLY_EXIT: "Korai zárás",
    KIND_CUSTOM_COMPARE: "Egyéni",
}


@dataclass
class RuleConfig:
    id: str
    name: str
    kind: str
    severity: str = SEVERITY_WARNING
    enabled: bool = True
    builtin: bool = False
    description: str = ""
    params: dict = field(default_factory=dict)


def _default_rules() -> list[RuleConfig]:
    return [
        RuleConfig(
            id="builtin_trend", name="Trend ellen kereskedés", kind=KIND_TREND,
            severity=SEVERITY_WARNING, builtin=True,
            description=(
                "Ne kereskedj a fő trend ellen.\n\n"
                "Ha az ár a hosszabb távú mozgóátlag (SMA) alatt van, az inkább "
                "csökkenő trendet jelez - long pozíciót ilyenkor nyitni a "
                "trenddel szembemegy. (Fordítva ugyanez shortra.)"
            ),
            params={"sma_period": 50},
        ),
        RuleConfig(
            id="builtin_rsi_extreme", name="Túlvett/túladott belépés", kind=KIND_RSI_EXTREME,
            severity=SEVERITY_WARNING, builtin=True,
            description=(
                "Ne lépj be már túlvett/túladott állapotban.\n\n"
                "Ha az RSI már szélsőséges tartományban van, a mozgás nagy "
                "része valószínűleg megtörtént - a késői belépés korrekció "
                "kockázatát hordozza."
            ),
            params={"rsi_period": 14, "overbought": 70, "oversold": 30},
        ),
        RuleConfig(
            id="builtin_no_stop_loss", name="Nincs stop-loss (nagy veszteség)", kind=KIND_LOSS_THRESHOLD,
            severity=SEVERITY_VIOLATION, builtin=True,
            description=(
                "Vágd rövidre a veszteséget (használj stop-losst).\n\n"
                "Ha egy pozíció nagy mínuszba fordul, és nincs előre "
                "meghatározott kiszállási szint, könnyen tovább nő a veszteség."
            ),
            params={"loss_percent": -5.0},
        ),
        RuleConfig(
            id="builtin_early_exit", name="Korai zárás", kind=KIND_EARLY_EXIT,
            severity=SEVERITY_INFO, builtin=True,
            description=(
                "Hagyd futni a nyereséget.\n\n"
                "Ha egy nyerő pozíciót nagyon korán zársz le, és az ár utána "
                "sokkal tovább mozgott a kedvező irányba, azt jelezheti, hogy "
                "túl korán realizáltad a nyereséget."
            ),
            params={"lookahead_candles": 20, "min_missed_percent": 2.0},
        ),
    ]


class RuleConfigStore:
    """A szabály-konfigurációk betöltése/mentése JSON fájlba."""

    def __init__(self, path: Path = RULES_FILE):
        self.path = path
        self.rules: list[RuleConfig] = self._load()

    def _load(self) -> list[RuleConfig]:
        if not self.path.exists():
            return _default_rules()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            known_fields = {f for f in RuleConfig.__dataclass_fields__}
            rules = [RuleConfig(**{k: v for k, v in item.items() if k in known_fields}) for item in data]
            return rules if rules else _default_rules()
        except (json.JSONDecodeError, TypeError, OSError) as exc:
            logger.warning("Hibás szabály-konfiguráció, alapértelmezettek használata: %s", exc)
            return _default_rules()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([asdict(r) for r in self.rules], indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def add(self, rule: RuleConfig) -> None:
        self.rules.append(rule)
        self.save()

    def update(self, rule: RuleConfig) -> None:
        for i, existing in enumerate(self.rules):
            if existing.id == rule.id:
                self.rules[i] = rule
                self.save()
                return

    def delete(self, rule_id: str) -> None:
        self.rules = [r for r in self.rules if r.id != rule_id]
        self.save()

    def enabled_rules(self) -> list[RuleConfig]:
        return [r for r in self.rules if r.enabled]

    def new_custom_rule(self) -> RuleConfig:
        return RuleConfig(
            id=uuid.uuid4().hex, name="Egyéni szabály", kind=KIND_CUSTOM_COMPARE,
            severity=SEVERITY_WARNING, builtin=False,
            params={"metric": "rsi", "period": 14, "comparator": "above", "threshold": 70.0, "applies_to": "both"},
        )
