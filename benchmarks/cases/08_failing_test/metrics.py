"""Small metrics module that is about to be used in reports."""
from __future__ import annotations


def total_return(equity: list[float]) -> float:
    return equity[-1] / equity[0] - 1


def max_drawdown(equity: list[float]) -> float:
    worst = 0.0
    low = equity[0]
    for value in equity:
        low = min(low, value)
        worst = min(worst, value / low - 1)
    return worst


def win_rate(trade_returns: list[float]) -> float:
    if not trade_returns:
        return float("nan")
    return sum(r > 0 for r in trade_returns) / len(trade_returns)
