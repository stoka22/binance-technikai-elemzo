# Önálló .exe csomagolás PyInstaller-rel.
# Használat: powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

& ".venv\Scripts\pyinstaller.exe" `
    --noconsole `
    --onefile `
    --name BinanceTA `
    --paths src `
    src\binance_ta\gui.py

Write-Output "Kész: dist\BinanceTA.exe"
