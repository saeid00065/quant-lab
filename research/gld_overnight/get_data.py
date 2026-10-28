"""Download raw GLD daily bars from Yahoo Finance once, store them unchanged, record SHA-256, run QC.

Usage: py -3 research/gld_overnight/get_data.py           (downloads only if the raw file is missing)
Raw file: data/raw/yahoo/GLD_1d_2005-01-03_2026-10-28.csv (never edited; analysis reads it as-is)
QC report: research/gld_overnight/out/qc.json
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "yahoo" / "GLD_1d_2005-01-03_2026-10-28.csv"
OUT = Path(__file__).resolve().parent / "out"
START, END_INCLUSIVE = "2005-01-03", "2026-10-28"


def download() -> None:
    import yfinance as yf
    df = yf.download("GLD", start=START, end="2026-10-29", interval="1d", auto_adjust=False,
                     actions=True, progress=False, multi_level_index=False)
    if df.empty:
        raise SystemExit("Yahoo returned no data")
    RAW.parent.mkdir(parents=True, exist_ok=True)
    df.reset_index().to_csv(RAW, index=False, float_format="%.10g")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_raw() -> pd.DataFrame:
    df = pd.read_csv(RAW, parse_dates=["Date"])
    return df.rename(columns=str.lower)


def qc(df: pd.DataFrame) -> dict:
    """Report problems; never fix them silently."""
    px = df[["open", "high", "low", "close"]]
    nyse_gaps = df["date"].diff().dt.days
    night = df["open"] / df["close"].shift(1) - 1
    day = df["close"] / df["open"] - 1
    extreme = df.assign(night=night, day=day).loc[(night.abs() > 0.05) | (day.abs() > 0.05), ["date", "night", "day"]]
    report = {
        "file": str(RAW.relative_to(ROOT)), "sha256": sha256(RAW), "rows": int(len(df)),
        "first": str(df["date"].iloc[0].date()), "last": str(df["date"].iloc[-1].date()),
        "dates_sorted_unique": bool(df["date"].is_monotonic_increasing and df["date"].is_unique),
        "nan_or_inf_prices": int((~np.isfinite(px.to_numpy())).sum()),
        "ohlc_violations": int(((df["low"] > df[["open", "close"]].min(axis=1)) |
                                (df["high"] < df[["open", "close"]].max(axis=1)) | (df["low"] > df["high"])).sum()),
        "zero_volume_days": int((df["volume"] <= 0).sum()) if "volume" in df else None,
        "splits_or_dividends": int(((df.get("stock splits", 0) != 0) | (df.get("dividends", 0) != 0)).sum()),
        "gaps_over_4_calendar_days": [str(d.date()) for d in df.loc[nyse_gaps > 4, "date"]],
        "sessions_per_year": {int(y): int(n) for y, n in df.groupby(df["date"].dt.year).size().items()},
        "extreme_moves_over_5pct": [{"date": str(r.date.date()), "night": round(r.night, 5), "day": round(r.day, 5)}
                                    for r in extreme.itertuples()],
        "open_equals_close_days": int((df["open"] == df["close"]).sum()),
        "open_equals_prev_close_days": int((df["open"] == df["close"].shift(1)).sum()),
    }
    return report


if __name__ == "__main__":
    if not RAW.exists():
        download()
        print("downloaded", RAW)
    df = load_raw()
    df = df[(df["date"] >= START) & (df["date"] <= END_INCLUSIVE)]
    report = qc(df)
    OUT.mkdir(exist_ok=True)
    (OUT / "qc.json").write_text(json.dumps(report, indent=1))
    json.dump({k: v for k, v in report.items() if k != "sessions_per_year"}, sys.stdout, indent=1)
    print("\nsessions per year:", report["sessions_per_year"])
