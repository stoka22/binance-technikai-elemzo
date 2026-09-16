"""Piac-szűrő ablak: a kereskedhető szimbólumokra (szűrve pl. quote eszközre)
kiszámolja a technikai pontszázalékot, és rangsorolt táblázatban mutatja.

Fontos: ez egy technikai jelzés-szűrő, NEM befektetési tanács - ezt a UI is
egyértelműen jelzi.
"""

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from binance_ta.client import SymbolInfo
from binance_ta.screener import ScanResult, scan_market

QUOTE_FILTER_ALL = "Mind"
SCAN_INTERVALS = ["15m", "30m", "1h", "4h", "1d"]


class ScreenerWindow(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        symbols: list[SymbolInfo],
        min_score: int,
        interval: str,
        on_select,
    ):
        super().__init__(parent)
        self.title("📡 Piac-szűrő")
        self.geometry("700x540")
        self.minsize(600, 420)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._symbols = symbols
        self._min_score = min_score
        self._on_select = on_select
        self._stop_event = threading.Event()
        self._scanning = False
        self._results: list[ScanResult] = []
        self._sorted_ascending = False

        self._build_ui(interval)

    def _build_ui(self, interval: str):
        top = ttk.Frame(self, padding=10)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Quote eszköz:").pack(side=tk.LEFT, padx=(0, 4))
        quote_assets = sorted({s.quote_asset for s in self._symbols})
        default_quote = "USDT" if "USDT" in quote_assets else QUOTE_FILTER_ALL
        self.quote_var = tk.StringVar(value=default_quote)
        ttk.Combobox(
            top, textvariable=self.quote_var, values=[QUOTE_FILTER_ALL] + quote_assets,
            width=8, state="readonly",
        ).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(top, text="Időtáv:").pack(side=tk.LEFT, padx=(0, 4))
        self.interval_var = tk.StringVar(value=interval if interval in SCAN_INTERVALS else "1h")
        ttk.Combobox(
            top, textvariable=self.interval_var, values=SCAN_INTERVALS, width=6, state="readonly",
        ).pack(side=tk.LEFT, padx=(0, 12))

        self.start_button = ttk.Button(top, text="▶ Szűrés indítása", command=self._on_start)
        self.start_button.pack(side=tk.LEFT, padx=(0, 4))
        self.stop_button = ttk.Button(top, text="⏹ Leállítás", command=self._on_stop, state="disabled")
        self.stop_button.pack(side=tk.LEFT)

        ttk.Label(
            self,
            text=(
                "⚠ Ez egy technikai jelzés-szűrő, NEM befektetési tanács. A pontszám azt mutatja, "
                "hogy a klasszikus indikátorok (RSI, MACD, trend, Bollinger) éppen mennyire mutatnak "
                "egy irányba - nem garancia semmire."
            ),
            foreground="#a06000", wraplength=610, justify="left", padding=(10, 4),
        ).pack(side=tk.TOP, fill=tk.X)

        progress_frame = ttk.Frame(self, padding=(10, 2))
        progress_frame.pack(side=tk.TOP, fill=tk.X)
        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100).pack(side=tk.TOP, fill=tk.X)
        self.progress_label = ttk.Label(progress_frame, text="Készen áll.")
        self.progress_label.pack(side=tk.TOP, anchor="w", pady=(4, 0))

        tree_frame = ttk.Frame(self, padding=(10, 4, 10, 10))
        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        columns = ("pair", "score", "direction", "price")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        tree.heading("pair", text="Pár")
        tree.heading("score", text="Pontszám", command=self._toggle_sort)
        tree.heading("direction", text="Jelzés")
        tree.heading("price", text="Ár")
        tree.column("pair", width=100, anchor="w")
        tree.column("score", width=90, anchor="e")
        tree.column("direction", width=150, anchor="center")
        tree.column("price", width=110, anchor="e")
        tree.tag_configure("buy", foreground="#0ecb81")
        tree.tag_configure("sell", foreground="#f6465d")

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        tree.bind("<Double-1>", self._on_row_activate)
        tree.bind("<Return>", self._on_row_activate)
        self.tree = tree

    # ---------- Szken (háttérszálon) ----------

    def _on_start(self):
        if self._scanning:
            return

        quote = self.quote_var.get()
        symbols = [
            (s.symbol, s.display) for s in self._symbols
            if quote == QUOTE_FILTER_ALL or s.quote_asset == quote
        ]
        if not symbols:
            messagebox.showinfo("Piac-szűrő", "Nincs a szűrésnek megfelelő szimbólum.", parent=self)
            return

        self._scanning = True
        self._stop_event = threading.Event()
        self.start_button.state(["disabled"])
        self.stop_button.state(["!disabled"])
        self.tree.delete(*self.tree.get_children())
        self.progress_var.set(0)
        self.progress_label.config(text=f"Szűrés indul: {len(symbols)} szimbólum...")

        interval = self.interval_var.get()
        stop_event = self._stop_event

        def progress_cb(done: int, total: int):
            self.after(0, self._update_progress, done, total)

        def worker():
            results = scan_market(symbols, interval, progress_cb, stop_event)
            self.after(0, self._on_scan_done, results, stop_event)

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress(self, done: int, total: int):
        percent = done / total * 100 if total else 100
        self.progress_var.set(percent)
        self.progress_label.config(text=f"Feldolgozva: {done} / {total}")

    def _on_scan_done(self, results: list[ScanResult], stop_event: threading.Event):
        self._scanning = False
        self.start_button.state(["!disabled"])
        self.stop_button.state(["disabled"])
        self._results = results
        self._sorted_ascending = False
        self._render_results()

        status = "Leállítva" if stop_event.is_set() else "Kész"
        self.progress_label.config(text=f"{status}. {len(results)} szimbólum értékelve.")

    def _on_stop(self):
        self._stop_event.set()
        self.stop_button.state(["disabled"])
        self.progress_label.config(text="Leállítás folyamatban - a folyamatban lévő kérések befejeződnek...")

    def _toggle_sort(self):
        self._sorted_ascending = not self._sorted_ascending
        self._results.sort(key=lambda r: r.score.percent, reverse=not self._sorted_ascending)
        self._render_results()

    # ---------- Megjelenítés ----------

    def _render_results(self):
        tree = self.tree
        tree.delete(*tree.get_children())
        for result in self._results:
            percent = result.score.percent
            if percent >= self._min_score:
                direction, tag = "🟢 Javasolt vétel", "buy"
            elif percent <= 100 - self._min_score:
                direction, tag = "🔴 Javasolt zárás", "sell"
            else:
                direction, tag = "Semleges", ""
            tree.insert(
                "", tk.END, iid=result.symbol,
                values=(result.display, f"{percent:.1f}%", direction, f"{result.last_price:g}"),
                tags=(tag,) if tag else (),
            )

    def _on_row_activate(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        self._on_select(selection[0])

    def _on_close(self):
        self._stop_event.set()
        self.destroy()
