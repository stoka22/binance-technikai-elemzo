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
  szűrő, nem befektetési tanács**, a UI is jelzi. A rendkívül alacsony likviditású
  (jellemzően nulla volumenű, lapos gyertyás) párokat automatikusan kihagyja, mert
  ezekre sem a pontszám, sem a chart nem adna megbízható/áttekinthető képet
- A rendszer aktuális (világos/sötét) témáját veszi fel induláskor
- 🎯 Gyakorlás mód: kattints egy gyertyára a belépéshez, egy másikra a záráshoz -
  a szimulált (Long/Short) ügylet rögzítésre kerül a 📒 Kereskedési naplóban.
  Minden lezárt ügyletet automatikusan összevetünk a konfigurált szabályokkal, a
  napló-ablak pedig kimutatja a nyerő arányt, a profit faktort és a leggyakoribb
  jelzéseket - ez segít saját, automata szűrő-szabályokat (pl. a Piac-szűrőben)
  felállítani
- ⚙ Szabályok kezelése (Eszközök menü): 3 súlyossági szint (ℹ️ Info / ⚠️ Figyelmeztetés /
  ❌ Szabálysértés), a 4 beépített szabály (trend, RSI-szélsőség, nincs stop-loss, korai
  zárás) ki/bekapcsolható és paraméterezhető, saját szabály pedig biztonságos
  építőelemekből (indikátor + összehasonlítás + érték + Long/Short/mindkettő)
  hozható létre - nincs szabad kódfuttatás
- 🔔 Javasolt be-/kilépési jelzések a charton: zöld ▲ / piros ▼ ott, ahol a Piac-szűrővel
  azonos technikai pontszám átlépi a Beállításokban megadott küszöböt (visszatekintő,
  tanulási célú - nem előrejelzés)
- 🕯 Gyertya-alakzat felismerés: 16 klasszikus alakzat (Doji, Kalapács, Elnyelő minta,
  Hajnal-/Alkonycsillag stb.) tiszta geometriai szabályokkal, ahogy a TA-Lib is teszi -
  NEM gépi tanulással. Színes pont jelöli a chart-on (zöld/piros/szürke), vidd rá az
  egeret a pontos névért; egy volatilitás-szűrő kiszűri a jelentéktelen, csendes
  szakaszokban is "technikailag illő" mintákat, hogy ne legyen zajos a jelölés
- 📐 Chart-alakzat (pivot-alapú) felismerés: dupla csúcs/alj és fej-váll/fordított
  fej-váll alakzatok, a helyi csúcs-/mélypontok (pivot pontok) geometriai
  vizsgálatával, ahogy pl. az Autochartist is teszi. A charton vonal köti össze az
  alakzat pontjait, rövid felirattal
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
    rule_config.py         Konfigurálható szabályok (RuleConfig, RuleConfigStore)
    trade_rules.py           Szabály-kiértékelő (kind szerint elágazva)
    rules_window.py            Szabályok kezelése ablak + szabály-szerkesztő
    journal_window.py            Kereskedési napló ablak (statisztika, hibalista)
    settings.py         Felhasználói beállítások (JSON perzisztencia)
    tooltip.py          Újrahasznosítható hover-tooltip widget
    indicator_info.py   Indikátor-leírások a Súgó menühöz / info gombokhoz
    candlestick_patterns.py Gyertya-alakzat felismerés (geometriai szabályokkal)
    chart_patterns.py         Pivot-alapú chart-alakzat felismerés (dupla csúcs/alj, fej-váll)
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
- Gyakorlás szabályai: `%USERPROFILE%\.binance_ta\rules.json`
- Gyakorló ügyletek: `%USERPROFILE%\.binance_ta\trades.json`
