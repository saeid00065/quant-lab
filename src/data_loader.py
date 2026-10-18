from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class OHLCVColumns:
    date: str
    open: str
    high: str
    low: str
    close: str
    volume: Optional[str] = None


def _guess_columns(df: pd.DataFrame) -> OHLCVColumns:
    cols = {c.strip().lower(): c for c in df.columns}

    def pick(*names: str) -> Optional[str]:
        for n in names:
            if n in cols:
                return cols[n]
        return None

    date = pick("date", "time", "timestamp", "datetime")
    open_ = pick("open", "o")
    high = pick("high", "h")
    low = pick("low", "l")
    close = pick("close", "c", "adj close", "adj_close", "adjusted close")
    volume = pick("volume", "vol", "v")

    if not (date and open_ and high and low and close):
        raise ValueError(
            "Could not infer OHLCV columns. Expected at least date, open, high, low, close."
        )

    return OHLCVColumns(
        date=date,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def normalize_ohlcv(
    df: pd.DataFrame,
    *,
    columns: Optional[OHLCVColumns] = None,
    dropna: bool = True,
) -> pd.DataFrame:
    """Normalize a dataframe to: [date, open, high, low, close, volume]."""

    if columns is None:
        columns = _guess_columns(df)

    out = pd.DataFrame(index=None)
    out["date"] = pd.to_datetime(df[columns.date], errors="coerce", utc=False)
    out["open"] = pd.to_numeric(df[columns.open], errors="coerce")
    out["high"] = pd.to_numeric(df[columns.high], errors="coerce")
    out["low"] = pd.to_numeric(df[columns.low], errors="coerce")
    out["close"] = pd.to_numeric(df[columns.close], errors="coerce")
    if columns.volume is not None:
        out["volume"] = pd.to_numeric(df[columns.volume], errors="coerce")
    else:
        out["volume"] = np.nan

    out = out.dropna(subset=["date", "open", "high", "low", "close"])
    out = out.sort_values("date").reset_index(drop=True)
    if dropna:
        out = out.dropna(subset=["open", "high", "low", "close"])
    return out


def load_csv_bytes(content: bytes, *, sep: str = ",") -> pd.DataFrame:
    """Load a user CSV upload and normalize it to OHLCV."""
    df = pd.read_csv(io.BytesIO(content), sep=sep)
    return normalize_ohlcv(df)


def generate_synthetic_ohlcv(
    *,
    start: str = "2020-01-01",
    periods: int = 1000,
    freq: str = "B",
    seed: int = 42,
    start_price: float = 100.0,
    drift: float = 0.0002,
    volatility: float = 0.02,
) -> pd.DataFrame:
    """Generate a realistic-ish synthetic OHLCV series using GBM."""

    rng = np.random.default_rng(seed)
    dates = pd.date_range(start=start, periods=periods, freq=freq)

    rets = drift + volatility * rng.standard_normal(size=len(dates))
    close = start_price * np.exp(np.cumsum(rets))

    # Simple OHLC construction around close
    spread = 0.002 + 0.01 * rng.random(size=len(dates))
    high = close * (1.0 + spread)
    low = close * (1.0 - spread)
    open_ = close * (1.0 + (rng.standard_normal(size=len(dates)) * spread * 0.25))
    volume = (1e6 * (1 + rng.random(size=len(dates)))).astype(int)

    return (
        pd.DataFrame(
            {
                "date": dates,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )
        .sort_values("date")
        .reset_index(drop=True)
    )


def fetch_yfinance_ohlcv(
    symbol: str,
    *,
    start: str,
    end: Optional[str] = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """Fetch OHLCV from yfinance and normalize."""

    import yfinance as yf

    data = yf.download(symbol, start=start, end=end, interval=interval, progress=False)
    if data is None or len(data) == 0:
        raise ValueError(f"No data returned for symbol={symbol!r}")

    data = data.reset_index()
    # yfinance uses Open/High/Low/Close/Volume
    data.columns = [str(c).strip().lower() for c in data.columns]
    col_map = {
        "date": "date" if "date" in data.columns else "index",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume" if "volume" in data.columns else None,
    }
    columns = OHLCVColumns(
        date="date" if "date" in data.columns else data.columns[0],
        open="open",
        high="high",
        low="low",
        close="close",
        volume=col_map["volume"],
    )
    return normalize_ohlcv(data, columns=columns)

