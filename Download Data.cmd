@echo off
setlocal

rem One click: download XAUUSD BID + ASK 1-minute bars (2019 -> yesterday), combine, sort,
rem check quality, save Parquet + yearly CSV, then open the Data page.
rem Closing the window is safe; double-click again to continue where it stopped.
rem Advanced: Download Data.cmd --start 2025-01-01 --end 2026-10-19 --symbol XAGUSD
cd /d "%~dp0"
title Quant Lab - downloading data

echo ============================================================
echo  Quant Lab - XAUUSD data download
echo  Bid + Ask, 1-minute, 2019 to yesterday, from Dukascopy.
echo  First run takes 1-2 hours. Later runs only fetch new days.
echo ============================================================
echo.

py -3 -u scripts\get_data.py --csv %*

echo.
if errorlevel 1 (
    echo Something went wrong. Read the message above, then double-click this file again.
) else (
    echo Finished. Files are in data\processed  ^(CSV in data\processed\csv^).
    start "" "dist\data.html"
)
echo Press any key to close.
pause >nul
