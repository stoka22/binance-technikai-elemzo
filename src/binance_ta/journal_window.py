"""Kereskedési napló kimutatás: a gyakorló ügyletek statisztikája és a
klasszikus alapszabályok szerint automatikusan kimutatott, leggyakoribb hibák."""

import logging
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from binance_ta.rule_config import SEVERITY_ICONS, RuleConfigStore
from binance_ta.trade_journal import TradeJournal
from binance_ta.trade_rules import evaluate_trade

logger = logging.getLogger(__name__)


class JournalWindow(tk.Toplevel):
    def __init__(self, parent: tk.Widget, journal: TradeJournal, fetch_klines_fn, rule_store: RuleConfigStore, on_manage_rules):
        super().__init__(parent)
        self.title("📒 Kereskedési napló")
        self.geometry("780x560")
        self.minsize(640, 440)
        self.transient(parent)

        self.journal = journal
        self._fetch_klines_fn = fetch_klines_fn
        self._rules = rule_store.enabled_rules()
        self._on_manage_rules = on_manage_rules
        self.violations_by_trade: dict[str, list] = {}

        self._build_ui()
        self._render()
        self._compute_violations_async()

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(top, text="⚙ Szabályok kezelése", command=self._on_manage_rules).pack(side=tk.LEFT)
        ttk.Button(top, text="🗑 Kijelölt törlése", command=self._on_delete_selected).pack(side=tk.LEFT, padx=(8, 0))
        self.status_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.status_var, foreground="#888888").pack(side=tk.LEFT, padx=(12, 0))

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.summary_var, padding=(10, 4), font=("Segoe UI", 10, "bold")).pack(
            side=tk.TOP, fill=tk.X
        )

        body = ttk.Frame(self, padding=(10, 0, 10, 10))
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        trades_frame = ttk.LabelFrame(body, text="Ügyletek")
        trades_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        columns = ("symbol", "direction", "entry", "exit", "pnl", "issues")
        tree = ttk.Treeview(trades_frame, columns=columns, show="headings", selectmode="browse")
        tree.heading("symbol", text="Szimbólum")
        tree.heading("direction", text="Irány")
        tree.heading("entry", text="Belépés")
        tree.heading("exit", text="Kilépés")
        tree.heading("pnl", text="P&L")
        tree.heading("issues", text="Hibák")
        tree.column("symbol", width=90, anchor="w")
        tree.column("direction", width=55, anchor="center")
        tree.column("entry", width=110, anchor="w")
        tree.column("exit", width=110, anchor="w")
        tree.column("pnl", width=65, anchor="e")
        tree.column("issues", width=50, anchor="center")
        tree.tag_configure("win", foreground="#0ecb81")
        tree.tag_configure("loss", foreground="#f6465d")
        tree.tag_configure("open", foreground="#888888")
        tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        vsb = ttk.Scrollbar(trades_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.bind("<<TreeviewSelect>>", self._on_trade_selected)
        self.tree = tree

        right = ttk.Frame(body, width=250)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))
        right.pack_propagate(False)

        ttk.Label(right, text="Leggyakoribb hibák", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.mistakes_list = tk.Listbox(right, height=8, activestyle="none")
        self.mistakes_list.pack(fill=tk.X, pady=(4, 12))

        ttk.Label(right, text="Kijelölt ügylet", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.detail_var = tk.StringVar(value="Válassz egy ügyletet a listából.")
        ttk.Label(right, textvariable=self.detail_var, wraplength=230, justify="left").pack(
            anchor="w", fill=tk.X, pady=(4, 0)
        )

    # ---------- Megjelenítés ----------

    def _render(self):
        tree = self.tree
        selected = tree.selection()
        tree.delete(*tree.get_children())

        closed = self.journal.closed_trades()
        wins = [t for t in closed if t.pnl_percent > 0]
        losses = [t for t in closed if t.pnl_percent <= 0]
        win_rate = len(wins) / len(closed) * 100 if closed else 0.0
        avg_win = sum(t.pnl_percent for t in wins) / len(wins) if wins else 0.0
        avg_loss = sum(t.pnl_percent for t in losses) / len(losses) if losses else 0.0
        gross_win = sum(t.pnl_percent for t in wins)
        gross_loss = abs(sum(t.pnl_percent for t in losses))
        if gross_loss > 0:
            profit_factor_text = f"{gross_win / gross_loss:.2f}"
        else:
            profit_factor_text = "∞" if gross_win > 0 else "-"

        self.summary_var.set(
            f"Lezárt ügyletek: {len(closed)}   |   Nyerő arány: {win_rate:.0f}%   |   "
            f"Átlag nyereség: {avg_win:+.1f}%   |   Átlag veszteség: {avg_loss:+.1f}%   |   "
            f"Profit faktor: {profit_factor_text}"
        )

        for trade in reversed(self.journal.trades):
            if trade.is_open:
                tag, pnl_text = "open", "nyitva"
            else:
                tag = "win" if trade.pnl_percent > 0 else "loss"
                pnl_text = f"{trade.pnl_percent:+.1f}%"
            issue_count = len(self.violations_by_trade.get(trade.id, []))
            tree.insert(
                "", tk.END, iid=trade.id,
                values=(
                    trade.symbol,
                    "Long" if trade.direction == "long" else "Short",
                    trade.entry_time[:16].replace("T", " "),
                    trade.exit_time[:16].replace("T", " ") if trade.exit_time else "-",
                    pnl_text,
                    issue_count if issue_count else "",
                ),
                tags=(tag,),
            )

        if selected and tree.exists(selected[0]):
            tree.selection_set(selected[0])

        self._render_mistake_frequency(closed)

    def _render_mistake_frequency(self, closed_trades):
        counts: dict[str, int] = {}
        for trade in closed_trades:
            for violation in self.violations_by_trade.get(trade.id, []):
                counts[violation.rule_id] = counts.get(violation.rule_id, 0) + 1

        names: dict[str, str] = {}
        severities: dict[str, str] = {}
        for trade in closed_trades:
            for violation in self.violations_by_trade.get(trade.id, []):
                names[violation.rule_id] = violation.name
                severities[violation.rule_id] = violation.severity

        self.mistakes_list.delete(0, tk.END)
        if not counts:
            self.mistakes_list.insert(tk.END, "Még nincs elég adat.")
            return
        for rule_id, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
            icon = SEVERITY_ICONS.get(severities.get(rule_id, ""), "")
            self.mistakes_list.insert(tk.END, f"{count}×  {icon} {names.get(rule_id, rule_id)}")

    def _on_trade_selected(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        trade = next((t for t in self.journal.trades if t.id == selection[0]), None)
        if trade is None:
            return
        lines = [
            f"{trade.symbol} ({trade.interval}) - {'Long' if trade.direction == 'long' else 'Short'}",
            f"Belépés: {trade.entry_price:g}",
            f"  {trade.entry_time[:16].replace('T', ' ')}",
        ]
        if trade.exit_price is not None:
            lines.append(f"Kilépés: {trade.exit_price:g}")
            lines.append(f"  {trade.exit_time[:16].replace('T', ' ')}")
            lines.append(f"Eredmény: {trade.pnl_percent:+.2f}%")
        violations = self.violations_by_trade.get(trade.id, [])
        if violations:
            lines.append("")
            lines.append("Észlelt jelzések:")
            for v in violations:
                lines.append(f"{SEVERITY_ICONS.get(v.severity, '')} {v.message}")
        self.detail_var.set("\n".join(lines))

    def _on_delete_selected(self):
        selection = self.tree.selection()
        if not selection:
            return
        if not messagebox.askyesno("Törlés", "Biztosan törlöd a kijelölt ügyletet?", parent=self):
            return
        self.journal.delete(selection[0])
        self.violations_by_trade.pop(selection[0], None)
        self._render()

    # ---------- Szabálysértések kiszámítása (háttérszálon) ----------

    def _compute_violations_async(self):
        closed = self.journal.closed_trades()
        symbols = sorted({t.symbol for t in closed})
        if not symbols:
            return

        self.status_var.set("Hibák elemzése folyamatban...")

        def worker():
            violations: dict[str, list] = {}
            for symbol in symbols:
                trades_for_symbol = [t for t in closed if t.symbol == symbol]
                interval = trades_for_symbol[0].interval
                try:
                    df = self._fetch_klines_fn(symbol, interval, 1000)
                except Exception:
                    logger.warning("Nem sikerült historikus adatot lekérni a napló elemzéséhez (%s)", symbol)
                    continue
                for trade in trades_for_symbol:
                    try:
                        violations[trade.id] = evaluate_trade(df, trade, self._rules)
                    except Exception:
                        logger.exception("Hiba az ügylet kiértékelésekor (%s)", trade.id)
            self.after(0, self._on_violations_ready, violations)

        threading.Thread(target=worker, daemon=True).start()

    def _on_violations_ready(self, violations: dict[str, list]):
        self.violations_by_trade = violations
        self.status_var.set("")
        self._render()
