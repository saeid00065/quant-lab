"""Momentum strategy candidate. Long when trend and momentum agree."""
from __future__ import annotations

import pandas as pd


def make_signals(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["sma_fast"] = out["close"].rolling(10).mean()
    out["sma_slow"] = out["close"].rolling(40).mean()
    out["trend_up"] = out["sma_fast"] > out["sma_slow"]

    out["ret"] = out["close"].pct_change()
    out["momentum"] = out["ret"].rolling(5).sum()
    out["next_ret"] = out["ret"].shift(-1)
    out["confirmed"] = out["momentum"].where(out["next_ret"] > 0, 0.0) > 0

    out["vol"] = out["ret"].rolling(21, center=True).std()
    out["calm"] = out["vol"] < out["vol"].median()

    out["signal"] = (out["trend_up"] & out["confirmed"] & out["calm"]).astype(int)
    return out
