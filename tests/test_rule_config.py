from pathlib import Path

from binance_ta.rule_config import RuleConfig, RuleConfigStore, SEVERITY_VIOLATION


def test_missing_file_seeds_four_builtin_rules(tmp_path: Path):
    store = RuleConfigStore(tmp_path / "rules.json")

    assert len(store.rules) == 4
    assert all(r.builtin for r in store.rules)
    assert {r.id for r in store.rules} == {
        "builtin_trend", "builtin_rsi_extreme", "builtin_no_stop_loss", "builtin_early_exit",
    }


def test_enabled_rules_excludes_disabled(tmp_path: Path):
    store = RuleConfigStore(tmp_path / "rules.json")
    store.rules[0].enabled = False

    enabled = store.enabled_rules()

    assert store.rules[0] not in enabled
    assert len(enabled) == 3


def test_update_persists_change(tmp_path: Path):
    path = tmp_path / "rules.json"
    store = RuleConfigStore(path)
    rule = store.rules[0]
    rule.severity = SEVERITY_VIOLATION
    rule.enabled = False
    store.update(rule)

    reloaded = RuleConfigStore(path)
    updated = next(r for r in reloaded.rules if r.id == rule.id)
    assert updated.severity == SEVERITY_VIOLATION
    assert updated.enabled is False


def test_add_and_delete_custom_rule(tmp_path: Path):
    path = tmp_path / "rules.json"
    store = RuleConfigStore(path)

    custom = store.new_custom_rule()
    custom.name = "Teszt szabály"
    store.add(custom)

    reloaded = RuleConfigStore(path)
    assert any(r.id == custom.id and r.name == "Teszt szabály" for r in reloaded.rules)

    reloaded.delete(custom.id)
    assert all(r.id != custom.id for r in reloaded.rules)

    final = RuleConfigStore(path)
    assert all(r.id != custom.id for r in final.rules)


def test_corrupt_file_falls_back_to_defaults(tmp_path: Path):
    path = tmp_path / "rules.json"
    path.write_text("{not valid json", encoding="utf-8")

    store = RuleConfigStore(path)

    assert len(store.rules) == 4


def test_new_custom_rule_has_sane_defaults(tmp_path: Path):
    store = RuleConfigStore(tmp_path / "rules.json")
    custom = store.new_custom_rule()

    assert custom.builtin is False
    assert custom.kind == "custom_compare"
    assert custom.params["metric"] in ("rsi", "price_vs_sma")
