from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(window=length, min_periods=length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame(
        {
            "macd": macd_line,
            "macd_signal": signal_line,
            "macd_hist": hist,
        }
    )


def add_indicators(
    df: pd.DataFrame,
    *,
    sma_fast: int | None = None,
    sma_slow: int | None = None,
    ema_length: int | None = None,
    rsi_length: int | None = None,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    which: Literal["all", "sma", "ema", "rsi", "macd", "combo"] = "all",
) -> pd.DataFrame:
    out = df.copy()

    if which in {"all", "combo", "sma"}:
        if sma_fast is not None:
            out[f"sma_{sma_fast}"] = sma(out["close"], sma_fast)
        if sma_slow is not None:
            out[f"sma_{sma_slow}"] = sma(out["close"], sma_slow)

    if which in {"all", "combo", "ema"} and ema_length is not None:
        out[f"ema_{ema_length}"] = ema(out["close"], ema_length)

    if which in {"all", "combo", "rsi"} and rsi_length is not None:
        out[f"rsi_{rsi_length}"] = rsi(out["close"], rsi_length)

    if which in {"all", "combo", "macd"}:
        m = macd(out["close"], macd_fast, macd_slow, macd_signal)
        out = pd.concat([out, m], axis=1)

    return out

