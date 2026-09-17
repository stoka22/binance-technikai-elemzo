"""Szabályok kezelése ablak: beépített és saját (egyéni) szabályok listázása,
ki/bekapcsolása, szerkesztése, törlése, valamint új egyéni szabály létrehozása
biztonságos, előre definiált építőelemekből (nincs szabad kódfuttatás)."""

import tkinter as tk
from tkinter import messagebox, ttk

from binance_ta.rule_config import (
    KIND_CUSTOM_COMPARE,
    KIND_EARLY_EXIT,
    KIND_LOSS_THRESHOLD,
    KIND_RSI_EXTREME,
    KIND_TREND,
    KIND_LABELS,
    SEVERITY_ICONS,
    SEVERITY_LABELS,
    SEVERITIES,
    RuleConfig,
    RuleConfigStore,
)

METRIC_LABELS = {"rsi": "RSI", "price_vs_sma": "Ár távolsága a SMA-tól (%)"}
COMPARATOR_LABELS = {"above": "nagyobb, mint", "below": "kisebb, mint"}
APPLIES_TO_LABELS = {"long": "csak Long", "short": "csak Short", "both": "Long és Short is"}

# (param_key, felirat, típus, választható értékek [choice esetén])
PARAM_SPECS: dict[str, list[tuple]] = {
    KIND_TREND: [("sma_period", "SMA periódus", "int")],
    KIND_RSI_EXTREME: [
        ("rsi_period", "RSI periódus", "int"),
        ("overbought", "Túlvett küszöb (RSI)", "float"),
        ("oversold", "Túladott küszöb (RSI)", "float"),
    ],
    KIND_LOSS_THRESHOLD: [("loss_percent", "Veszteség küszöb (%, negatív szám)", "float")],
    KIND_EARLY_EXIT: [
        ("lookahead_candles", "Előretekintés (gyertyák száma)", "int"),
        ("min_missed_percent", "Min. elmulasztott hozam (%)", "float"),
    ],
    KIND_CUSTOM_COMPARE: [
        ("metric", "Mit nézzen", "choice", METRIC_LABELS),
        ("period", "Periódus", "int"),
        ("comparator", "Feltétel", "choice", COMPARATOR_LABELS),
        ("threshold", "Érték", "float"),
        ("applies_to", "Mikor érvényes", "choice", APPLIES_TO_LABELS),
    ],
}


class RulesWindow(tk.Toplevel):
    def __init__(self, parent: tk.Widget, store: RuleConfigStore):
        super().__init__(parent)
        self.title("⚙ Szabályok kezelése")
        self.geometry("680x440")
        self.minsize(580, 360)
        self.transient(parent)

        self.store = store
        self._build_ui()
        self._render()

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(top, text="➕ Új szabály", command=self._on_add).pack(side=tk.LEFT)
        ttk.Button(top, text="✏ Szerkesztés", command=self._on_edit).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(top, text="🗑 Törlés", command=self._on_delete).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(
            self,
            text="A ✓ oszlopra kattintva gyorsan ki/bekapcsolhatod a szabályt. Dupla­kattintás: szerkesztés.",
            foreground="#666666", font=("Segoe UI", 8), padding=(10, 0),
        ).pack(side=tk.TOP, fill=tk.X)

        columns = ("enabled", "name", "severity", "kind")
        tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        tree.heading("enabled", text="✓")
        tree.heading("name", text="Szabály")
        tree.heading("severity", text="Súlyosság")
        tree.heading("kind", text="Típus")
        tree.column("enabled", width=32, anchor="center", stretch=False)
        tree.column("name", width=260, anchor="w")
        tree.column("severity", width=150, anchor="w")
        tree.column("kind", width=140, anchor="w")
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 10))

        tree.bind("<Button-1>", self._on_click)
        tree.bind("<Double-1>", self._on_row_double_click)

        self.tree = tree

    def _render(self):
        tree = self.tree
        selected = tree.selection()
        tree.delete(*tree.get_children())

        for rule in self.store.rules:
            check = "☑" if rule.enabled else "☐"
            severity_text = f"{SEVERITY_ICONS[rule.severity]} {SEVERITY_LABELS[rule.severity]}"
            kind_text = KIND_LABELS.get(rule.kind, rule.kind) + (" (beépített)" if rule.builtin else "")
            tree.insert("", tk.END, iid=rule.id, values=(check, rule.name, severity_text, kind_text))

        if selected and tree.exists(selected[0]):
            tree.selection_set(selected[0])

    def _selected_rule(self) -> RuleConfig | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return next((r for r in self.store.rules if r.id == selection[0]), None)

    def _on_click(self, event):
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        row = self.tree.identify_row(event.y)
        if not row or self.tree.identify_column(event.x) != "#1":
            return
        rule = next((r for r in self.store.rules if r.id == row), None)
        if rule is None:
            return
        rule.enabled = not rule.enabled
        self.store.update(rule)
        self._render()

    def _on_row_double_click(self, _event=None):
        self._on_edit()

    def _on_add(self):
        rule = self.store.new_custom_rule()
        RuleEditDialog(self, rule, is_new=True, on_save=self._on_rule_saved)

    def _on_edit(self):
        rule = self._selected_rule()
        if rule is None:
            messagebox.showinfo("Szerkesztés", "Válassz ki egy szabályt a listából.", parent=self)
            return
        RuleEditDialog(self, rule, is_new=False, on_save=self._on_rule_saved)

    def _on_rule_saved(self, rule: RuleConfig, is_new: bool):
        if is_new:
            self.store.add(rule)
        else:
            self.store.update(rule)
        self._render()

    def _on_delete(self):
        rule = self._selected_rule()
        if rule is None:
            messagebox.showinfo("Törlés", "Válassz ki egy szabályt a listából.", parent=self)
            return
        if rule.builtin:
            messagebox.showerror(
                "Törlés", "A beépített szabályok nem törölhetők - de kikapcsolhatod a ✓ oszlopra kattintva.",
                parent=self,
            )
            return
        if not messagebox.askyesno("Törlés", f"Biztosan törlöd a(z) „{rule.name}” szabályt?", parent=self):
            return
        self.store.delete(rule.id)
        self._render()


class RuleEditDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, rule: RuleConfig, is_new: bool, on_save):
        super().__init__(parent)
        self.rule = rule
        self.is_new = is_new
        self.on_save = on_save

        self.title("➕ Új szabály" if is_new else f"✏ {rule.name}")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self, padding=16)
        frm.pack(fill=tk.BOTH, expand=True)
        row = 0

        ttk.Label(frm, text="Név:").grid(row=row, column=0, sticky="w", pady=2)
        self.name_var = tk.StringVar(value=self.rule.name)
        ttk.Entry(frm, textvariable=self.name_var, width=32).grid(row=row, column=1, columnspan=2, sticky="w")
        row += 1

        ttk.Label(frm, text="Súlyosság:").grid(row=row, column=0, sticky="w", pady=2)
        self.severity_display_to_value = {f"{SEVERITY_ICONS[s]} {SEVERITY_LABELS[s]}": s for s in SEVERITIES}
        self.severity_var = tk.StringVar(
            value=f"{SEVERITY_ICONS[self.rule.severity]} {SEVERITY_LABELS[self.rule.severity]}"
        )
        ttk.Combobox(
            frm, textvariable=self.severity_var, state="readonly", width=20,
            values=list(self.severity_display_to_value.keys()),
        ).grid(row=row, column=1, columnspan=2, sticky="w")
        row += 1

        self.enabled_var = tk.BooleanVar(value=self.rule.enabled)
        ttk.Checkbutton(frm, text="Bekapcsolva", variable=self.enabled_var).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(2, 8)
        )
        row += 1

        ttk.Separator(frm).grid(row=row, column=0, columnspan=3, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text=f"Beállítások ({KIND_LABELS.get(self.rule.kind, self.rule.kind)})", font=("Segoe UI", 9, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(4, 4)
        )
        row += 1

        self.param_vars: dict[str, tk.Variable] = {}
        self.param_choice_maps: dict[str, dict] = {}
        specs = PARAM_SPECS.get(self.rule.kind, [])
        for spec in specs:
            key, label, kind = spec[0], spec[1], spec[2]
            ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="w", pady=2)
            if kind == "choice":
                choices: dict = spec[3]
                display_to_value = {v: k for k, v in choices.items()}
                self.param_choice_maps[key] = display_to_value
                current_value = self.rule.params.get(key)
                var = tk.StringVar(value=choices.get(current_value, next(iter(choices.values()))))
                ttk.Combobox(
                    frm, textvariable=var, state="readonly", width=28, values=list(choices.values()),
                ).grid(row=row, column=1, columnspan=2, sticky="w")
            else:
                default = self.rule.params.get(key, 0)
                var = tk.StringVar(value=str(default))
                ttk.Entry(frm, textvariable=var, width=14).grid(row=row, column=1, sticky="w")
            self.param_vars[key] = var
            row += 1

        ttk.Label(frm, text="Leírás (a felugró üzenetben jelenik meg):").grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(8, 2)
        )
        row += 1
        self.description_text = tk.Text(frm, width=44, height=4, wrap="word")
        self.description_text.insert("1.0", self.rule.description)
        self.description_text.grid(row=row, column=0, columnspan=3, sticky="w")
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Mégse", command=self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btns, text="💾 Mentés", command=self._save).pack(side=tk.RIGHT)

    def _save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Hibás bemenet", "A szabály neve nem lehet üres.", parent=self)
            return

        new_params = {}
        specs = PARAM_SPECS.get(self.rule.kind, [])
        try:
            for spec in specs:
                key, _label, kind = spec[0], spec[1], spec[2]
                if kind == "choice":
                    display_value = self.param_vars[key].get()
                    new_params[key] = self.param_choice_maps[key][display_value]
                elif kind == "int":
                    new_params[key] = int(self.param_vars[key].get())
                else:
                    new_params[key] = float(self.param_vars[key].get())
        except ValueError:
            messagebox.showerror("Hibás bemenet", "A számmezők csak számot tartalmazhatnak.", parent=self)
            return

        self.rule.name = name
        self.rule.severity = self.severity_display_to_value[self.severity_var.get()]
        self.rule.enabled = self.enabled_var.get()
        self.rule.params = new_params
        self.rule.description = self.description_text.get("1.0", "end").strip()

        self.on_save(self.rule, self.is_new)
        self.destroy()
