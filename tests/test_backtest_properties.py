"""Property-based tests for the backtest engine, indicators and SMA strategy (Hypothesis).

Hypothesis generates many random price paths and position sequences; each test states a rule
that must hold for all of them. Expected values are recomputed independently here (plain loops),
never taken from the code under test.

Engine accounting model (src/backtest.py docstring). pos_t = target decided at close t; h_t = position held
after the fill on bar t (close mode: h_t = pos_t; open_next: h_t = pos_{t-1}, h_{-1} = pos_{-1} = 0):
    close:     1 + ret_t = (1 + h_{t-1} * (close_t / close_{t-1} - 1)) * (1 - turn_t * c)
    open_next: 1 + ret_t = (1 + h_{t-1} * (open_t / close_{t-1} - 1)) * (1 - turn_t * c) * (1 + h_t * (close_t / open_t - 1))
    turn_t = |h_t - h_{t-1}|,  c = (fee_bps + slippage_bps) / 1e4,  equity_t = capital * prod_{s<=t} (1 + ret_s)
Costs are paid at the fill: after the price move that happened before it, before the move after it.

Tolerance: rel 1e-9 / abs 1e-9 — results are products of up to ~150 float factors, so only
rounding error (~1e-13) is expected; anything larger is a real difference.
Runs are reproducible: derandomize=True fixes the examples, no example database is used.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings, strategies as st

from src.backtest import BacktestConfig, backtest_from_positions
from src.indicators import ema, macd, rsi, sma
from src.strategy import sma_crossover_signals

REL = ABS = 1e-9
PROPS = settings(max_examples=60, deadline=None, derandomize=True, database=None)


# ---------- generators ----------

log_moves = st.floats(-0.05, 0.05, allow_nan=False)


def _bars_from(log_gaps, log_moves_, start=100.0):
    """open_t = close_{t-1} * e^gap_t, close_t = open_t * e^move_t."""
    opens, closes, prev = [], [], start
    for g, m in zip(log_gaps, log_moves_):
        o = prev * math.exp(g)
        prev = o * math.exp(m)
        opens.append(o)
        closes.append(prev)
    return opens, closes


@st.composite
def prices(draw, min_len=2, max_len=150):
    """Daily bars with positive opens and closes; overnight gaps and intraday moves within +-5% (log)."""
    n = draw(st.integers(min_len, max_len))
    gaps = draw(st.lists(log_moves, min_size=n, max_size=n))
    moves = draw(st.lists(log_moves, min_size=n, max_size=n))
    opens, closes = _bars_from(gaps, moves)
    return pd.DataFrame({"date": pd.date_range("2024-01-01", periods=n, freq="D"), "open": opens, "close": closes})


@st.composite
def prices_and_positions(draw, **kw):
    df = draw(prices(**kw))
    pos = draw(st.lists(st.sampled_from([0, 1]), min_size=len(df), max_size=len(df)))
    return df, pd.Series(pos)


costs = st.tuples(st.floats(0, 50), st.floats(0, 50))  # fee_bps, slippage_bps
MODES = pytest.mark.parametrize("mode", ["close", "open_next"])


def _run(df, pos, fee=0.0, slip=0.0, capital=10_000.0, mode="close"):
    return backtest_from_positions(df, positions=pos, config=BacktestConfig(capital, fee, slip, mode))


def _held(pos, mode):
    p = [int(x) for x in pos]
    return p if mode == "close" else [0] + p[:-1]


# ---------- accounting ----------

@MODES
@PROPS
@given(data=prices_and_positions(), cost=costs)
def test_equity_follows_the_accounting_recursion(mode, data, cost):
    """Every bar: equity change == held position x price move - cost of the fill, per the documented model."""
    df, pos = data
    fee, slip = cost
    eq, _, _ = _run(df, pos, fee, slip, mode=mode)
    o, c, h = df["open"].to_numpy(), df["close"].to_numpy(), _held(pos, mode)
    rate = (fee + slip) / 1e4
    equity, h_prev, c_prev = 10_000.0, 0, None
    for t in range(len(df)):
        paid = 1 - abs(h[t] - h_prev) * rate
        if mode == "close":
            equity *= (1 + h_prev * (c[t] / c_prev - 1 if t else 0.0)) * paid
        else:
            gap = o[t] / c_prev - 1 if t else 0.0
            equity *= (1 + h_prev * gap) * paid * (1 + h[t] * (c[t] / o[t] - 1))
        assert eq["equity"].iloc[t] == pytest.approx(equity, rel=REL, abs=ABS)
        assert eq["position_held"].iloc[t] == h[t]
        h_prev, c_prev = h[t], c[t]


@MODES
@PROPS
@given(df=prices(), cost=costs)
def test_always_flat_never_changes_equity(mode, df, cost):
    eq, trades, metrics = _run(df, pd.Series(0, index=df.index), *cost, mode=mode)
    assert (eq["equity"] == 10_000.0).all()
    assert trades.empty and metrics["trade_count"] == 0
    assert metrics["max_drawdown"] == 0.0


@MODES
@PROPS
@given(df=prices(), cost=costs)
def test_always_long_is_buy_and_hold_minus_one_entry_cost(mode, df, cost):
    """close: bought at close[0]; open_next: bought at open[1] (decided at close[0])."""
    fee, slip = cost
    eq, _, metrics = _run(df, pd.Series(1, index=df.index), fee, slip, mode=mode)
    entry = df["close"].iloc[0] if mode == "close" else df["open"].iloc[1]
    expected = 10_000.0 * (1 - (fee + slip) / 1e4) * df["close"].iloc[-1] / entry
    assert eq["equity"].iloc[-1] == pytest.approx(expected, rel=REL, abs=ABS)
    assert metrics["open_position_at_end"] == 1


@MODES
@PROPS
@given(data=prices_and_positions(), cost=costs, extra_bps=st.floats(0.01, 50))
def test_higher_costs_never_increase_final_equity(mode, data, cost, extra_bps):
    df, pos = data
    fee, slip = cost
    cheap = _run(df, pos, fee, slip, mode=mode)[0]["equity"].iloc[-1]
    dear = _run(df, pos, fee + extra_bps, slip, mode=mode)[0]["equity"].iloc[-1]
    assert dear <= cheap * (1 + REL)
    if not any(_held(pos, mode)):  # never filled -> costs irrelevant
        assert dear == cheap


@MODES
@PROPS
@given(data=prices_and_positions())
def test_equity_scales_linearly_with_capital(mode, data):
    df, pos = data
    a = _run(df, pos, 5, 2, capital=1_000.0, mode=mode)[0]["equity"].to_numpy()
    b = _run(df, pos, 5, 2, capital=7_500.0, mode=mode)[0]["equity"].to_numpy()
    np.testing.assert_allclose(b, a * 7.5, rtol=REL)


@MODES
@PROPS
@given(data=prices_and_positions(min_len=3))
def test_trade_ledger_reconciles_with_equity_when_flat_at_end(mode, data):
    """No costs, nothing held on the last bar: compounding the closed trades == total equity growth."""
    df, pos = data
    pos.iloc[-1] = 0
    if mode == "open_next":
        pos.iloc[-2] = 0  # held on the last bar = target from the bar before
    eq, trades, metrics = _run(df, pos, mode=mode)
    growth = math.prod(1 + r for r in trades["return"]) if not trades.empty else 1.0
    assert growth == pytest.approx(eq["equity"].iloc[-1] / 10_000.0, rel=REL)
    h = pd.Series(_held(pos, mode))
    entries = int(((h == 1) & (h.shift(1, fill_value=0) == 0)).sum())
    assert metrics["trade_count"] == len(trades) == entries
    assert metrics["open_position_at_end"] == 0


@MODES
@PROPS
@given(data=prices_and_positions(), cost=costs)
def test_drawdown_matches_independent_running_peak(mode, data, cost):
    df, pos = data
    eq, _, metrics = _run(df, pos, *cost, mode=mode)
    peak, worst = -math.inf, 0.0
    for t, e in enumerate(eq["equity"]):
        peak = max(peak, e)
        dd = e / peak - 1
        assert eq["drawdown"].iloc[t] == pytest.approx(dd, abs=ABS)
        worst = min(worst, dd)
    assert -1.0 <= metrics["max_drawdown"] <= 0.0
    assert metrics["max_drawdown"] == pytest.approx(worst, abs=ABS)


# ---------- timing ----------

@PROPS
@given(prices_and_positions(min_len=3))
def test_position_decided_on_last_bar_does_not_earn_that_bar(data):
    """close mode, zero cost: flipping only the final target cannot change any equity value."""
    df, pos = data
    flipped = pos.copy()
    flipped.iloc[-1] = 1 - flipped.iloc[-1]
    a = _run(df, pos)[0]["equity"].to_numpy()
    b = _run(df, flipped)[0]["equity"].to_numpy()
    np.testing.assert_allclose(a, b, rtol=REL)


@PROPS
@given(prices_and_positions(min_len=3), costs)
def test_open_next_ignores_the_target_decided_on_the_last_bar(data, cost):
    """open_next: the last target would fill after the data ends, so even its cost never appears."""
    df, pos = data
    flipped = pos.copy()
    flipped.iloc[-1] = 1 - flipped.iloc[-1]
    a = _run(df, pos, *cost, mode="open_next")[0]["equity"].to_numpy()
    b = _run(df, flipped, *cost, mode="open_next")[0]["equity"].to_numpy()
    np.testing.assert_array_equal(a, b)


@PROPS
@given(prices_and_positions(min_len=3))
def test_open_next_equity_before_the_fill_bar_ignores_that_bar_open(data):
    """Changing open[t] can only affect equity from bar t on (no peeking at the next open)."""
    df, pos = data
    t = len(df) // 2
    other = df.copy()
    other.loc[t, "open"] *= 1.03
    a = _run(df, pos, 5, 2, mode="open_next")[0]["equity"]
    b = _run(other, pos, 5, 2, mode="open_next")[0]["equity"]
    _same_prefix(a, b, t)


# ---------- look-ahead leakage ----------

@st.composite
def prices_with_cutoff_and_other_future(draw):
    """A price path, a cutoff, and a second path identical before the cutoff but different after."""
    df = draw(prices(min_len=30, max_len=150))
    k = draw(st.integers(5, len(df) - 1))
    m = len(df) - k
    opens, closes = _bars_from(draw(st.lists(log_moves, min_size=m, max_size=m)),
                               draw(st.lists(log_moves, min_size=m, max_size=m)), start=df["close"].iloc[k - 1])
    other = df.copy()
    other.loc[k:, "open"] = opens
    other.loc[k:, "close"] = closes
    return df, other, k


def _same_prefix(a: pd.Series, b: pd.Series, k: int):
    pd.testing.assert_series_equal(a.iloc[:k].reset_index(drop=True), b.iloc[:k].reset_index(drop=True),
                                   check_names=False, rtol=REL, atol=ABS)


@PROPS
@given(prices_with_cutoff_and_other_future(), st.integers(2, 25))
def test_indicators_before_cutoff_ignore_future_prices(data, length):
    df, other, k = data
    for f in (lambda s: sma(s, length), lambda s: ema(s, length), lambda s: rsi(s, length)):
        _same_prefix(f(df["close"]), f(other["close"]), k)
        _same_prefix(f(df["close"]), f(df["close"].iloc[:k]), k)  # truncated data, too
    for col in ("macd", "macd_signal", "macd_hist"):
        _same_prefix(macd(df["close"])[col], macd(other["close"])[col], k)


@MODES
@PROPS
@given(data=prices_with_cutoff_and_other_future(), fast=st.integers(2, 10), gap=st.integers(1, 15))
def test_sma_signals_and_equity_before_cutoff_ignore_future_prices(mode, data, fast, gap):
    df, other, k = data
    slow = fast + gap
    sig_a = sma_crossover_signals(df, fast=fast, slow=slow)
    sig_b = sma_crossover_signals(other, fast=fast, slow=slow)
    for col in ("position", "trade"):
        _same_prefix(sig_a[col], sig_b[col], k)
    eq_a = _run(df, sig_a["position"], 5, 2, mode=mode)[0]["equity"]
    eq_b = _run(other, sig_b["position"], 5, 2, mode=mode)[0]["equity"]
    _same_prefix(eq_a, eq_b, k)
