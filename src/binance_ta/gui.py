"""Grafikus (Tkinter) Windows alkalmazás: Binance árfolyam lekérése,
gyertya (candlestick) chart, SMA / Bollinger / RSI / MACD indikátorok,
élő (automatikus) frissítés és egérrel követhető kereszt (crosshair).

Indítás:
    python -m binance_ta.gui
    (vagy telepített csomagként: binance-ta-gui)
"""

import logging
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

from binance_ta.client import BinanceAPIError, fetch_klines, get_exchange_symbols
from binance_ta.indicators import add_bollinger_bands, add_macd, add_rsi, add_sma
from binance_ta.logging_setup import configure_logging

logger = logging.getLogger(__name__)

INTERVALS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
MIN_LIVE_REFRESH_SECONDS = 5


class BinanceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Binance Technikai Elemző")
        self.geometry("1150x800")
        self.minsize(850, 650)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._all_symbols: list[str] = []
        self._live_after_id: str | None = None
        self.canvas = None
        self.toolbar = None

        self._build_controls()
        self._build_chart_area()
        self._build_statusbar()

        self._load_symbols_async()

    # ---------- UI felépítés ----------

    def _build_controls(self):
        bar = ttk.Frame(self, padding=8)
        bar.pack(side=tk.TOP, fill=tk.X)

        row1 = ttk.Frame(bar)
        row1.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(row1, text="Szimbólum:").pack(side=tk.LEFT, padx=(0, 4))
        self.symbol_var = tk.StringVar(value="BTCUSDT")
        self.symbol_combo = ttk.Combobox(row1, textvariable=self.symbol_var, width=12)
        self.symbol_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.symbol_combo.bind("<KeyRelease>", self._on_symbol_keyrelease)

        ttk.Label(row1, text="Időtáv:").pack(side=tk.LEFT, padx=(0, 4))
        self.interval_var = tk.StringVar(value="1h")
        ttk.Combobox(
            row1, textvariable=self.interval_var, values=INTERVALS, width=6, state="readonly"
        ).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(row1, text="Gyertyák száma:").pack(side=tk.LEFT, padx=(0, 4))
        self.limit_var = tk.StringVar(value="300")
        ttk.Entry(row1, textvariable=self.limit_var, width=6).pack(side=tk.LEFT, padx=(0, 12))

        self.fetch_button = ttk.Button(row1, text="Lekérés és rajzolás", command=lambda: self.on_fetch(manual=True))
        self.fetch_button.pack(side=tk.LEFT, padx=(12, 0))

        self.live_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            row1, text="Élő frissítés", variable=self.live_var, command=self._on_live_toggle
        ).pack(side=tk.LEFT, padx=(20, 4))

        ttk.Label(row1, text="mp-enként:").pack(side=tk.LEFT, padx=(0, 4))
        self.live_interval_var = tk.StringVar(value="30")
        ttk.Entry(row1, textvariable=self.live_interval_var, width=5).pack(side=tk.LEFT)

        row2 = ttk.Frame(bar)
        row2.pack(side=tk.TOP, fill=tk.X, pady=(6, 0))

        self.sma_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="SMA", variable=self.sma_enabled).pack(side=tk.LEFT)
        self.sma_period_var = tk.StringVar(value="20")
        ttk.Entry(row2, textvariable=self.sma_period_var, width=4).pack(side=tk.LEFT, padx=(2, 16))

        self.bb_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="Bollinger", variable=self.bb_enabled).pack(side=tk.LEFT)
        self.bb_period_var = tk.StringVar(value="20")
        ttk.Entry(row2, textvariable=self.bb_period_var, width=4).pack(side=tk.LEFT, padx=(2, 16))

        self.rsi_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="RSI", variable=self.rsi_enabled).pack(side=tk.LEFT)
        self.rsi_period_var = tk.StringVar(value="14")
        ttk.Entry(row2, textvariable=self.rsi_period_var, width=4).pack(side=tk.LEFT, padx=(2, 16))

        self.macd_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="MACD (12/26/9)", variable=self.macd_enabled).pack(side=tk.LEFT, padx=(0, 16))

        self.volume_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="Volumen", variable=self.volume_enabled).pack(side=tk.LEFT)

    def _build_chart_area(self):
        self.chart_frame = ttk.Frame(self)
        self.chart_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        ttk.Label(
            self.chart_frame,
            text="Add meg a szimbólumot és nyomd meg a 'Lekérés és rajzolás' gombot.",
            anchor="center",
        ).pack(expand=True)

    def _build_statusbar(self):
        self.status_var = tk.StringVar(value="Kész.")
        ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(8, 4)).pack(
            side=tk.BOTTOM, fill=tk.X
        )

    # ---------- Szimbólumlista / autocomplete ----------

    def _load_symbols_async(self):
        def worker():
            try:
                symbols = get_exchange_symbols()
            except BinanceAPIError as exc:
                logger.warning("Szimbólumlista betöltése sikertelen: %s", exc)
                return
            self.after(0, self._on_symbols_loaded, symbols)

        threading.Thread(target=worker, daemon=True).start()

    def _on_symbols_loaded(self, symbols: list[str]):
        self._all_symbols = symbols
        self.symbol_combo["values"] = symbols
        self.status_var.set(f"Kész. ({len(symbols)} kereskedhető szimbólum betöltve)")

    def _on_symbol_keyrelease(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        typed = self.symbol_var.get().upper()
        if not self._all_symbols:
            return
        matches = [s for s in self._all_symbols if typed in s] if typed else self._all_symbols
        self.symbol_combo["values"] = matches[:30]

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
            seconds = 30
        self._live_after_id = self.after(seconds * 1000, lambda: self.on_fetch(manual=False))

    def _cancel_live_refresh(self):
        if self._live_after_id is not None:
            self.after_cancel(self._live_after_id)
            self._live_after_id = None

    def _on_close(self):
        self._cancel_live_refresh()
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
            style="yahoo",
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

    def _attach_crosshair(self, ax, df: pd.DataFrame):
        """Egérrel követett szaggatott kereszt + OHLC tooltip az ár-panelen."""
        vline = ax.axvline(color="gray", lw=0.6, ls=":", visible=False)
        hline = ax.axhline(color="gray", lw=0.6, ls=":", visible=False)
        annot = ax.annotate(
            "", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
            bbox=dict(boxstyle="round", fc="white", alpha=0.85), fontsize=8,
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


def main() -> None:
    configure_logging()
    logger.info("Binance Technikai Elemző indul")
    app = BinanceApp()
    app.mainloop()


if __name__ == "__main__":
    main()
