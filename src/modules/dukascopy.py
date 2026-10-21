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
import os
import struct
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

BASE_URL = "https://datafeed.dukascopy.com/datafeed"
USER_AGENT = "Mozilla/5.0 (quant-lab research downloader)"
# Optional proxy for networks that block the datafeed host. First non-empty line of
# proxy.txt in the project root, or the QUANTLAB_PROXY env var (env wins), e.g.
# socks5h://127.0.0.1:10808 or http://127.0.0.1:10809. Without one, requests uses the
# usual HTTPS_PROXY env var / Windows system proxy.
PROXY_FILE = Path(__file__).resolve().parents[2] / "proxy.txt"


def proxy_url() -> str | None:
    url = os.environ.get("QUANTLAB_PROXY", "").strip()
    if not url and PROXY_FILE.exists():
        lines = [ln.strip() for ln in PROXY_FILE.read_text(encoding="utf-8").splitlines()]
        url = next((ln for ln in lines if ln and not ln.startswith("#")), "")
    return url or None
RECORD = struct.Struct(">5if")

# Instruments offered for download: (label, price scale, plausible price range).
# Prices are stored as int / scale. The range is a guard: if decoded prices fall outside it,
# the scale is wrong and decoding stops instead of returning silently wrong prices.
# XAUUSD scale verified against real files (2025-01: ~2623). Others follow Dukascopy's
# point size and are protected by the range guard.
INSTRUMENT_INFO = {
    "XAUUSD": ("Gold spot", 1000, (200, 20000)),
    "XAGUSD": ("Silver spot", 1000, (3, 500)),
    "EURUSD": ("EUR/USD", 100000, (0.5, 2.5)),
    "GBPUSD": ("GBP/USD", 100000, (0.7, 3)),
    "AUDUSD": ("AUD/USD", 100000, (0.3, 1.5)),
    "NZDUSD": ("NZD/USD", 100000, (0.3, 1.5)),
    "USDCAD": ("USD/CAD", 100000, (0.8, 2)),
    "USDCHF": ("USD/CHF", 100000, (0.5, 2)),
    "USDJPY": ("USD/JPY", 1000, (50, 300)),
    "EURJPY": ("EUR/JPY", 1000, (50, 300)),
    "GBPJPY": ("GBP/JPY", 1000, (80, 350)),
    "USATECHIDXUSD": ("Nasdaq 100 CFD", 1000, (1000, 100000)),
    "USA500IDXUSD": ("S&P 500 CFD", 1000, (500, 30000)),
    "USA30IDXUSD": ("Dow Jones 30 CFD", 1000, (5000, 150000)),
}
POINT_SCALE = {k: v[1] for k, v in INSTRUMENT_INFO.items()}


def check_price_scale(symbol: str, df: pd.DataFrame) -> None:
    lo, hi = INSTRUMENT_INFO[symbol][2]
    if len(df) and not (lo <= df["close"].median() <= hi):
        raise ValueError(f"{symbol}: decoded median price {df['close'].median():.5f} is outside {lo}..{hi}; price scale is wrong")

SIDES = ("BID", "ASK")

# A 404 for one of the last RECENT_DAYS UTC days may only mean "not published yet", so it is
# not cached as an empty day (that would hide the day for good); it is retried next run.
RECENT_DAYS = 3


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def last_complete_day() -> date:
    """Latest UTC calendar day that has ended. Day files are UTC days, so local dates are wrong here."""
    return utc_today() - timedelta(days=1)


def is_recent(day: date) -> bool:
    return day > utc_today() - timedelta(days=RECENT_DAYS)


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


class DukascopyBlocked(RuntimeError):
    """Dukascopy refuses every request from this connection (HTTP 503/429 or no answer)."""


class Stopped(RuntimeError):
    """The caller asked to stop."""


def _sleep(seconds: float, should_stop) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if should_stop and should_stop():
            raise Stopped()
        time.sleep(min(1.0, end - time.monotonic()))


