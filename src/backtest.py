from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    initial_capital: float = 10_000.0
    fee_bps: float = 5.0
    slippage_bps: float = 2.0
    execution: Literal["close", "open_next"] = "open_next"


def _apply_costs(returns: pd.Series, turnover: pd.Series, fee_bps: float, slip_bps: float) -> pd.Series:
    bps = fee_bps + slip_bps
    cost = (turnover * bps) / 10_000.0
    return returns - cost


def backtest_from_positions(
    df: pd.DataFrame,
    *,
    positions: pd.Series,
    config: BacktestConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Backtest long-only or long/flat positions.

    Returns: (equity_df, trades_df, metrics_dict)
    """
    if "close" not in df.columns:
        raise ValueError("df must include close")

    out = df.copy()
    out["position"] = positions.astype(int).values
    out["position_prev"] = out["position"].shift(1).fillna(0).astype(int)
    base_ret = out["close"].pct_change().fillna(0.0)
    strat_ret = base_ret * out["position_prev"]
    turnover = (out["position"] - out["position_prev"]).abs()
    strat_ret = _apply_costs(strat_ret, turnover, config.fee_bps, config.slippage_bps)
    out["strategy_return"] = strat_ret
    out["equity"] = config.initial_capital * (1 + out["strategy_return"]).cumprod()
    out["drawdown"] = out["equity"] / out["equity"].cummax() - 1.0

    trades = []
    entry_index = None
    for i in range(1, len(out)):
        if out.iloc[i]["position"] == 1 and out.iloc[i - 1]["position"] == 0:
            entry_index = i
        elif out.iloc[i]["position"] == 0 and out.iloc[i - 1]["position"] == 1 and entry_index is not None:
            entry_price = out.iloc[entry_index]["close"]
            exit_price = out.iloc[i]["close"]
            trades.append({
                "entry_time": out.iloc[entry_index]["date"],
                "exit_time": out.iloc[i]["date"],
                "entry_price": float(entry_price),
                "exit_price": float(exit_price),
                "return": float(exit_price / entry_price - 1),
            })
            entry_index = None

    trades_df = pd.DataFrame(trades)
    metrics = compute_metrics(out, trades_df)
    equity_df = out[["date", "close", "position", "equity", "drawdown", "strategy_return"]]
    return equity_df, trades_df, metrics


def compute_metrics(equity_frame: pd.DataFrame, trades_df: pd.DataFrame) -> dict:
    eq = equity_frame["equity"]
    rets = equity_frame["strategy_return"]
    total_return = float(eq.iloc[-1] / eq.iloc[0] - 1)
    years = max(len(eq) - 1, 1) / 252.0
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1) if years > 0 else 0.0
    std = float(rets.std(ddof=0))
    downside = rets[rets < 0]
    down_std = float(downside.std(ddof=0))

    metrics = {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": float(equity_frame["drawdown"].min()),
        "sharpe": float(rets.mean() / std * np.sqrt(252)) if std else np.nan,
        "sortino": float(rets.mean() / down_std * np.sqrt(252)) if down_std else np.nan,
    }
    if trades_df.empty:
        return metrics | {"trade_count": 0, "win_rate": np.nan, "avg_trade_return": np.nan, "median_trade_return": np.nan, "profit_factor": np.nan}

    trade_returns = trades_df["return"].astype(float)
    winners, losers = trade_returns[trade_returns > 0], trade_returns[trade_returns < 0]
    gross_loss = float(abs(losers.sum()))
    return metrics | {
        "trade_count": int(len(trade_returns)),
        "win_rate": float(len(winners) / len(trade_returns)),
        "avg_trade_return": float(trade_returns.mean()),
        "median_trade_return": float(trade_returns.median()),
        "profit_factor": float(winners.sum() / gross_loss) if gross_loss else np.inf,
    }
