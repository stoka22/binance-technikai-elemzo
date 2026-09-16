# Binance Technikai Elemző

Tanulási célú, grafikus (Tkinter) Windows alkalmazás, amely a Binance publikus
API-járól kér le árfolyamadatokat, és candlestick charton jeleníti meg SMA,
Bollinger szalagok, RSI és MACD indikátorokkal, opcionális élő (automatikus)
frissítéssel.

## Funkciók

- Candlestick chart (mplfinance), Binance márkaszínekkel (`binance` stílus)
- SMA, Bollinger szalagok, RSI, MACD, volumen - egyenként ki/be kapcsolható panelek
- Élő (automatikus) frissítés testreszabható időközzel
- Egérrel követhető kereszt (crosshair) OHLC tooltippel a charton
- Görgővel nagyítás/kicsinyítés (arányos ár-skálával), jobb gombos húzással mozgatás -
  a nézet (zoom/pozíció) megmarad élő frissítésnél/újra-lekérésnél, csak szimbólumváltáskor
  áll vissza teljes nézetre
- Elegáns chart-fejléc: nemzetközi pénznemjel (₿, Ξ, $, € stb.) ha van ismert, a teljes
  pár/időtáv hover-tooltipben; a chart belső címe is "BASE/QUOTE" formátumú
- Kereshető szimbólum-választó ablak (🔍), nagy előnézeti sávval, pénznemjelekkel és
  csillagozható kedvencekkel
- ⭐ Watchlist oldalsáv: az összes kedvenc ára és 24 órás %-os változása egyszerre látszik,
  kb. 15 mp-enként frissülve - kattintással betölthető a chartra
- 📡 Piac-szűrő (Eszközök menü): technikai pontszázalékot (RSI+MACD+trend+Bollinger,
  volumennel súlyozva) számol az összes (vagy quote eszköz szerint szűrt) szimbólumra,
  és a Beállításokban megadott küszöb fölött/alatt 🟢/🔴 jelzést ad - **ez egy technikai
  szűrő, nem befektetési tanács**, a UI is jelzi
- A rendszer aktuális (világos/sötét) témáját veszi fel induláskor
- 🎯 Gyakorlás mód: kattints egy gyertyára a belépéshez, egy másikra a záráshoz -
  a szimulált (Long/Short) ügylet rögzítésre kerül a 📒 Kereskedési naplóban.
  Minden lezárt ügyletet automatikusan összevetünk pár klasszikus alapszabállyal
  (ne kereskedj a trend ellen, ne lépj be túlvett/túladott állapotban, vágd rövidre
  a veszteséget, hagyd futni a nyereséget), a napló-ablak pedig kimutatja a nyerő
  arányt, a profit faktort és a leggyakoribb hibákat - ez segít saját, automata
  szűrő-szabályokat (pl. a Piac-szűrőben) felállítani
- 🔔 Javasolt be-/kilépési jelzések a charton: zöld ▲ / piros ▼ ott, ahol a Piac-szűrővel
  azonos technikai pontszám átlépi a Beállításokban megadott küszöböt (visszatekintő,
  tanulási célú - nem előrejelzés)
- Felugró súgó buborékok (tooltip) minden vezérlőn - Beállításokban ki/bekapcsolható
- Kattintható ⓘ infó gombok az indikátorok mellett (rövid magyar magyarázat)
- Perzisztens beállítások (`%USERPROFILE%\.binance_ta\settings.json`)

## Projekt szerkezet

```
src/binance_ta/
    client.py           Binance REST API kliens (retry/backoff, logging)
    indicators.py       SMA / RSI / MACD / Bollinger számítás (pandas)
    gui.py              Tkinter GUI + candlestick chart (mplfinance)
    symbol_picker.py    Kereshető szimbólum-választó ablak (kedvencekkel)
    currency_symbols.py  Nemzetközi pénznemjelek (₿, Ξ, $, € stb.), ha ismertek
    scoring.py           Folytonos technikai pontszám (-100%..+100%) egy dataframere
    screener.py           Piac-szintű szken korlátozott párhuzamossággal
    screener_window.py     Piac-szűrő ablak (eredménytábla, küszöb szerinti jelzés)
    trade_journal.py     Gyakorló ügyletek (Trade, TradeJournal) - JSON perzisztencia
    trade_rules.py         Klasszikus alapszabályok + ügylet-kiértékelés
    journal_window.py        Kereskedési napló ablak (statisztika, hibalista)
    settings.py         Felhasználói beállítások (JSON perzisztencia)
    tooltip.py          Újrahasznosítható hover-tooltip widget
    indicator_info.py   Indikátor-leírások a Súgó menühöz / info gombokhoz
    win_theme.py         Windows sötét/világos mód érzékelése + sötét címsor
    logging_setup.py     Fájlba forgatott + konzol logging
tests/                  pytest unit tesztek (indikátorok, API kliens, beállítások)
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
- Gyakorló ügyletek: `%USERPROFILE%\.binance_ta\trades.json`
