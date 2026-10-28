"""Fill-timing tests for src/backtest.py. Expected values are worked out by hand from the prices below.

Bars (open, close): 0 (100, 105), 1 (110, 115), 2 (120, 125), 3 (130, 135). Target positions [1, 1, 0, 0]:
long decided at close 0, flat decided at close 2.
  close:     buy at close0=105, sell at close2=125 -> equity x 125/105
  open_next: buy at open1=110,  sell at open3=130  -> equity x 130/110
             (bar 1: 115/110, bar 2: 125/115, bar 3: gap 130/125 then flat)
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.backtest import BacktestConfig, backtest_from_positions

REL = 1e-12  # only float rounding on a 4-bar product


def _bars():
    return pd.DataFrame({"date": pd.date_range("2024-01-01", periods=4, freq="D"),
                         "open": [100.0, 110.0, 120.0, 130.0], "close": [105.0, 115.0, 125.0, 135.0]})


def _run(pos, execution, fee=0.0, slip=0.0):
    return backtest_from_positions(_bars(), positions=pd.Series(pos),
                                   config=BacktestConfig(10_000.0, fee, slip, execution))


def test_close_mode_fills_at_same_bar_close():
    eq, trades, m = _run([1, 1, 0, 0], "close")
    assert eq["equity"].tolist() == pytest.approx([10_000, 10_000 * 115 / 105, 10_000 * 125 / 105, 10_000 * 125 / 105], rel=REL)
    assert eq["position_held"].tolist() == [1, 1, 0, 0]
    assert trades[["entry_price", "exit_price"]].values.tolist() == [[105.0, 125.0]]
    assert trades["entry_time"].iloc[0] == pd.Timestamp("2024-01-01")  # entry on bar 0 is recorded
    assert m["open_position_at_end"] == 0


def test_open_next_fills_at_next_bar_open():
    eq, trades, m = _run([1, 1, 0, 0], "open_next")
    assert eq["equity"].tolist() == pytest.approx([10_000, 10_000 * 115 / 110, 10_000 * 125 / 110, 10_000 * 130 / 110], rel=REL)
    assert eq["position"].tolist() == [1, 1, 0, 0]          # target, as decided
    assert eq["position_held"].tolist() == [0, 1, 1, 0]     # one bar later
    assert trades[["entry_price", "exit_price"]].values.tolist() == [[110.0, 130.0]]
    assert trades[["entry_time", "exit_time"]].values.tolist() == [[pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-04")]]
    assert trades["return"].iloc[0] == pytest.approx(130 / 110 - 1, rel=REL)


def test_open_next_costs_charged_on_fill_bars():
    eq, _, _ = _run([1, 1, 0, 0], "open_next", fee=7.0, slip=3.0)  # 10 bps = 0.001 per unit of turnover
    r1 = 0.999 * 115 / 110 - 1   # pay 0.1% at the open-1 buy, then hold to close 1
    r2 = 125 / 115 - 1           # gap 115->120 and move 120->125, no fill
    r3 = 130 / 125 * 0.999 - 1   # gap 125->130 held, then pay 0.1% at the open-3 sell
    assert eq["strategy_return"].tolist() == pytest.approx([0.0, r1, r2, r3], rel=REL)
    assert eq["equity"].iloc[-1] == pytest.approx(10_000 * (1 + r1) * (1 + r2) * (1 + r3), rel=REL)


def test_open_next_exit_takes_the_overnight_gap():
    df = _bars()
    df.loc[2, "open"] = 90.0  # gap down after the flat decision at close 1
    eq, trades, _ = backtest_from_positions(df, positions=pd.Series([1, 0, 0, 0]),
                                            config=BacktestConfig(10_000.0, 0.0, 0.0, "open_next"))
    assert eq["equity"].iloc[-1] == pytest.approx(10_000 * 90 / 110, rel=REL)  # bought 110, sold 90
    assert trades["exit_price"].iloc[0] == 90.0


def test_signal_on_last_bar_is_never_filled_with_open_next():
    eq, trades, m = _run([0, 0, 0, 1], "open_next", fee=5.0, slip=2.0)
    assert (eq["equity"] == 10_000.0).all() and trades.empty
    assert m["open_position_at_end"] == 0
    eq_c, _, m_c = _run([0, 0, 0, 1], "close", fee=5.0, slip=2.0)
    assert eq_c["equity"].iloc[-1] == pytest.approx(10_000 * (1 - 0.0007), rel=REL)  # filled, cost paid
    assert m_c["open_position_at_end"] == 1


def test_open_next_needs_open_column():
    with pytest.raises(ValueError, match="open column"):
        backtest_from_positions(_bars().drop(columns="open"), positions=pd.Series([0, 1, 1, 0]),
                                config=BacktestConfig(execution="open_next"))


def test_unknown_execution_is_rejected():
    with pytest.raises(ValueError, match="Unknown execution"):
        _run([0, 1, 1, 0], "vwap")
