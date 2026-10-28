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


def _cost_factor(turnover: pd.Series, fee_bps: float, slip_bps: float) -> pd.Series:
    """Fraction of equity kept after paying fees + slippage on a fill of size `turnover`."""
    return 1 - turnover * (fee_bps + slip_bps) / 10_000.0


def backtest_from_positions(
    df: pd.DataFrame,
    *,
    positions: pd.Series,
    config: BacktestConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Backtest long-only or long/flat positions.

    `positions[t]` is the target decided with information up to the close of bar t.
    Fill timing (config.execution):
      - "close":     filled at close[t]; held over (close[t], close[t+1]].
      - "open_next": filled at open[t+1]; the overnight gap close[t] -> open[t+1] belongs to the old
                     position, the move open[t+1] -> close[t+1] to the new one. A target decided on the
                     last bar is never filled. Requires an `open` column.
    Bar return: (1 + held_prev * gap) * (1 - turnover * (fee_bps + slippage_bps) / 1e4) * (1 + held * move) - 1,
    i.e. costs are paid as a fraction of equity at the moment of the fill (after the gap, before the move).
    In "close" mode gap is the whole close-to-close return and move is 0. Trade prices are raw fill prices
    (no costs). equity_df["position"] is the target, equity_df["position_held"] the position after the fill.

    Returns: (equity_df, trades_df, metrics_dict)
    """
    if "close" not in df.columns:
        raise ValueError("df must include close")
    if config.execution not in ("close", "open_next"):
        raise ValueError(f"Unknown execution {config.execution!r}")
    if config.execution == "open_next" and "open" not in df.columns:
        raise ValueError("execution='open_next' needs an open column")

    out = df.copy()
    out["position"] = positions.astype(int).values
    close = out["close"].astype(float)
    if config.execution == "close":
        held = out["position"]
        fill_price = close
        gap = close.pct_change().fillna(0.0)                # whole bar is "gap" from the previous close
        move = pd.Series(0.0, index=out.index)
    else:
        held = out["position"].shift(1).fillna(0).astype(int)
        fill_price = out["open"].astype(float)
        gap = (fill_price / close.shift(1) - 1).fillna(0.0)
        move = close / fill_price - 1
    held_prev = held.shift(1).fillna(0).astype(int)
    turnover = (held - held_prev).abs()
    kept = _cost_factor(turnover, config.fee_bps, config.slippage_bps)
    out["position_held"] = held.astype(int)
    out["strategy_return"] = (1 + held_prev * gap) * kept * (1 + held * move) - 1
    out["equity"] = config.initial_capital * (1 + out["strategy_return"]).cumprod()
    out["drawdown"] = out["equity"] / out["equity"].cummax() - 1.0

    trades = []
    entry_index = None
    held_arr, held_prev_arr = held.to_numpy(), held_prev.to_numpy()
    for i in range(len(out)):
        if held_arr[i] == 1 and held_prev_arr[i] == 0:
            entry_index = i
        elif held_arr[i] == 0 and held_prev_arr[i] == 1 and entry_index is not None:
            entry_price, exit_price = float(fill_price.iloc[entry_index]), float(fill_price.iloc[i])
            trades.append({
                "entry_time": out["date"].iloc[entry_index],
                "exit_time": out["date"].iloc[i],
                "entry_price": entry_price,
                "exit_price": exit_price,
                "return": exit_price / entry_price - 1,
            })
            entry_index = None

    trades_df = pd.DataFrame(trades)
    metrics = compute_metrics(out, trades_df) | {"open_position_at_end": int(held_arr[-1]) if len(out) else 0}
    equity_df = out[["date", "close", "position", "position_held", "equity", "drawdown", "strategy_return"]]
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
