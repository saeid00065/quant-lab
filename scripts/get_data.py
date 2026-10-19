"""One command for the data section: download BID + ASK, combine, sort, check, export.

Usage:
  py -3 -u scripts/get_data.py                              XAUUSD, 2019-01-01 .. yesterday
  py -3 -u scripts/get_data.py --start 2025-01-01 --end 2026-10-19 --csv
  py -3 -u scripts/get_data.py --skip-download              rebuild from files already downloaded
Or double-click "Download Data.cmd" in the project folder.

Steps:
 1. download  data/raw/dukascopy/{SYMBOL}/{BID,ASK}/YYYY/YYYY-MM-DD.bi5  (raw, never modified;
              already-downloaded days are skipped, so a stopped run resumes)
 2. combine   BID + ASK joined on the UTC minute, sorted by time, mid and spread added
 3. check     data quality report (nothing is dropped or filled silently)
 4. export    data/processed/{SYMBOL}_1m.parquet and _{5m,15m,1h,4h,1D}.parquet
              data/processed/csv/{SYMBOL}_1m_YYYY.csv   (with --csv; minutes with ticks only)
              results/data_qc/{SYMBOL}_qc.json and dist/data_report.js (dashboard Data page)
"""
from __future__ import annotations

import argparse
import os
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.data_loader import resample_bars  # noqa: E402
from src.data_quality import daily_closes, run_all  # noqa: E402
from src.modules.dukascopy import DukascopyBlocked, combine_bid_ask, download, load_side  # noqa: E402

# Only instruments whose price scale and trading calendar have been checked.
INSTRUMENTS = {
    "XAUUSD": "Spot gold vs USD (OTC, no exchange). Price per troy ounce.",
    "XAGUSD": "Spot silver vs USD (OTC, no exchange). Price per troy ounce. Calendar assumed same as gold.",
}
RAW = ROOT / "data/raw/dukascopy"
PROC = ROOT / "data/processed"
QC = ROOT / "results/data_qc"
TIMEFRAMES = {"5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h", "1D": "1D"}
CSV_COLS = ["date"] + [f"{s}_{f}" for s in ("bid", "ask") for f in ("open", "high", "low", "close")] + [
    "bid_volume", "ask_volume", "spread_close"]

