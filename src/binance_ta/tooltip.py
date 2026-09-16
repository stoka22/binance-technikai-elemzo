"""Könnyűsúlyú hover-tooltip (felugró súgó buborék) Tkinter widgetekhez."""

import tkinter as tk
from typing import Callable

SHOW_DELAY_MS = 450


class ToolTip:
    """Egérrel rávitelkor rövid súgó szöveget jelenít meg a widget alatt.

    `enabled_getter` minden megjelenítés előtt lekérdezésre kerül, így a
    beállításokból egy helyen (Settings.show_tooltips) ki/be kapcsolható az
    összes tooltip anélkül, hogy újra kellene kötni az egér-eseményeket.
    """

    def __init__(self, widget: tk.Widget, text: str, enabled_getter: Callable[[], bool] = lambda: True):
        self.widget = widget
        self.text = text
        self.enabled_getter = enabled_getter
        self._tip_window: tk.Toplevel | None = None
        self._after_id: str | None = None

        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._unschedule()
        self._after_id = self.widget.after(SHOW_DELAY_MS, self._show)

    def _unschedule(self):
        if self._after_id is not None:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self):
        self._after_id = None
        if not self.enabled_getter() or self._tip_window is not None:
            return

        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

        self._tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        try:
            tw.wm_attributes("-topmost", True)
        except tk.TclError:
            pass

        tk.Label(
            tw, text=self.text, justify=tk.LEFT, background="#ffffe0", foreground="#000000",
            relief=tk.SOLID, borderwidth=1, padx=6, pady=4, font=("Segoe UI", 9), wraplength=300,
        ).pack()

    def _hide(self, _event=None):
        self._unschedule()
        if self._tip_window is not None:
            self._tip_window.destroy()
            self._tip_window = None
