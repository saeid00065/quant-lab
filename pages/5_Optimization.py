import streamlit as st
import pandas as pd

from src.backtest import BacktestConfig
from src.optimization import grid_search_sma_crossover
from pages.common import DATA_KEY
from pages.common import save_to_session, SIGNALS_KEY, BACKTEST_KEY, ensure_df, load_from_session
from src.strategy import sma_crossover_signals


st.header("5) Optimization")

df = load_from_session(DATA_KEY)
ensure_df(df)

col1, col2 = st.columns(2)
with col1:
    fast_min = st.number_input("Fast min", 2, 200, 10)
    fast_max = st.number_input("Fast max", 2, 250, 40)
with col2:
    slow_min = st.number_input("Slow min", 5, 250, 30)
    slow_max = st.number_input("Slow max", 5, 400, 120)

step = st.number_input("Step", 1, 20, 2)
objective = st.selectbox("Objective", ["sharpe", "total_return", "cagr", "max_drawdown"], index=0)

fee_bps = st.slider("Fee (bps)", 0.0, 50.0, 5.0, step=1.0)
slippage_bps = st.slider("Slippage (bps)", 0.0, 50.0, 2.0, step=1.0)

if st.button("Run grid search", type="primary"):
    config = BacktestConfig(initial_capital=10_000.0, fee_bps=float(fee_bps), slippage_bps=float(slippage_bps))
    table, best = grid_search_sma_crossover(
        df,
        fast_range=(int(fast_min), int(fast_max)),
        slow_range=(int(slow_min), int(slow_max)),
        step=int(step),
        config=config,
        objective=objective,
    )
    save_to_session("quantlab_opt_table", table)
    save_to_session("quantlab_opt_best", best)
    st.success("Optimization complete.")

opt_table = load_from_session("quantlab_opt_table")
opt_best = load_from_session("quantlab_opt_best")
if opt_table is None:
    st.info("Run grid search to find the best parameters.")
    st.stop()

st.subheader("Best parameters")
st.json(opt_best)

st.subheader("Top results")
st.dataframe(opt_table.head(25), use_container_width=True)

if st.button("Use best params for signals", type="secondary"):
    best_fast = int(opt_best["fast"])
    best_slow = int(opt_best["slow"])
    sig = sma_crossover_signals(df, fast=best_fast, slow=best_slow)
    save_to_session(SIGNALS_KEY, sig)
    save_to_session(BACKTEST_KEY, None)
    st.success("Signals updated with best parameters.")

