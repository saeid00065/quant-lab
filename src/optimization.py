from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from .backtest import BacktestConfig, backtest_from_positions
from .strategy import sma_crossover_signals


@dataclass(frozen=True)
class GridResult:
    fast: int
    slow: int
    metrics: dict


def grid_search_sma_crossover(
    df: pd.DataFrame,
    *,
    fast_range: tuple[int, int],
    slow_range: tuple[int, int],
    step: int = 1,
    config: BacktestConfig | None = None,
    objective: Literal["sharpe", "total_return", "cagr", "max_drawdown"] = "sharpe",
) -> tuple[pd.DataFrame, dict]:
    if config is None:
        config = BacktestConfig()

    results = []
    for fast in range(fast_range[0], fast_range[1] + 1, step):
        for slow in range(slow_range[0], slow_range[1] + 1, step):
            if fast >= slow:
                continue

            sig = sma_crossover_signals(df, fast=fast, slow=slow)
            equity, trades, metrics = backtest_from_positions(
                sig,
                positions=sig["position"],
                config=config,
            )
            row = {"fast": fast, "slow": slow}
            row.update(metrics)
            results.append(row)

    table = pd.DataFrame(results)
    if table.empty:
        raise ValueError("No valid parameter combinations found")

    if objective == "max_drawdown":
        table = table.sort_values(["max_drawdown"], ascending=True)
    else:
        table = table.sort_values([objective], ascending=False)

    best_row = table.iloc[0].to_dict()
    best = {"fast": int(best_row["fast"]), "slow": int(best_row["slow"]), "metrics": best_row}
    return table.reset_index(drop=True), best

