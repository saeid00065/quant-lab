"""Download HistData.com free 1-minute bars (ASCII M1) and build checked UTC Parquet files.

Usage:
  py -3 -u scripts/get_histdata.py                         XAUUSD + 7 major FX pairs, all available years
  py -3 -u scripts/get_histdata.py --symbols XAUUSD EURUSD
  py -3 -u scripts/get_histdata.py --skip-download         rebuild Parquet + QC from the raw zips only

Steps:
 1. download  data/raw/histdata/{SYMBOL}/HISTDATA_COM_ASCII_{SYMBOL}_M1_{YYYY|YYYYMM}.zip  (never modified;
              existing files are skipped, except the current month which is refreshed); manifest.json per
              symbol records period, bytes, SHA-256 and download time
 2. build     data/processed/histdata/{SYMBOL}_1m.parquet  (time_utc, open, high, low, close)
 3. check     results/data_qc/histdata_{SYMBOL}_qc.json

Source format (HistData docs): "YYYYMMDD HHMMSS;open;high;low;close;volume", time = EST fixed UTC-5 (no DST),
bar time = bar open, prices are one quote stream (bid for FX), volume is always 0. Converted here: time + 5h -> UTC.
Corrections are never silent: exact duplicate rows are dropped and counted; timestamps repeated with different
prices are counted and the first copy is kept; both are reported in the QC file.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "histdata"
PROCESSED = ROOT / "data" / "processed" / "histdata"
QC_DIR = ROOT / "results" / "data_qc"
BASE = "https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes"
DEFAULT = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"]
UA = {"User-Agent": "Mozilla/5.0 (quant-lab research downloader)"}
PAUSE = 2.0  # seconds between requests, to be polite to a free service


def periods(session: requests.Session, sym: str) -> list[str]:
    """Available periods from the symbol page: 'YYYY' for full years, 'YYYY/M' for months of the current year."""
    html = session.get(f"{BASE}/{sym.lower()}", headers=UA, timeout=30).text
    found = set(re.findall(rf"1-minute-bar-quotes/{sym.lower()}/(\d{{4}}(?:/\d{{1,2}})?)\"", html))
    return sorted(found, key=lambda p: (int(p[:4]), int(p[5:] or 0)))


def zip_name(sym: str, period: str) -> str:
    y, _, m = period.partition("/")
    return f"HISTDATA_COM_ASCII_{sym}_M1_{y}{int(m):02d}.zip" if m else f"HISTDATA_COM_ASCII_{sym}_M1_{y}.zip"


def fetch(session: requests.Session, sym: str, period: str) -> bytes:
    page_url = f"{BASE}/{sym.lower()}/{period}"
    for attempt in range(4):
        try:
            html = session.get(page_url, headers=UA, timeout=30).text
            form = {k: v for k, v in re.findall(r'<input type="hidden" name="(\w+)" id="\w+" value="([^"]*)"', html)}
            if "tk" not in form:
                raise RuntimeError("download form not found")
            time.sleep(PAUSE)
            r = session.post("https://www.histdata.com/get.php", data=form, timeout=120,
                             headers=UA | {"Referer": page_url})
            r.raise_for_status()
            if not zipfile.is_zipfile(io.BytesIO(r.content)):
                raise RuntimeError(f"not a zip ({len(r.content)} bytes)")
            return r.content
        except (requests.RequestException, RuntimeError) as e:
            wait = 15 * (attempt + 1)
            print(f"      {sym} {period}: {e}; retry in {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"{sym} {period}: download failed after retries")


def download(sym: str) -> None:
    folder = RAW / sym
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    current_month = f"{date.today().year}/{date.today().month}"
    with requests.Session() as s:
        todo = periods(s, sym)
        print(f"  {sym}: {len(todo)} periods ({todo[0]} .. {todo[-1]})", flush=True)
        for p in todo:
            name = zip_name(sym, p)
            path = folder / name
            if path.exists() and p != current_month:
                continue
            data = fetch(s, sym, p)
            path.write_bytes(data)
            manifest[name] = {"period": p, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                              "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                              "partial": p == current_month}
            manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True))
            print(f"    {name}  {len(data)/1e6:.1f} MB", flush=True)
            time.sleep(PAUSE)


def read_zip(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        csv = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if len(csv) != 1:
            raise RuntimeError(f"{path.name}: expected one CSV, found {csv}")
        df = pd.read_csv(z.open(csv[0]), sep=";", header=None, names=["t", "open", "high", "low", "close", "volume"])
    df["source_file"] = path.name
    return df


def build(sym: str) -> dict:
    files = sorted((RAW / sym).glob("*.zip"))
    if not files:
        raise SystemExit(f"{sym}: no raw files")
    raw = pd.concat([read_zip(f) for f in files], ignore_index=True)
    raw["time_utc"] = pd.to_datetime(raw["t"], format="%Y%m%d %H%M%S") + pd.Timedelta(hours=5)
    raw["time_utc"] = raw["time_utc"].dt.tz_localize("UTC")
    n_raw = len(raw)
    cols = ["open", "high", "low", "close"]
    exact = raw.duplicated(subset=["time_utc", *cols])
    df = raw[~exact].sort_values("time_utc", kind="stable")
    conflict = df.duplicated(subset=["time_utc"], keep="first")
    conflict_times = df.loc[conflict, "time_utc"]
    df = df[~conflict].reset_index(drop=True)

    px = df[cols].to_numpy()
    gap_min = df["time_utc"].diff().dt.total_seconds().div(60)
    ret = np.log(df["close"]).diff().abs()
    qc = {
        "symbol": sym, "source": "histdata.com ASCII M1 (EST fixed UTC-5 -> UTC)", "raw_files": len(files),
        "raw_rows": n_raw, "rows": len(df),
        "dropped_exact_duplicates": int(exact.sum()),
        "conflicting_duplicate_timestamps_kept_first": int(conflict.sum()),
        "conflicting_examples": [str(t) for t in conflict_times.head(5)],
        "first_utc": str(df["time_utc"].iloc[0]), "last_utc": str(df["time_utc"].iloc[-1]),
        "nan_or_inf": int((~np.isfinite(px)).sum()), "non_positive_prices": int((px <= 0).sum()),
        "ohlc_violations": int(((df["low"] > df[["open", "close"]].min(axis=1)) |
                                (df["high"] < df[["open", "close"]].max(axis=1)) | (df["low"] > df["high"])).sum()),
        "non_whole_minutes": int((df["time_utc"].dt.second != 0).sum()),
        "gaps_minutes": {"2-10": int(gap_min.between(2, 10).sum()), "11-58": int(gap_min.between(11, 58).sum()),
                         "59-61 (daily break)": int(gap_min.between(59, 61).sum()),
                         "62-2879": int(gap_min.between(62, 2879).sum()), ">=2880 (weekend/holiday)": int((gap_min >= 2880).sum()),
                         "longest": float(gap_min.max()), "longest_ends_utc": str(df.loc[gap_min.idxmax(), "time_utc"])},
        "one_minute_moves_over_1pct": int((ret > 0.01).sum()),
        "one_minute_moves_over_5pct": [str(t) for t in df.loc[ret > 0.05, "time_utc"].head(20)],
        "rows_per_year": {int(y): int(n) for y, n in df.groupby(df["time_utc"].dt.year).size().items()},
        "raw_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
    }
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df[["time_utc", *cols]].to_parquet(PROCESSED / f"{sym}_1m.parquet", index=False)
    QC_DIR.mkdir(parents=True, exist_ok=True)
    (QC_DIR / f"histdata_{sym}_qc.json").write_text(json.dumps(qc, indent=1))
    return qc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=DEFAULT)
    ap.add_argument("--skip-download", action="store_true")
    args = ap.parse_args()
    syms = [s.upper() for s in args.symbols]
    if not args.skip_download:
        print("[1/2] downloading from histdata.com (resumes; raw files are never modified)", flush=True)
        for s in syms:
            download(s)
    print("[2/2] building UTC Parquet + QC", flush=True)
    for s in syms:
        q = build(s)
        print(f"  {s}: {q['rows']:,} bars {q['first_utc'][:10]} .. {q['last_utc'][:10]} | dup dropped {q['dropped_exact_duplicates']}, "
              f"conflicts {q['conflicting_duplicate_timestamps_kept_first']} | OHLC bad {q['ohlc_violations']} | "
              f">1% 1-min moves {q['one_minute_moves_over_1pct']} | longest gap {q['gaps_minutes']['longest']:.0f} min", flush=True)


if __name__ == "__main__":
    sys.exit(main())
