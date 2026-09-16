# Binance Technikai Elemző

Tanulási célú, grafikus (Tkinter) Windows alkalmazás, amely a Binance publikus
API-járól kér le árfolyamadatokat, és candlestick charton jeleníti meg SMA,
Bollinger szalagok, RSI és MACD indikátorokkal, opcionális élő (automatikus)
frissítéssel.

## Funkciók

- Candlestick chart (mplfinance), Binance márkaszínekkel (`binance` / `binancedark` stílus)
- SMA, Bollinger szalagok, RSI, MACD, volumen - egyenként ki/be kapcsolható panelek
- Élő (automatikus) frissítés testreszabható időközzel
- Egérrel követhető kereszt (crosshair) OHLC tooltippel a charton
- Szimbólum-autocomplete a Binance kereskedhető párjai alapján
- Sötét / világos téma (Nézet menü vagy Beállítások)
- Felugró súgó buborékok (tooltip) minden vezérlőn - Beállításokban ki/bekapcsolható
- Kattintható ⓘ infó gombok az indikátorok mellett (rövid magyar magyarázat)
- Perzisztens beállítások (`%USERPROFILE%\.binance_ta\settings.json`)

## Projekt szerkezet

```
src/binance_ta/
    client.py            Binance REST API kliens (retry/backoff, logging)
    indicators.py         SMA / RSI / MACD / Bollinger számítás (pandas)
    gui.py                 Tkinter GUI + candlestick chart (mplfinance)
    settings.py            Felhasználói beállítások (JSON perzisztencia)
    tooltip.py              Újrahasznosítható hover-tooltip widget
    indicator_info.py       Indikátor-leírások a Súgó menühöz / info gombokhoz
    logging_setup.py       Fájlba forgatott + konzol logging
tests/                     pytest unit tesztek (indikátorok, API kliens, beállítások)
scripts/build_exe.ps1     Önálló .exe csomagolás PyInstaller-rel
```

## Telepítés

A `tkinter` a Windows Store-os / hivatalos python.org-os Python csomagokban
elérhető, néhány egyedi disztribúcióból (pl. PlatformIO venv) hiányzik –
ellenőrizd: `python -c "import tkinter"`.

```powershell
python -m venv .venv
.venv\Scripts\pip install -e .[dev]
```

## Futtatás

```powershell
.venv\Scripts\python.exe -m binance_ta.gui
```

## Tesztelés

```powershell
.venv\Scripts\pytest
```

## Önálló .exe build

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
```

Az eredmény: `dist\BinanceTA.exe`.

## Log fájl és beállítások

- Napló: `%USERPROFILE%\.binance_ta\binance_ta.log` (forgatva, max. 3×1 MB)
- Beállítások: `%USERPROFILE%\.binance_ta\settings.json`