def _fetch(url: str, retries: int = 4, pause: float = 0.0, on_wait=None, should_stop=None) -> bytes:
    """GET one file. 404 -> b"" (no file for that day). 429/5xx/no answer -> back off and retry.

    `on_wait(reason, seconds)` is told about every wait so a UI can show it; `should_stop()`
    is checked every second, so cancelling never waits for a long backoff.
    """
    import requests

    proxy = proxy_url()
    proxies = {"http": proxy, "https": proxy} if proxy else None
    delay = 5.0
    reason = ""
    for attempt in range(retries):
        if should_stop and should_stop():
            raise Stopped()
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=(10, 30), proxies=proxies)
            code = r.status_code
        except requests.RequestException as exc:
            code, reason = None, f"did not respond ({type(exc).__name__})"
        _sleep(pause, should_stop)
        if code == 200:
            return r.content
        if code == 404:
            return b""
        if code is not None and code not in (429, 500, 502, 503, 504):
            r.raise_for_status()
        if code is not None:
            reason = f"refused the request (HTTP {code})"
        if attempt < retries - 1:
            if on_wait:
                on_wait(reason, delay)
            _sleep(delay, should_stop)
            delay = min(delay * 2, 60.0)
    via = f"via proxy {proxy}" if proxy else "no proxy set"
    raise DukascopyBlocked(f"{reason}, {via} after {retries} tries: {url}")


def download(
    symbol: str,
    start: date,
    end: date,
    raw_dir: Path,
    *,
    sides: Iterable[str] = SIDES,
    pause: float = 0.5,
    log=print,
    progress=None,
    on_wait=None,
    should_stop=None,
    give_up_after: int = 2,
) -> dict:
    """Download missing day files into raw_dir, one at a time. Existing files are left untouched.

    If the first `give_up_after` files in a row all fail, Dukascopy is blocking this connection:
    raise DukascopyBlocked at once instead of grinding through every day.
    An empty answer for a recent day (see RECENT_DAYS) is not saved, and an empty file already
    saved for a recent day is fetched again; such days are listed in "not_published".
    Returns counts: {"downloaded", "cached", "empty", "failed": [..], "not_published": [..]}.
    """
    # Day by day, both sides together, so a partial download is still usable.
    jobs = [DayFile(symbol, s, d) for d in day_range(start, end) for s in sides]

    def have(j: DayFile) -> bool:
        p = j.path(raw_dir)
        return p.exists() and not (is_recent(j.day) and p.stat().st_size == 0)

    todo = [j for j in jobs if not have(j)]
    stats = {"requested": len(jobs), "cached": len(jobs) - len(todo), "downloaded": 0, "empty": 0, "failed": [],
             "not_published": []}
    log(f"      {len(jobs)} day files: {stats['cached']} already downloaded, {len(todo)} to go", flush=True)

    t0 = time.monotonic()
    streak = 0
    for i, job in enumerate(todo, 1):
        try:
            payload = _fetch(job.url, pause=pause, on_wait=on_wait, should_stop=should_stop)
            streak = 0
            p = job.path(raw_dir)
            if not payload and is_recent(job.day):
                stats["not_published"].append(f"{job.day} {job.side}")
                p.unlink(missing_ok=True)  # an old empty file must not count as "had it"
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                tmp = p.with_suffix(".part")
                tmp.write_bytes(payload)
                tmp.replace(p)
                stats["downloaded"] += 1
                stats["empty"] += len(payload) == 0
        except Stopped:
            raise
        except Exception as exc:  # recorded, not swallowed
            stats["failed"].append(str(exc))
            streak += 1
            if streak >= give_up_after and stats["downloaded"] == 0:
                raise DukascopyBlocked(str(exc)) from exc
        if progress is not None:
            progress(i, len(todo), len(stats["failed"]))
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
    check_price_scale(symbol, bars)
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
