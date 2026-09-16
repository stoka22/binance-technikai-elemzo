"""Windows-specifikus segédfüggvények: a rendszer sötét/világos módjának
érzékelése, és a natív sötét címsor bekapcsolása a Tk ablakon.

Egyik függvény sem kritikus: ha bármelyik lépés nem sikerül (nem Windows,
régi Windows build, stb.), csendben visszaesnek az alapértelmezett
(világos) viselkedésre - emiatt nem szabad az alkalmazásnak elszállnia.
"""

import ctypes
import logging
import sys

logger = logging.getLogger(__name__)

# DWMWA_USE_IMMERSIVE_DARK_MODE attribútum-azonosító: Windows 10 1809-2004
# build alatt 19, utána (és Windows 11-en) 20 - mindkettőt megpróbáljuk.
_DARK_TITLEBAR_ATTRIBUTES = (20, 19)


def prefers_dark() -> bool:
    """True, ha a Windows "Szín" beállításokban az alkalmazások sötét módja aktív."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
    except OSError:
        logger.debug("Windows téma-beállítás nem olvasható, világos módra esünk vissza.", exc_info=True)
        return False


def enable_dark_titlebar(window, enabled: bool) -> None:
    """Az ablak címsorát sötétre (vagy vissza világosra) állítja a DWM API-n keresztül.

    Csak vizuális csinosítás a rendszer sötét módjához - ha a Windows build
    nem támogatja, egyszerűen nem történik semmi.
    """
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1 if enabled else 0)
        for attribute in _DARK_TITLEBAR_ATTRIBUTES:
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            )
            if result == 0:
                return
    except OSError:
        logger.debug("Sötét címsor beállítása nem sikerült (nem kritikus).", exc_info=True)
