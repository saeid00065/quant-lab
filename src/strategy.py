from __future__ import annotations

import numpy as np
import pandas as pd


def sma_crossover_signals(
    df: pd.DataFrame,
    *,
    fast: int,
    slow: int,
) -> pd.DataFrame:
    """Long-only: position=1 when fast SMA crosses above slow SMA."""

    from .indicators import sma

    if fast >= slow:
        raise ValueError("fast must be < slow")

    out = df.copy()
    out["sma_fast"] = sma(out["close"], fast)
    out["sma_slow"] = sma(out["close"], slow)

    # Define regime: long when fast > slow
    out["position"] = (out["sma_fast"] > out["sma_slow"]).astype(int)

    # Trade markers (changes in position)
    out["position_prev"] = out["position"].shift(1)
    out["trade"] = 0
    out.loc[(out["position_prev"] == 0) & (out["position"] == 1), "trade"] = 1
    out.loc[(out["position_prev"] == 1) & (out["position"] == 0), "trade"] = -1
    out = out.drop(columns=["position_prev"])
    return out


def signals_to_positions(
    df: pd.DataFrame,
    *,
    mode: str = "position",
    position_col: str = "position",
) -> pd.Series:
    if mode != "position":
        raise ValueError("Currently only mode='position' is supported")
    if position_col not in df.columns:
        raise ValueError(f"Missing position column {position_col!r}")
    return df[position_col].astype(int)

