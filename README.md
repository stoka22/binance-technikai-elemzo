# Binance Technikai Elemző

Tanulási célú, grafikus (Tkinter) Windows alkalmazás, amely a Binance publikus
API-járól kér le árfolyamadatokat, és candlestick charton jeleníti meg SMA,
Bollinger szalagok, RSI és MACD indikátorokkal, opcionális élő (automatikus)
frissítéssel.

## Projekt szerkezet

```
src/binance_ta/
    client.py          Binance REST API kliens (retry/backoff, logging)
    indicators.py       SMA / RSI / MACD / Bollinger számítás (pandas)
    gui.py               Tkinter GUI + candlestick chart (mplfinance)
    logging_setup.py    Fájlba forgatott + konzol logging
tests/                   pytest unit tesztek (indikátorok, API kliens mockolva)
scripts/build_exe.ps1   Önálló .exe csomagolás PyInstaller-rel
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

## Log fájl

Az alkalmazás a `%USERPROFILE%\.binance_ta\binance_ta.log` fájlba írja a
naplót (forgatva, max. 3×1 MB).
