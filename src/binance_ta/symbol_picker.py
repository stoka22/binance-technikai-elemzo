"""Kereshető szimbólum-választó ablak: "BASE/QUOTE" formázás, élő szűrés
gépelés közben és csillagozható kedvencek - ahogy a Binance/TradingView
kereskedési felületén megszokott, nem egy sima legördülő lista."""

import tkinter as tk
from tkinter import ttk

from binance_ta.client import SymbolInfo

STAR_ON = "★"
STAR_OFF = "☆"


class SymbolPickerDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        symbols: list[SymbolInfo],
        favorites: set[str],
        current_symbol: str,
        on_select,
        on_toggle_favorite,
    ):
        super().__init__(parent)
        self.title("🔍 Szimbólum kiválasztása")
        self.geometry("380x480")
        self.minsize(320, 360)
        self.transient(parent)
        self.grab_set()

        self._symbols = symbols
        self._favorites = favorites
        self._current_symbol = current_symbol
        self._on_select = on_select
        self._on_toggle_favorite = on_toggle_favorite

        self._build_ui()
        self._populate("")

        self.search_var.trace_add("write", lambda *_: self._populate(self.search_var.get()))
        self.bind("<Escape>", lambda _e: self.destroy())
        self.search_entry.focus_set()

    def _build_ui(self):
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(frm, textvariable=self.search_var)
        self.search_entry.pack(fill=tk.X, pady=(0, 8))
        self.search_entry.bind("<Return>", self._on_activate)
        self.search_entry.bind("<Down>", self._focus_tree)

        tree_frame = ttk.Frame(frm)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("star", "pair")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        tree.heading("star", text="")
        tree.heading("pair", text="Kereskedési pár")
        tree.column("star", width=32, anchor="center", stretch=False)
        tree.column("pair", width=260, anchor="w")
        tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.bind("<Button-1>", self._on_click)
        tree.bind("<Double-1>", self._on_activate)
        tree.bind("<Return>", self._on_activate)

        self.tree = tree

        ttk.Label(
            frm, text="Kattints a ☆ ikonra a kedvencekhez adáshoz - duplaklikk vagy Enter a kiválasztáshoz.",
            foreground="#666666", font=("Segoe UI", 8), wraplength=340,
        ).pack(fill=tk.X, pady=(8, 0))

    def _populate(self, filter_text: str):
        tree = self.tree
        tree.delete(*tree.get_children())

        needle = filter_text.strip().upper()
        matches = [
            info for info in self._symbols
            if not needle or needle in info.symbol or needle in info.display
        ]
        matches.sort(key=lambda info: (info.symbol not in self._favorites, info.symbol))

        select_iid = None
        for info in matches:
            star = STAR_ON if info.symbol in self._favorites else STAR_OFF
            tree.insert("", tk.END, iid=info.symbol, values=(star, info.display))
            if info.symbol == self._current_symbol:
                select_iid = info.symbol

        if select_iid:
            tree.selection_set(select_iid)
            tree.see(select_iid)
        elif matches:
            tree.selection_set(matches[0].symbol)

    def _focus_tree(self, _event=None):
        children = self.tree.get_children()
        if children:
            self.tree.focus_set()
            self.tree.focus(children[0])
            self.tree.selection_set(children[0])
        return "break"

    def _on_click(self, event):
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        row = self.tree.identify_row(event.y)
        if not row:
            return
        if self.tree.identify_column(event.x) == "#1":  # csillag oszlop
            self._toggle_favorite(row)
            return "break"

    def _toggle_favorite(self, symbol: str):
        is_now_favorite = symbol not in self._favorites
        if is_now_favorite:
            self._favorites.add(symbol)
        else:
            self._favorites.discard(symbol)
        self._on_toggle_favorite(symbol, is_now_favorite)
        self._populate(self.search_var.get())

    def _on_activate(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        self._on_select(selection[0])
        self.destroy()