# Proposed chronological split. Recorded BEFORE any strategy/parameter work.
# Status stays "proposed" until the user confirms it.
SPLIT = [
    {"name": "research", "start": "2019-01-01", "end": "2023-12-31"},
    {"name": "validation", "start": "2024-01-01", "end": "2024-12-31"},
    {"name": "final_test", "start": "2025-01-01", "end": None},
]


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def build(symbol: str, start: date, end: date, *, csv: bool = False, raw: Path = RAW, proc: Path = PROC,
          qc_dir: Path = QC, dashboard: Path | None = ROOT / "dist/data_report.js") -> dict:
    print(f"[2/4] combining BID + ASK for {start} .. {end}", flush=True)
    bid, man_b = load_side(symbol, "BID", start, end, raw)
    ask, man_a = load_side(symbol, "ASK", start, end, raw)
    manifest = man_b + man_a
    df = combine_bid_ask(bid, ask)
    if df.empty:
        raise SystemExit("No bars found. Download first (run without --skip-download).")

    files_hash = hashlib.sha256("".join(m.get("sha256", m["status"]) for m in manifest).encode()).hexdigest()
    man = pd.DataFrame(manifest)
    man["weekday"] = pd.to_datetime(man["day"]).dt.weekday
    file_summary = {}
    for side in ("BID", "ASK"):
        m = man[man["side"] == side]
        file_summary[side] = {
            "files": int(len(m)),
            "ok": int((m["status"] == "ok").sum()),
            "empty": int((m["status"] == "empty").sum()),
            "missing": int((m["status"] == "missing").sum()),
            "missing_or_empty_weekdays": m.loc[(m["status"] != "ok") & (m["weekday"] < 5), "day"].tolist(),
        }

    proc.mkdir(parents=True, exist_ok=True)
    qc_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(proc / f"{symbol}_1m.parquet", index=False)
    tf_rows = {"1m": int(len(df)), "1m_with_ticks": int(df["has_ticks"].sum())}
    for name, rule in TIMEFRAMES.items():
        r = resample_bars(df, rule)
        r.to_parquet(proc / f"{symbol}_{name}.parquet", index=False)
        tf_rows[name] = int(len(r))

    if csv:
        out = proc / "csv"
        out.mkdir(exist_ok=True)
        t = df.loc[df["has_ticks"], CSV_COLS]
        for yr, g in t.groupby(t["date"].dt.year):
            g.to_csv(out / f"{symbol}_1m_{yr}.csv", index=False, date_format="%Y-%m-%d %H:%M:%S")
        print(f"      CSV written to {out} ({len(t):,} rows with ticks, UTC bar start)", flush=True)

    print("[3/4] running quality checks", flush=True)
    qc = run_all(df)
    filler = qc["filler_bars"]

    corrections = [
        {"step": "decode", "rows": int(len(bid) + len(ask)), "effect": "bi5 integers / point scale -> USD prices; offsets -> UTC bar-start timestamps"},
        {"step": "join bid+ask", "rows": int(len(df)), "effect": "outer join on timestamp, sorted by time; rows with only one side are counted in values.side_missing, not dropped"},
        {"step": "mid prices", "rows": int(len(df)), "effect": "mid = (bid+ask)/2 per OHLC field (mid high/low approximate)"},
        {"step": "flag filler bars", "rows": filler, "effect": "has_ticks = False for flat zero-volume minutes Dukascopy writes when there were no ticks. Kept in the 1m file; excluded from resampled bars, CSV and statistics"},
        {"step": "drop / fill / adjust", "rows": 0, "effect": "none. No split/dividend adjustment applies to spot metals"},
    ]

    split = []
    for s in SPLIT:
        lo = pd.Timestamp(s["start"], tz="UTC")
        hi = pd.Timestamp(s["end"], tz="UTC") + pd.Timedelta(days=1) if s["end"] else df["date"].max() + pd.Timedelta(minutes=1)
        m = (df["date"] >= lo) & (df["date"] < hi) & df["has_ticks"]
        split.append(s | {"tick_minutes": int(m.sum())})

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "spec": {
            "symbol": symbol,
            "instrument": INSTRUMENTS[symbol],
            "source": "Dukascopy Bank public datafeed (datafeed.dukascopy.com), 1-minute candles",
            "sides": "BID and ASK downloaded separately; mid derived",
            "price_type": "bid / ask quotes (not trades)",
            "timestamp": "UTC, bar START (bar covers [t, t+1min)); finished bar usable at t+1min",
            "timezone": "UTC; sessions and calendar evaluated in local time with DST",
            "volume": "Dukascopy tick-volume proxy (their own liquidity), NOT total market volume",
            "range_requested": [start.isoformat(), end.isoformat()],
            "corporate_actions": "not applicable (spot commodity)",
            "survivorship": "not applicable (single continuous instrument)",
            "venue_note": "Dukascopy quotes differ from your broker's feed by a few cents to dollars; spreads especially differ. Re-validate on the execution broker before live use.",
        },
        "reproduce": {
            "dataset_sha256": files_hash,
            "commands": [
                f"py -3 -u scripts/get_data.py --symbol {symbol} --start {start} --end {end}",
                "py -3 -m pytest tests -q",
            ],
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "git_commit": git("rev-parse", "--short", "HEAD"),
            "git_dirty_files": git("status", "--porcelain").splitlines(),
            "outputs": [p.name for p in sorted(proc.glob(f"{symbol}_*.parquet"))],
        },
        "files": file_summary,
        "timeframes": tf_rows,
        "corrections": corrections,
        "split": {"status": "proposed - needs user confirmation before any parameter selection", "segments": split},
        "qc": qc,
    }

    print("[4/4] writing report", flush=True)
    (qc_dir / f"{symbol}_qc.json").write_text(json.dumps(report | {"manifest": manifest}, indent=1, default=str))
    if dashboard is not None:
        dash = report | {"daily_close": daily_closes(df)}
        dashboard.write_text(
            "// Generated by scripts/get_data.py. Do not edit by hand.\nwindow.DATA_REPORT = "
            + json.dumps(dash, separators=(",", ":"), default=str) + ";\n",
            encoding="utf-8",
        )
    print(f"      files: BID {file_summary['BID']['ok']}/{file_summary['BID']['files']}, "
          f"ASK {file_summary['ASK']['ok']}/{file_summary['ASK']['files']} with data", flush=True)
    print(f"      bars: {tf_rows['1m']:,} minutes, {tf_rows['1m_with_ticks']:,} with ticks", flush=True)
    print(f"      duplicates {qc['integrity']['duplicate_timestamps']}, sorted {qc['integrity']['monotonic_increasing']}, "
          f"median spread ${qc['spread']['all'].get('median', float('nan')):.3f}", flush=True)
    print("Done. Open the dashboard Data page for the full report.", flush=True)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbol", default="XAUUSD", choices=sorted(INSTRUMENTS))
    ap.add_argument("--start", default="2019-01-01", help="first UTC day, YYYY-MM-DD")
    ap.add_argument("--end", default=(date.today() - timedelta(days=1)).isoformat(), help="last UTC day, inclusive")
    ap.add_argument("--skip-download", action="store_true", help="only rebuild from files already downloaded")
    ap.add_argument("--csv", action="store_true", help="also write yearly CSV files")
    ap.add_argument("--rounds", type=int, default=6, help="download rounds; failed days are retried after a wait")
    ap.add_argument("--wait", type=int, default=300, help="seconds to wait between rounds when Dukascopy throttles")
    ap.add_argument("--proxy", help="proxy for the datafeed, e.g. socks5h://127.0.0.1:10808 (default: proxy.txt / QUANTLAB_PROXY)")
    a = ap.parse_args()
    if a.proxy:
        os.environ["QUANTLAB_PROXY"] = a.proxy
    start, end = date.fromisoformat(a.start), date.fromisoformat(a.end)

    if not a.skip_download:
        print(f"[1/4] downloading {a.symbol} BID + ASK {start} .. {end}", flush=True)
        print("      You can close this window any time; running it again continues where it stopped.", flush=True)
        for rnd in range(1, a.rounds + 1):
            try:
                stats = download(a.symbol, start, end, RAW, log=print)
            except DukascopyBlocked as exc:
                print(f"      Dukascopy is blocking this connection ({str(exc).split(' after ')[0]}).", flush=True)
                stats = {"downloaded": 0, "cached": 0, "failed": ["blocked"]}
            print(f"      round {rnd}: {stats['downloaded']} downloaded, {stats['cached']} already had, "
                  f"{len(stats['failed'])} failed", flush=True)
            if not stats["failed"]:
                break
            if rnd < a.rounds:
                print(f"      Dukascopy is throttling. Waiting {a.wait // 60} min, then retrying only the failed days...", flush=True)
                time.sleep(a.wait)
        else:
            print(f"      {len(stats['failed'])} days still missing. Building with what we have; run again later to fill them.", flush=True)
    build(a.symbol, start, end, csv=a.csv)


if __name__ == "__main__":
    main()
