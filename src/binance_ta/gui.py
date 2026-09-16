"""Grafikus (Tkinter) Windows alkalmazás: Binance árfolyam lekérése,
gyertya (candlestick) chart, SMA / Bollinger / RSI / MACD indikátorok,
élő (automatikus) frissítés, egérrel követhető kereszt (crosshair),
felugró súgó buborékok és beállítások-ablak. A felület induláskor
automatikusan felveszi a Windows aktuális (világos/sötét) rendszertémáját.

Indítás:
    python -m binance_ta.gui
    (vagy telepített csomagként: binance-ta-gui)
"""

import logging
import math
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import mplfinance as mpf
import pandas as pd

import matplotlib

# "Agg" (ablak nélküli) pyplot backend: az mplfinance a `mpf.plot()` hívásban
# pyplot-on keresztül hozza létre a Figure-t, és "TkAgg" esetén ehhez saját,
# rejtett Tk-ablakot is nyitna, ami a mi ablakunk bezárása után is életben
# tartaná a mainloop-ot. Mi a visszaadott Figure-t saját FigureCanvasTkAgg-be
# ágyazzuk be explicit módon, ezért pyplot-nak nincs szüksége GUI backendre.
matplotlib.use("Agg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from binance_ta.client import BinanceAPIError, SymbolInfo, TickerInfo, fetch_klines, get_ticker_prices, get_tradable_symbols
from binance_ta.indicator_info import INDICATOR_INFO
from binance_ta.indicators import add_bollinger_bands, add_macd, add_rsi, add_sma
from binance_ta.logging_setup import configure_logging
from binance_ta.settings import Settings
from binance_ta.symbol_picker import SymbolPickerDialog
from binance_ta.tooltip import ToolTip
from binance_ta.win_theme import enable_dark_titlebar, prefers_dark

logger = logging.getLogger(__name__)

INTERVALS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
MIN_LIVE_REFRESH_SECONDS = 5
WATCHLIST_REFRESH_SECONDS = 15
APP_TITLE = "📈 Binance Technikai Elemző"
APP_VERSION = "0.3.0"

# A chart Binance-stílusa a rendszer aktuális témájához igazodik
# (a mplfinance-nek van kifejezetten erre a célra beépített dark variánsa).
LIGHT_MPF_STYLE = "binance"
DARK_MPF_STYLE = "binancedark"
LIGHT_CROSSHAIR = ("#ffffe0", "#000000")
DARK_CROSSHAIR = ("#2b2b2b", "#ffffff")


class SettingsDialog(tk.Toplevel):
    """Beállítások ablak: téma, tooltipek ki/be, alapértelmezett lekérési paraméterek."""

    def __init__(self, parent: tk.Tk, settings: Settings, on_save):
        super().__init__(parent)
        self.title("⚙ Beállítások")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.settings = settings
        self.on_save = on_save

        self.tooltips_var = tk.BooleanVar(value=settings.show_tooltips)
        self.symbol_var = tk.StringVar(value=settings.default_symbol)
        self.interval_var = tk.StringVar(value=settings.default_interval)
        self.limit_var = tk.StringVar(value=str(settings.default_limit))
        self.live_seconds_var = tk.StringVar(value=str(settings.live_refresh_seconds))

        frm = ttk.Frame(self, padding=16)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Checkbutton(
            frm, text="ℹ Felugró súgó buborékok (tooltip) mutatása", variable=self.tooltips_var
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        ttk.Separator(frm).grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)

        ttk.Label(frm, text="Alapértelmezett értékek", font=("Segoe UI", 10, "bold")).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(6, 6)
        )
        ttk.Label(frm, text="Szimbólum:").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=self.symbol_var, width=14).grid(row=3, column=1, sticky="w")
        ttk.Label(frm, text="Időtáv:").grid(row=4, column=0, sticky="w", pady=2)
        ttk.Combobox(
            frm, textvariable=self.interval_var, values=INTERVALS, width=11, state="readonly"
        ).grid(row=4, column=1, sticky="w")
        ttk.Label(frm, text="Gyertyák száma:").grid(row=5, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=self.limit_var, width=14).grid(row=5, column=1, sticky="w")
        ttk.Label(frm, text="Élő frissítés (mp):").grid(row=6, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=self.live_seconds_var, width=14).grid(row=6, column=1, sticky="w")

        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(btns, text="Mégse", command=self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btns, text="💾 Mentés", command=self._save).pack(side=tk.RIGHT)

    def _save(self):
        try:
            limit = int(self.limit_var.get())
            live_seconds = int(self.live_seconds_var.get())
        except ValueError:
            messagebox.showerror(
                "Hibás bemenet", "A gyertyák száma és az élő frissítés (mp) csak egész szám lehet.", parent=self
            )
            return
        if not (1 <= limit <= 1000):
            messagebox.showerror("Hibás bemenet", "A gyertyák száma 1 és 1000 között lehet.", parent=self)
            return

        self.settings.show_tooltips = self.tooltips_var.get()
        self.settings.default_symbol = self.symbol_var.get().strip().upper() or self.settings.default_symbol
        self.settings.default_interval = self.interval_var.get()
        self.settings.default_limit = limit
        self.settings.live_refresh_seconds = max(MIN_LIVE_REFRESH_SECONDS, live_seconds)
        self.settings.save()

        self.on_save(self.settings)
        self.destroy()


class BinanceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.settings = Settings.load()

        self.title(APP_TITLE)
        self.geometry("1180x820")
        self.minsize(880, 650)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._all_symbols: set[str] = set()
        self._all_symbol_infos: list[SymbolInfo] = []
        self._symbol_info_by_name: dict[str, SymbolInfo] = {}
        self._live_after_id: str | None = None
        self._watchlist_after_id: str | None = None
        self._watchlist_tickers: dict[str, TickerInfo] = {}
        self._watchlist_request_id = 0
        self._tooltips: list[ToolTip] = []
        self.canvas = None
        self.toolbar = None

        self._apply_system_theme()
        self._build_menu()
        self._build_controls()
        self._build_chart_area()
        self._build_statusbar()

        self._load_symbols_async()

    # ---------- Rendszertéma (világos/sötét) ----------

    def _apply_system_theme(self):
        """A Windows aktuális "Alkalmazásszín" beállítását veszi fel indításkor.

        Csak induláskor derítjük ki - ha valaki menet közben átkapcsolja a
        Windows témáját, az alkalmazás újraindítása szükséges a követéshez.
        """
        dark = prefers_dark()
        style = ttk.Style(self)

        if dark:
            style.theme_use("clam")
            bg, fg, field_bg, border = "#202020", "#f2f2f2", "#2b2b2b", "#3f3f3f"

            self.configure(bg=bg)
            style.configure(".", background=bg, foreground=fg, fieldbackground=field_bg, bordercolor=border)
            for name in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton", "TLabelframe", "TLabelframe.Label"):
                style.configure(name, background=bg, foreground=fg)
            style.configure("TButton", background=field_bg, foreground=fg, padding=4)
            style.map("TButton", background=[("active", border)])
            style.configure("TEntry", fieldbackground=field_bg, foreground=fg, insertcolor=fg)
            style.configure("TCombobox", fieldbackground=field_bg, foreground=fg)
            style.map("TCombobox", fieldbackground=[("readonly", field_bg)], foreground=[("readonly", fg)])
            style.configure("TSeparator", background=border)

            self.option_add("*TCombobox*Listbox.background", field_bg)
            self.option_add("*TCombobox*Listbox.foreground", fg)
            self.option_add("*Menu.background", bg)
            self.option_add("*Menu.foreground", fg)
            self.option_add("*Menu.activeBackground", border)
            self.option_add("*Menu.activeForeground", fg)

            self._mpf_style = DARK_MPF_STYLE
            self._crosshair_bg, self._crosshair_fg = DARK_CROSSHAIR
        else:
            style.theme_use("vista")
            self._mpf_style = LIGHT_MPF_STYLE
            self._crosshair_bg, self._crosshair_fg = LIGHT_CROSSHAIR

        enable_dark_titlebar(self, dark)

    # ---------- Menüsor ----------

    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="🚪 Kilépés", command=self._on_close)
        menubar.add_cascade(label="Fájl", menu=file_menu)

        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="⚙ Beállítások...", command=self._open_settings)
        menubar.add_cascade(label="Beállítások", menu=settings_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="ℹ Indikátorok magyarázata", command=self._show_all_indicator_info)
        help_menu.add_separator()
        help_menu.add_command(label="Névjegy", command=self._show_about)
        menubar.add_cascade(label="Súgó", menu=help_menu)

        self.config(menu=menubar)

    def _open_settings(self):
        SettingsDialog(self, self.settings, self._on_settings_saved)

    def _on_settings_saved(self, settings: Settings):
        self.settings = settings
        self.status_var.set("Beállítások elmentve.")

    def _show_indicator_info(self, key: str):
        messagebox.showinfo(f"{key} - mit jelent?", INDICATOR_INFO[key], parent=self)

    def _show_all_indicator_info(self):
        text = "\n\n".join(INDICATOR_INFO[key] for key in ("SMA", "Bollinger", "RSI", "MACD", "Volumen"))
        messagebox.showinfo("Indikátorok magyarázata", text, parent=self)

    def _show_about(self):
        messagebox.showinfo(
            "Névjegy",
            f"{APP_TITLE}\nVerzió {APP_VERSION}\n\n"
            "Tanulási célú alkalmazás candlestick charttal, SMA / RSI / MACD / "
            "Bollinger indikátorokkal, élő frissítéssel és testreszabható beállításokkal.\n\n"
            "Adatforrás: Binance publikus API",
            parent=self,
        )

    # ---------- Tooltip segéd ----------

    def _tooltip(self, widget: tk.Widget, text: str):
        self._tooltips.append(ToolTip(widget, text, enabled_getter=lambda: self.settings.show_tooltips))

    # ---------- UI felépítés ----------

    def _build_controls(self):
        bar = ttk.Frame(self, padding=8)
        bar.pack(side=tk.TOP, fill=tk.X)

        row1 = ttk.Frame(bar)
        row1.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(row1, text="Szimbólum:").pack(side=tk.LEFT, padx=(0, 4))
        self.symbol_var = tk.StringVar(value=self.settings.default_symbol)
        symbol_entry = ttk.Entry(row1, textvariable=self.symbol_var, width=12)
        symbol_entry.pack(side=tk.LEFT, padx=(0, 2))
        self._tooltip(symbol_entry, "Kereskedési pár a Binance-en, pl. BTCUSDT, ETHUSDT.\nVagy nyisd meg a 🔍 szimbólum-választót.")

        picker_btn = ttk.Button(row1, text="🔍", width=3, command=self._open_symbol_picker)
        picker_btn.pack(side=tk.LEFT, padx=(0, 12))
        self._tooltip(picker_btn, "Kereshető szimbólum-választó megnyitása, kedvencekkel (⭐).")

        ttk.Label(row1, text="Időtáv:").pack(side=tk.LEFT, padx=(0, 4))
        self.interval_var = tk.StringVar(value=self.settings.default_interval)
        interval_combo = ttk.Combobox(row1, textvariable=self.interval_var, values=INTERVALS, width=6, state="readonly")
        interval_combo.pack(side=tk.LEFT, padx=(0, 12))
        self._tooltip(interval_combo, "Egy gyertya időtartama (pl. 1h = óránkénti gyertyák).")

        ttk.Label(row1, text="Gyertyák száma:").pack(side=tk.LEFT, padx=(0, 4))
        self.limit_var = tk.StringVar(value=str(self.settings.default_limit))
        limit_entry = ttk.Entry(row1, textvariable=self.limit_var, width=6)
        limit_entry.pack(side=tk.LEFT, padx=(0, 12))
        self._tooltip(limit_entry, "Hány gyertyát töltsön be (1-1000).")

        self.fetch_button = ttk.Button(
            row1, text="🔄 Lekérés és rajzolás", command=lambda: self.on_fetch(manual=True)
        )
        self.fetch_button.pack(side=tk.LEFT, padx=(12, 0))
        self._tooltip(self.fetch_button, "Adatok lekérése a Binance API-ról és a chart újrarajzolása.")

        self.live_var = tk.BooleanVar(value=False)
        live_check = ttk.Checkbutton(row1, text="🔴 Élő frissítés", variable=self.live_var, command=self._on_live_toggle)
        live_check.pack(side=tk.LEFT, padx=(20, 4))
        self._tooltip(live_check, "Bekapcsolva az app a megadott időközönként\nautomatikusan újra lekéri az adatokat.")

        ttk.Label(row1, text="mp-enként:").pack(side=tk.LEFT, padx=(0, 4))
        self.live_interval_var = tk.StringVar(value=str(self.settings.live_refresh_seconds))
        ttk.Entry(row1, textvariable=self.live_interval_var, width=5).pack(side=tk.LEFT)

        indicators = ttk.LabelFrame(bar, text="Indikátorok")
        indicators.pack(side=tk.TOP, fill=tk.X, pady=(8, 0))

        self.sma_enabled = tk.BooleanVar(value=True)
        self.sma_period_var = tk.StringVar(value="20")
        self._add_indicator_cell(indicators, 0, "📈 SMA", self.sma_enabled, self.sma_period_var, "SMA")

        self.bb_enabled = tk.BooleanVar(value=False)
        self.bb_period_var = tk.StringVar(value="20")
        self._add_indicator_cell(indicators, 1, "📊 Bollinger", self.bb_enabled, self.bb_period_var, "Bollinger")

        self.rsi_enabled = tk.BooleanVar(value=True)
        self.rsi_period_var = tk.StringVar(value="14")
        self._add_indicator_cell(indicators, 2, "📉 RSI", self.rsi_enabled, self.rsi_period_var, "RSI")

        self.macd_enabled = tk.BooleanVar(value=False)
        self._add_indicator_cell(indicators, 3, "〰 MACD (12/26/9)", self.macd_enabled, None, "MACD")

        self.volume_enabled = tk.BooleanVar(value=True)
        self._add_indicator_cell(indicators, 4, "▮ Volumen", self.volume_enabled, None, "Volumen")

    def _add_indicator_cell(self, parent, column, label, enabled_var, period_var, info_key):
        cell = ttk.Frame(parent, padding=(8, 4))
        cell.grid(row=0, column=column, sticky="w")

        ttk.Checkbutton(cell, text=label, variable=enabled_var).pack(side=tk.LEFT)

        if period_var is not None:
            ttk.Entry(cell, textvariable=period_var, width=4).pack(side=tk.LEFT, padx=(4, 4))

        info_btn = ttk.Button(cell, text="ⓘ", width=2, command=lambda: self._show_indicator_info(info_key))
        info_btn.pack(side=tk.LEFT, padx=(4, 0))
        self._tooltip(info_btn, f"Kattints a(z) {info_key} indikátor rövid leírásáért.")

    def _build_chart_area(self):
        content = ttk.Frame(self)
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self._build_watchlist(content)

        self.chart_frame = ttk.Frame(content)
        self.chart_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(
            self.chart_frame,
            text="Add meg a szimbólumot és nyomd meg a '🔄 Lekérés és rajzolás' gombot.",
            anchor="center",
        ).pack(expand=True)

    def _build_watchlist(self, parent):
        frame = ttk.LabelFrame(parent, text="⭐ Watchlist", width=210)
        frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        frame.pack_propagate(False)

        columns = ("pair", "price", "change")
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        tree.heading("pair", text="Pár")
        tree.heading("price", text="Ár")
        tree.heading("change", text="24ó %")
        tree.column("pair", width=85, anchor="w")
        tree.column("price", width=70, anchor="e")
        tree.column("change", width=55, anchor="e")
        tree.tag_configure("up", foreground="#0ecb81")
        tree.tag_configure("down", foreground="#f6465d")
        tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 2))
        tree.bind("<<TreeviewSelect>>", self._on_watchlist_select)

        self.watchlist_tree = tree
        self._tooltip(
            tree, "A csillagozott kedvenc szimbólumok friss ára és 24 órás\nváltozása, kb. "
            f"{WATCHLIST_REFRESH_SECONDS} mp-enként frissül. Kattints egy sorra a chart betöltéséhez."
        )

        self._watchlist_empty_label = ttk.Label(
            frame, text="Még nincs kedvenc.\nCsillagozz a 🔍 választóban.",
            foreground="#888888", anchor="center", justify="center", wraplength=190,
        )

        self._render_watchlist()
        self._refresh_watchlist()

    def _build_statusbar(self):
        self.status_var = tk.StringVar(value="Kész.")
        ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(8, 4)).pack(
            side=tk.BOTTOM, fill=tk.X
        )

    # ---------- Szimbólumlista / választó ----------

    def _load_symbols_async(self):
        def worker():
            try:
                infos = get_tradable_symbols()
            except BinanceAPIError as exc:
                logger.warning("Szimbólumlista betöltése sikertelen: %s", exc)
                return
            self.after(0, self._on_symbols_loaded, infos)

        threading.Thread(target=worker, daemon=True).start()

    def _on_symbols_loaded(self, infos: list[SymbolInfo]):
        self._all_symbol_infos = infos
        self._all_symbols = {info.symbol for info in infos}
        self._symbol_info_by_name = {info.symbol: info for info in infos}
        self.status_var.set(f"Kész. ({len(infos)} kereskedhető szimbólum betöltve)")
        self._render_watchlist()

    def _open_symbol_picker(self):
        if not self._all_symbol_infos:
            messagebox.showinfo(
                "Szimbólumlista", "A szimbólumlista még töltődik, próbáld meg pár másodperc múlva.", parent=self
            )
            return
        SymbolPickerDialog(
            self,
            symbols=self._all_symbol_infos,
            favorites=set(self.settings.favorite_symbols),
            current_symbol=self.symbol_var.get().strip().upper(),
            on_select=self._on_symbol_picked,
            on_toggle_favorite=self._on_favorite_toggled,
        )

    def _on_symbol_picked(self, symbol: str):
        self.symbol_var.set(symbol)

    def _on_favorite_toggled(self, symbol: str, is_favorite: bool):
        favorites = self.settings.favorite_symbols
        if is_favorite and symbol not in favorites:
            favorites.append(symbol)
        elif not is_favorite and symbol in favorites:
            favorites.remove(symbol)
        self.settings.save()
        self._refresh_watchlist()

    # ---------- Watchlist (kedvencek árai egyszerre) ----------

    def _refresh_watchlist(self):
        if self._watchlist_after_id is not None:
            self.after_cancel(self._watchlist_after_id)
            self._watchlist_after_id = None

        # A kedvenc-lista (nevek) azonnal megjelenik, még az árak beérkezése előtt is -
        # így pl. egy csillagozás után rögtön látszik az új sor ("…" ár-placeholderrel).
        self._render_watchlist()

        favorites = list(self.settings.favorite_symbols)
        if not favorites:
            self._schedule_next_watchlist_refresh()
            return

        # Ha gyors egymásutánban több kedvenc-váltás is történik, több lekérés is
        # párhuzamosan futhat - csak a legutóbb indítottét fogadjuk el, hogy egy
        # korábban indult, de később visszaérkező (hiányosabb) válasz ne írja
        # felül a frissebbet.
        self._watchlist_request_id += 1
        request_id = self._watchlist_request_id

        def worker():
            try:
                tickers = get_ticker_prices(favorites)
            except BinanceAPIError as exc:
                logger.warning("Watchlist frissítése sikertelen: %s", exc)
                self.after(0, self._schedule_next_watchlist_refresh)
                return
            self.after(0, self._on_watchlist_loaded, tickers, request_id)

        threading.Thread(target=worker, daemon=True).start()

    def _on_watchlist_loaded(self, tickers: list[TickerInfo], request_id: int):
        if request_id != self._watchlist_request_id:
            return  # időközben újabb kérés indult, ez az eredmény már elavult
        self._watchlist_tickers = {t.symbol: t for t in tickers}
        self._render_watchlist()
        self._schedule_next_watchlist_refresh()

    def _schedule_next_watchlist_refresh(self):
        self._watchlist_after_id = self.after(WATCHLIST_REFRESH_SECONDS * 1000, self._refresh_watchlist)

    def _render_watchlist(self):
        tree = self.watchlist_tree
        selected = tree.selection()
        tree.delete(*tree.get_children())

        favorites = self.settings.favorite_symbols
        if not favorites:
            self._watchlist_empty_label.pack(expand=True, pady=20)
            return
        self._watchlist_empty_label.pack_forget()

        tickers = self._watchlist_tickers
        for symbol in favorites:
            info = self._symbol_info_by_name.get(symbol)
            pair_text = info.display if info else symbol
            ticker = tickers.get(symbol)
            if ticker is None:
                tree.insert("", tk.END, iid=symbol, values=(pair_text, "…", ""))
                continue
            price_text = self._format_price(ticker.last_price)
            change_text = f"{ticker.change_percent:+.2f}%"
            tag = "up" if ticker.change_percent >= 0 else "down"
            tree.insert("", tk.END, iid=symbol, values=(pair_text, price_text, change_text), tags=(tag,))

        if selected and selected[0] in favorites:
            tree.selection_set(selected[0])

    @staticmethod
    def _format_price(value: float) -> str:
        if value >= 1:
            return f"{value:,.2f}"
        return f"{value:.8f}".rstrip("0").rstrip(".")

    def _on_watchlist_select(self, _event=None):
        selection = self.watchlist_tree.selection()
        if not selection:
            return
        symbol = selection[0]
        if symbol == self.symbol_var.get().strip().upper():
            return
        self.symbol_var.set(symbol)
        self.on_fetch(manual=True)

    # ---------- Bemenet begyűjtése ----------

    def _gather_options(self) -> dict:
        return {
            "sma": self.sma_enabled.get(),
            "sma_period": int(self.sma_period_var.get()),
            "bollinger": self.bb_enabled.get(),
            "bb_period": int(self.bb_period_var.get()),
            "rsi": self.rsi_enabled.get(),
            "rsi_period": int(self.rsi_period_var.get()),
            "macd": self.macd_enabled.get(),
            "volume": self.volume_enabled.get(),
        }

    # ---------- Adatlekérés ----------

    def on_fetch(self, manual: bool = True):
        self._cancel_live_refresh()

        symbol = self.symbol_var.get().strip().upper()
        interval = self.interval_var.get().strip()

        try:
            limit = int(self.limit_var.get())
            opts = self._gather_options()
        except ValueError:
            messagebox.showerror(
                "Hibás bemenet", "A gyertyák száma és az indikátor-periódusok egész számok kell legyenek."
            )
            return

        if not symbol:
            messagebox.showerror("Hibás bemenet", "Add meg a kereskedési párt, pl. BTCUSDT.")
            return
        if self._all_symbols and symbol not in self._all_symbols:
            messagebox.showerror("Hibás szimbólum", f"'{symbol}' nem található a Binance kereskedhető párjai között.")
            return
        if not (1 <= limit <= 1000):
            messagebox.showerror("Hibás bemenet", "A gyertyák száma 1 és 1000 között lehet.")
            return

        self.fetch_button.state(["disabled"])
        self.status_var.set(f"Lekérés folyamatban: {symbol} ({interval})...")

        thread = threading.Thread(
            target=self._fetch_worker, args=(symbol, interval, limit, opts, manual), daemon=True
        )
        thread.start()

    def _fetch_worker(self, symbol, interval, limit, opts, manual):
        try:
            df = fetch_klines(symbol, interval, limit)
            if opts["sma"]:
                df = add_sma(df, opts["sma_period"])
            if opts["bollinger"]:
                df = add_bollinger_bands(df, opts["bb_period"])
            if opts["rsi"]:
                df = add_rsi(df, opts["rsi_period"])
            if opts["macd"]:
                df = add_macd(df)
        except BinanceAPIError as exc:
            self.after(0, self._on_fetch_error, exc, manual)
            return
        except Exception as exc:  # váratlan hiba (pl. hibás adatformátum)
            logger.exception("Váratlan hiba a lekérés/számítás közben")
            self.after(0, self._on_fetch_error, exc, manual)
            return

        self.after(0, self._on_fetch_success, df, symbol, interval, opts)

    def _on_fetch_error(self, exc: Exception, manual: bool):
        self.fetch_button.state(["!disabled"])
        self.status_var.set(f"Hiba történt a lekérés közben: {exc}")
        if manual:
            messagebox.showerror("Hiba", f"Nem sikerült lekérni az adatokat:\n{exc}")
        self._schedule_live_refresh()

    def _on_fetch_success(self, df, symbol, interval, opts):
        self.fetch_button.state(["!disabled"])
        self._draw_chart(df, symbol, interval, opts)

        last = df.iloc[-1]
        parts = [f"{symbol} | záróár: {last['close']:.2f}"]
        if opts["sma"]:
            sma_col = f"sma_{opts['sma_period']}"
            parts.append(f"SMA{opts['sma_period']}: {last[sma_col]:.2f}")
        if opts["rsi"]:
            rsi_col = f"rsi_{opts['rsi_period']}"
            parts.append(f"RSI{opts['rsi_period']}: {last[rsi_col]:.2f}")
        if opts["macd"]:
            parts.append(f"MACD: {last['macd']:.2f}")
        self.status_var.set(" | ".join(parts))

        self._schedule_live_refresh()

    # ---------- Élő frissítés ----------

    def _on_live_toggle(self):
        if self.live_var.get():
            self.on_fetch(manual=True)
        else:
            self._cancel_live_refresh()

    def _schedule_live_refresh(self):
        self._cancel_live_refresh()
        if not self.live_var.get():
            return
        try:
            seconds = max(MIN_LIVE_REFRESH_SECONDS, int(self.live_interval_var.get()))
        except ValueError:
            seconds = self.settings.live_refresh_seconds
        self._live_after_id = self.after(seconds * 1000, lambda: self.on_fetch(manual=False))

    def _cancel_live_refresh(self):
        if self._live_after_id is not None:
            self.after_cancel(self._live_after_id)
            self._live_after_id = None

    def _on_close(self):
        self._cancel_live_refresh()
        if self._watchlist_after_id is not None:
            self.after_cancel(self._watchlist_after_id)
            self._watchlist_after_id = None
        self.destroy()

    # ---------- Rajzolás ----------

    def _draw_chart(self, df: pd.DataFrame, symbol: str, interval: str, opts: dict):
        for child in self.chart_frame.winfo_children():
            child.destroy()

        indexed = df.set_index("open_time")
        ohlc = indexed[["open", "high", "low", "close", "volume"]].rename(
            columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
        )

        addplots = []
        if opts["sma"]:
            addplots.append(
                mpf.make_addplot(indexed[f"sma_{opts['sma_period']}"], panel=0, color="#1f77b4", width=1.1)
            )
        if opts["bollinger"]:
            addplots.append(
                mpf.make_addplot(indexed[f"bb_upper_{opts['bb_period']}"], panel=0, color="#888888", width=0.8, linestyle="--")
            )
            addplots.append(
                mpf.make_addplot(indexed[f"bb_lower_{opts['bb_period']}"], panel=0, color="#888888", width=0.8, linestyle="--")
            )

        next_panel = 2 if opts["volume"] else 1
        if opts["rsi"]:
            rsi_panel = next_panel
            addplots.append(
                mpf.make_addplot(
                    indexed[f"rsi_{opts['rsi_period']}"], panel=rsi_panel, color="purple",
                    ylabel=f"RSI {opts['rsi_period']}", width=1.1,
                )
            )
            addplots.append(mpf.make_addplot(pd.Series(70, index=indexed.index), panel=rsi_panel, color="red", linestyle="--", width=0.7))
            addplots.append(mpf.make_addplot(pd.Series(30, index=indexed.index), panel=rsi_panel, color="green", linestyle="--", width=0.7))
            next_panel += 1
        if opts["macd"]:
            macd_panel = next_panel
            addplots.append(mpf.make_addplot(indexed["macd"], panel=macd_panel, color="#1f77b4", ylabel="MACD", width=1.1))
            addplots.append(mpf.make_addplot(indexed["macd_signal"], panel=macd_panel, color="#ff7f0e", width=1.1))
            addplots.append(
                mpf.make_addplot(indexed["macd_hist"], panel=macd_panel, type="bar", color="#999999", alpha=0.6, width=0.7)
            )
            next_panel += 1

        fig, axlist = mpf.plot(
            ohlc,
            type="candle",
            style=self._mpf_style,
            addplot=addplots or None,
            volume=opts["volume"],
            returnfig=True,
            figsize=(12, 7),
            title=f"{symbol}  ({interval})",
            ylabel="Ár (USDT)",
            show_nontrading=False,
            datetime_format="%m-%d %H:%M",
            xrotation=15,
            tight_layout=True,
        )

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        toolbar = NavigationToolbar2Tk(canvas, self.chart_frame, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(side=tk.TOP, fill=tk.X)
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas = canvas
        self.toolbar = toolbar

        self._attach_crosshair(axlist[0], df)
        self._attach_scroll_zoom(axlist[0], df)
        self._attach_pan(axlist[0], df)
        self._tooltip(
            canvas.get_tk_widget(),
            "Görgesd az egeret a nagyításhoz/kicsinyítéshez (a kurzor pozíciója körül,\n"
            "az ár-skála arányosan követi). Jobb egérgombbal húzva mozgathatod balra-jobbra.\n"
            "Az eszköztár Home gombja visszaállítja az eredeti nézetet.",
        )

    def _attach_crosshair(self, ax, df: pd.DataFrame):
        """Egérrel követett szaggatott kereszt + OHLC tooltip az ár-panelen."""
        vline = ax.axvline(color="gray", lw=0.6, ls=":", visible=False)
        hline = ax.axhline(color="gray", lw=0.6, ls=":", visible=False)
        annot = ax.annotate(
            "", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
            bbox=dict(boxstyle="round", fc=self._crosshair_bg, ec=self._crosshair_fg, alpha=0.9),
            fontsize=8, color=self._crosshair_fg,
        )
        annot.set_visible(False)
        n = len(df)

        def on_move(event):
            if event.inaxes != ax:
                if vline.get_visible():
                    vline.set_visible(False)
                    hline.set_visible(False)
                    annot.set_visible(False)
                    event.canvas.draw_idle()
                return
            if event.xdata is None:
                return
            x = int(round(event.xdata))
            if x < 0 or x >= n:
                return
            row = df.iloc[x]
            vline.set_xdata([x, x])
            vline.set_visible(True)
            hline.set_ydata([event.ydata, event.ydata])
            hline.set_visible(True)
            annot.xy = (x, event.ydata)
            annot.set_text(
                f"{row['open_time']:%Y-%m-%d %H:%M}\n"
                f"O:{row['open']:.2f}  H:{row['high']:.2f}\n"
                f"L:{row['low']:.2f}  C:{row['close']:.2f}"
            )
            annot.set_visible(True)
            event.canvas.draw_idle()

        ax.figure.canvas.mpl_connect("motion_notify_event", on_move)

    def _rescale_price_y(self, ax, df: pd.DataFrame):
        """Az ár-tengely (y) arányos beállítása a jelenleg látható gyertyákhoz.

        A mplfinance a gyertyákat matplotlib collection-ként rajzolja, amiket
        az `Axes.relim()` nem vesz figyelembe, ezért a látható index-tartomány
        low/high értékeiből kézzel számoljuk ki az új y-tartományt.
        """
        n = len(df)
        xmin, xmax = ax.get_xlim()
        lo = max(0, int(math.floor(xmin)))
        hi = min(n - 1, int(math.ceil(xmax)))
        if lo > hi:
            return

        window = df.iloc[lo : hi + 1]
        y_min = window["low"].min()
        y_max = window["high"].max()
        if pd.isna(y_min) or pd.isna(y_max) or y_min == y_max:
            return

        padding = (y_max - y_min) * 0.08
        ax.set_ylim(y_min - padding, y_max + padding)

    def _attach_scroll_zoom(self, ax, df: pd.DataFrame):
        """Egérgörgővel nagyítás/kicsinyítés a kurzor pozíciója körül (idő tengely).

        A `mpf.plot` panelei egy közös (sharex) idő tengelyen osztoznak, ezért
        elég csak az ár-panel xlim-jét módosítani - a többi panel (volumen,
        RSI, MACD) automatikusan követi. Az ár (y) tengely minden zoomolás
        után arányosan újraszámolódik a látható gyertyákhoz.
        """
        n = len(df)
        min_visible = min(10, n)

        def on_scroll(event):
            if event.xdata is None:
                return

            cur_min, cur_max = ax.get_xlim()
            cur_range = cur_max - cur_min
            if cur_range <= 0:
                return

            zoom_in = event.button == "up"
            factor = 0.85 if zoom_in else 1 / 0.85
            new_range = cur_range * factor
            new_range = max(min_visible, min(new_range, n * 1.3))

            rel = (event.xdata - cur_min) / cur_range
            new_min = event.xdata - rel * new_range
            new_max = new_min + new_range

            ax.set_xlim(new_min, new_max)
            self._rescale_price_y(ax, df)
            event.canvas.draw_idle()

        ax.figure.canvas.mpl_connect("scroll_event", on_scroll)

    def _attach_pan(self, ax, df: pd.DataFrame):
        """Jobb egérgombbal húzva balra-jobbra mozgatható a chart (időben).

        Pixel-alapú elmozdulást számolunk (nem adat-koordinátát), mert a
        húzás közben az xlim - és vele az adat/pixel arány - folyamatosan
        változna, ha a kurzor alatti adat-koordinátát vennénk referenciának.
        """
        state = {}

        def on_press(event):
            if event.button != 3 or event.inaxes != ax:
                return
            state["pixel_x"] = event.x
            state["xlim"] = ax.get_xlim()

        def on_release(event):
            if event.button == 3:
                state.clear()

        def on_motion(event):
            if "pixel_x" not in state or event.x is None:
                return
            xmin, xmax = state["xlim"]
            bbox = ax.get_window_extent()
            if bbox.width <= 0:
                return
            data_per_pixel = (xmax - xmin) / bbox.width
            dx_data = (event.x - state["pixel_x"]) * data_per_pixel

            ax.set_xlim(xmin - dx_data, xmax - dx_data)
            self._rescale_price_y(ax, df)
            event.canvas.draw_idle()

        ax.figure.canvas.mpl_connect("button_press_event", on_press)
        ax.figure.canvas.mpl_connect("button_release_event", on_release)
        ax.figure.canvas.mpl_connect("motion_notify_event", on_motion)


def main() -> None:
    configure_logging()
    logger.info("Binance Technikai Elemző indul")
    app = BinanceApp()
    app.mainloop()


if __name__ == "__main__":
    main()
