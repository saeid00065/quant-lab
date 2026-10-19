"""Export Dukascopy bars for any symbol, date range and timeframe as ONE file with bid and ask together.

Used by the dashboard download form (scripts/dashboard_server.py). Raw day files are cached in
data/raw/dukascopy and reused; exports go to data/exports.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from src.data_loader import resample_bars
from src.modules.dukascopy import INSTRUMENT_INFO, combine_bid_ask, load_side

TIMEFRAMES = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "1D": "1D"}
PRICES = ("bid_ask", "bid", "ask", "mid")
FIELDS = ("open", "high", "low", "close")


def export_columns(price: str) -> list[str]:
    if price == "bid_ask":
        cols = [f"{s}_{f}" for s in ("bid", "ask") for f in FIELDS] + ["spread_close", "bid_volume", "ask_volume"]
    else:
        cols = [f"{price}_{f}" for f in FIELDS] + ["bid_volume"]
    return ["date"] + cols


def shape(df: pd.DataFrame, timeframe: str, price: str) -> pd.DataFrame:
    """Combined 1-minute bid/ask frame -> chosen timeframe and price columns, sorted by time."""
    if timeframe == "1m":
        out = df[df["has_ticks"]].copy()
    else:
        out = resample_bars(df, TIMEFRAMES[timeframe])
        if "spread_close" in export_columns(price):
            out["spread_close"] = out["ask_close"] - out["bid_close"]
    cols = export_columns(price)
    for c in cols:
        if c not in out:
            out[c] = float("nan")
    return out[cols].sort_values("date").reset_index(drop=True)


def build_export(symbol: str, start: date, end: date, timeframe: str, price: str, raw_dir: Path) -> tuple[pd.DataFrame, dict]:
    """Combine cached BID+ASK files, keep minutes with ticks, resample, select columns.

    `date` is the UTC bar START. Returns (frame, summary). Nothing is filled: minutes without
    ticks are left out, and resampled buckets without ticks produce no row.
    """
    if symbol not in INSTRUMENT_INFO:
        raise ValueError(f"unknown symbol {symbol}")
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"unknown timeframe {timeframe}")
    if price not in PRICES:
        raise ValueError(f"unknown price {price}")

    bid, man_b = load_side(symbol, "BID", start, end, raw_dir)
    ask, man_a = load_side(symbol, "ASK", start, end, raw_dir)
    if bid.empty and ask.empty:
        raise ValueError("no data downloaded for this range")
    df = combine_bid_ask(bid, ask)
    out = shape(df, timeframe, price)

    missing = [m["day"] + " " + m["side"] for m in man_b + man_a if m["status"] == "missing"]
    summary = {
        "rows": int(len(out)),
        "first": out["date"].iloc[0].isoformat() if len(out) else None,
        "last": out["date"].iloc[-1].isoformat() if len(out) else None,
        "minutes_with_ticks": int(df["has_ticks"].sum()),
        "filler_minutes_excluded": int((~df["has_ticks"]).sum()),
        "rows_one_side_only": int((df["bid_close"].isna() | df["ask_close"].isna()).sum()),
        "missing_day_files": missing,
        "duplicates": int(out["date"].duplicated().sum()),
    }
    return out, summary


def write_export(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Prices have at most 5 decimals at source; rounding to 6 only removes float noise from mid/spread.
    num = df.select_dtypes("number").columns
    df.assign(**{c: df[c].round(6) for c in num}).to_csv(path, index=False, date_format="%Y-%m-%d %H:%M:%S")
    return path
