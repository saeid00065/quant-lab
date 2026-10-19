"""Dukascopy public datafeed: download and decode 1-minute BID/ASK candles.

Feed facts (checked against real files, 2025-01):
- URL: https://datafeed.dukascopy.com/datafeed/{SYMBOL}/{YYYY}/{MM-1:02d}/{DD:02d}/{SIDE}_candles_min_1.bi5
  (month is zero-based).
- One file = one UTC calendar day = 1440 one-minute bars, LZMA compressed.
- Record = 24 bytes, big-endian: time offset seconds (int32), open, close, low, high
  (int32, price * point_scale), volume (float32).
- Timestamp = bar START in UTC.
- Minutes with no ticks are filled with flat bars (O=H=L=C, volume 0) at the last price.
  These are NOT trades; data_quality flags them and nothing here drops them.
- Volume is Dukascopy's own tick-volume proxy, not total market volume (gold is OTC).

Raw files are cached byte-for-byte and never modified.
"""
from __future__ import annotations

import hashlib
import lzma
import struct
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

BASE_URL = "https://datafeed.dukascopy.com/datafeed"
USER_AGENT = "Mozilla/5.0 (quant-lab research downloader)"
RECORD = struct.Struct(">5if")

# Price scale per instrument (prices stored as int * 1/scale).
POINT_SCALE = {"XAUUSD": 1000, "XAGUSD": 1000, "EURUSD": 100000, "GBPUSD": 100000, "USDJPY": 1000}

SIDES = ("BID", "ASK")


@dataclass(frozen=True)
class DayFile:
    symbol: str
    side: str
    day: date

    @property
    def url(self) -> str:
        d = self.day
        return f"{BASE_URL}/{self.symbol}/{d.year}/{d.month - 1:02d}/{d.day:02d}/{self.side}_candles_min_1.bi5"

    def path(self, raw_dir: Path) -> Path:
        return raw_dir / self.symbol / self.side / str(self.day.year) / f"{self.day.isoformat()}.bi5"


def day_range(start: date, end: date) -> list[date]:
    """Inclusive list of calendar days."""
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def decode_candles(payload: bytes, day: date, scale: int) -> pd.DataFrame:
    """Decode one .bi5 candle file into a UTC-indexed frame. Empty payload -> empty frame."""
    cols = ["date", "open", "high", "low", "close", "volume"]
    if not payload:
        return pd.DataFrame(columns=cols)
    raw = lzma.decompress(payload)
    if len(raw) % RECORD.size:
        raise ValueError(f"{day}: payload length {len(raw)} is not a multiple of {RECORD.size}")
    arr = np.frombuffer(raw, dtype=np.dtype([("t", ">i4"), ("o", ">i4"), ("c", ">i4"), ("l", ">i4"), ("h", ">i4"), ("v", ">f4")]))
    day0 = pd.Timestamp(day, tz="UTC")
    return pd.DataFrame(
        {
            "date": day0 + pd.to_timedelta(arr["t"].astype(np.int64), unit="s"),
            "open": arr["o"].astype(np.float64) / scale,
            "high": arr["h"].astype(np.float64) / scale,
            "low": arr["l"].astype(np.float64) / scale,
            "close": arr["c"].astype(np.float64) / scale,
            "volume": arr["v"].astype(np.float64),
        }
    )


def _fetch(url: str, retries: int = 8, pause: float = 0.0) -> bytes:
    """GET one file. 404 -> b"" (no file for that day). 429/5xx -> back off and retry.

    Dukascopy throttles bursts with 503/429, so the backoff starts long.
    """
    import requests

    delay = 5.0
    for attempt in range(retries):
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 120.0)
            continue
        time.sleep(pause)
        if r.status_code == 200:
            return r.content
        if r.status_code == 404:
            return b""
        if r.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
            time.sleep(delay)
            delay = min(delay * 2, 120.0)
            continue
        r.raise_for_status()
    raise RuntimeError(f"giving up on {url}")


def download(
    symbol: str,
    start: date,
    end: date,
    raw_dir: Path,
    *,
    sides: Iterable[str] = SIDES,
    workers: int = 1,
    pause: float = 0.5,
    log=print,
) -> dict:
    """Download missing day files into raw_dir. Existing files are left untouched.

    Returns counts: {"downloaded", "cached", "empty", "failed": [..]}.
    """
    # Day by day, both sides together, so a partial download is still usable.
    jobs = [DayFile(symbol, s, d) for d in day_range(start, end) for s in sides]
    todo = [j for j in jobs if not j.path(raw_dir).exists()]
    stats = {"requested": len(jobs), "cached": len(jobs) - len(todo), "downloaded": 0, "empty": 0, "failed": []}
    log(f"      {len(jobs)} day files: {stats['cached']} already downloaded, {len(todo)} to go", flush=True)

    def work(job: DayFile) -> tuple[DayFile, int]:
        payload = _fetch(job.url, pause=pause)
        p = job.path(raw_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".part")
        tmp.write_bytes(payload)
        tmp.replace(p)
        return job, len(payload)

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, j) for j in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                job, size = fut.result()
                stats["downloaded"] += 1
                stats["empty"] += size == 0
            except Exception as exc:  # recorded, not swallowed
                stats["failed"].append(str(exc))
            if i % 20 == 0 or i == len(todo):
                eta = (time.monotonic() - t0) / i * (len(todo) - i) / 60
                log(f"      {i / len(todo):6.1%}  {i}/{len(todo)} files  about {eta:.0f} min left"
                    f"  failed {len(stats['failed'])}", flush=True)
    return stats


def load_side(symbol: str, side: str, start: date, end: date, raw_dir: Path) -> tuple[pd.DataFrame, list[dict]]:
    """Decode cached day files for one side. Returns (bars, per-file manifest)."""
    scale = POINT_SCALE[symbol]
    frames, manifest = [], []
    for d in day_range(start, end):
        p = DayFile(symbol, side, d).path(raw_dir)
        if not p.exists():
            manifest.append({"day": d.isoformat(), "side": side, "status": "missing"})
            continue
        payload = p.read_bytes()
        df = decode_candles(payload, d, scale)
        manifest.append({
            "day": d.isoformat(), "side": side, "status": "ok" if len(df) else "empty",
            "bytes": len(payload), "rows": len(df), "sha256": hashlib.sha256(payload).hexdigest(),
        })
        if len(df):
            frames.append(df)
    bars = pd.concat(frames, ignore_index=True) if frames else decode_candles(b"", start, scale)
    return bars, manifest


def combine_bid_ask(bid: pd.DataFrame, ask: pd.DataFrame) -> pd.DataFrame:
    """Outer-join BID and ASK bars on timestamp; adds mid OHLC and close spread.

    Mid OHLC is the average of bid and ask per field (an approximation: the true mid
    high/low can differ because bid and ask extremes need not coincide).
    """
    b = bid.set_index("date").add_prefix("bid_")
    a = ask.set_index("date").add_prefix("ask_")
    out = b.join(a, how="outer").sort_index()
    for f in ("open", "high", "low", "close"):
        out[f"mid_{f}"] = (out[f"bid_{f}"] + out[f"ask_{f}"]) / 2
    out["spread_close"] = out["ask_close"] - out["bid_close"]
    # A minute is "real" when either side recorded ticks.
    out["has_ticks"] = (out["bid_volume"].fillna(0) > 0) | (out["ask_volume"].fillna(0) > 0)
    return out.reset_index()
