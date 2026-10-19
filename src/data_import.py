"""Import candle CSVs exported from the Dukascopy website (one file for BID, one for ASK) and
combine them into one time-sorted bid/ask frame.

Accepted layout (Dukascopy "Historical data export" and similar):
    Gmt time,Open,High,Low,Close,Volume
    01.01.2025 00:00:00.000,2623.655,2623.905,2622.448,2622.828,0.0427
The time column may be named "Gmt time", "Time (UTC)", "Local time", "Date", "Timestamp"...
Times may carry an offset ("01.01.2025 03:30:00.000 GMT+0330"); they are converted to UTC.
Times without any zone information are taken as UTC and this assumption is reported.
Nothing is filled. Exact duplicate rows are removed and counted; conflicting duplicates stop
the import.
"""
from __future__ import annotations

import io
import re

import pandas as pd

from src.modules.dukascopy import combine_bid_ask

OFFSET = re.compile(r"\s*(?:GMT|UTC)\s*([+-])(\d{2}):?(\d{2})\s*$", re.I)


def _find(cols: dict[str, str], *names: str) -> str | None:
    for n in names:
        for low, orig in cols.items():
            if low == n or low.startswith(n + " ") or low.startswith(n + "("):
                return orig
    return None


def _parse_time(s: pd.Series, header: str) -> tuple[pd.Series, str]:
    s = s.astype(str).str.strip()
    m = s.str.extract(OFFSET)
    has_offset = m[0].notna()
    base = s.str.replace(OFFSET, "", regex=True)
    dayfirst = bool(base.iloc[0][:5].count(".") == 2 or re.match(r"^\d{2}\.\d{2}\.\d{4}", base.iloc[0]))
    t = pd.to_datetime(base, dayfirst=dayfirst, errors="coerce", format="mixed")
    if t.isna().any():
        bad = s[t.isna()].iloc[0]
        raise ValueError(f"could not read time value {bad!r} in column {header!r}")
    if has_offset.any():
        if not has_offset.all():
            raise ValueError("some times have a GMT offset and some do not")
        minutes = (m[1].astype(int) * 60 + m[2].astype(int)) * m[0].map({"+": 1, "-": -1})
        t = t - pd.to_timedelta(minutes, unit="min")
        note = "converted from GMT offset in the time column to UTC"
    elif "gmt" in header.lower() or "utc" in header.lower():
        note = f"column {header!r} is UTC"
    else:
        note = f"no time zone in column {header!r}: ASSUMED UTC - check your export setting"
    return t.dt.tz_localize("UTC"), note


def parse_candles_csv(content: bytes, name: str = "") -> tuple[pd.DataFrame, dict]:
    """One exported CSV -> frame [date, open, high, low, close, volume] (UTC bar start)."""
    text = content.decode("utf-8-sig", errors="replace")
    sep = ";" if text.split("\n", 1)[0].count(";") > text.split("\n", 1)[0].count(",") else ","
    raw = pd.read_csv(io.StringIO(text), sep=sep)
    cols = {str(c).strip().lower(): c for c in raw.columns}
    tcol = _find(cols, "gmt time", "time (utc)", "local time", "time", "date", "datetime", "timestamp")
    o, h, l, c = (_find(cols, k) for k in ("open", "high", "low", "close"))
    v = _find(cols, "volume", "vol")
    if not (tcol and o and h and l and c):
        raise ValueError(f"{name}: need time, open, high, low, close columns; found {list(raw.columns)}")
    t, note = _parse_time(raw[tcol], str(tcol))
    df = pd.DataFrame({
        "date": t,
        "open": pd.to_numeric(raw[o], errors="coerce"), "high": pd.to_numeric(raw[h], errors="coerce"),
        "low": pd.to_numeric(raw[l], errors="coerce"), "close": pd.to_numeric(raw[c], errors="coerce"),
        "volume": pd.to_numeric(raw[v], errors="coerce") if v else float("nan"),
    })
    side_hint = "BID" if re.search(r"bid", name, re.I) else "ASK" if re.search(r"ask", name, re.I) else None
    return df, {"file": name, "rows": int(len(df)), "time_note": note, "side_in_name": side_hint,
                "bad_numbers": int(df[["open", "high", "low", "close"]].isna().any(axis=1).sum())}


def _stack(frames: list[pd.DataFrame], side: str) -> tuple[pd.DataFrame, dict]:
    df = pd.concat(frames, ignore_index=True).sort_values("date", kind="stable")
    dup_mask = df["date"].duplicated(keep=False)
    exact = df.duplicated(keep="first")
    conflicting = df[dup_mask & ~df.duplicated(keep=False)]
    if len(conflicting):
        raise ValueError(f"{side}: {conflicting['date'].nunique()} timestamps appear twice with different prices "
                         f"(first {conflicting['date'].iloc[0]}). Are two different exports mixed?")
    out = df[~exact].reset_index(drop=True)
    step = out["date"].diff().dropna()
    tf = step.mode().iloc[0] if len(step) else pd.Timedelta(0)
    return out, {"rows": int(len(out)), "exact_duplicates_removed": int(exact.sum()), "bar_size": str(tf)}


def combine_imports(bid_files: list[tuple[str, bytes]], ask_files: list[tuple[str, bytes]]) -> tuple[pd.DataFrame, dict]:
    """Parse and combine uploaded BID and ASK exports. Returns (combined frame, report)."""
    if not bid_files or not ask_files:
        raise ValueError("add at least one BID file and one ASK file")
    report: dict = {"files": [], "warnings": []}
    sides = {}
    for side, files in (("BID", bid_files), ("ASK", ask_files)):
        frames = []
        for name, content in files:
            df, info = parse_candles_csv(content, name)
            info["side"] = side
            if info["side_in_name"] and info["side_in_name"] != side:
                report["warnings"].append(f"{name} is in the {side} box but its name says {info['side_in_name']}")
            if "ASSUMED" in info["time_note"]:
                report["warnings"].append(f"{name}: {info['time_note']}")
            if info["bad_numbers"]:
                report["warnings"].append(f"{name}: {info['bad_numbers']} rows with unreadable prices (kept as empty)")
            report["files"].append(info)
            frames.append(df)
        sides[side], report[side] = _stack(frames, side)
    if report["BID"]["bar_size"] != report["ASK"]["bar_size"]:
        raise ValueError(f"BID bars are {report['BID']['bar_size']} but ASK bars are {report['ASK']['bar_size']}")
    combined = combine_bid_ask(sides["BID"], sides["ASK"])
    if sides["BID"]["volume"].isna().all() and sides["ASK"]["volume"].isna().all():
        combined["has_ticks"] = True  # no volume column: cannot tell filler bars apart
        report["warnings"].append("no volume column: flat no-tick bars cannot be detected and are kept")
    report["bar_size"] = report["BID"]["bar_size"]
    report["rows_one_side_only"] = int((combined["bid_close"].isna() | combined["ask_close"].isna()).sum())
    if report["rows_one_side_only"]:
        report["warnings"].append(f"{report['rows_one_side_only']} bars exist on one side only (check the date ranges match)")
    crossed = int((combined["ask_close"] < combined["bid_close"]).sum())
    if crossed:
        report["warnings"].append(f"{crossed} bars have ask below bid: are the BID and ASK files swapped?")
    return combined, report
