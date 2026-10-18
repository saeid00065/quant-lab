import streamlit as st
import plotly.graph_objects as go

from src.backtest import BacktestConfig, backtest_from_positions
from pages.common import DATA_KEY, SIGNALS_KEY, BACKTEST_KEY, ensure_df, load_from_session, save_to_session


st.header("4) Backtesting")

df = load_from_session(DATA_KEY)
ensure_df(df)

signals = load_from_session(SIGNALS_KEY)
if signals is None:
    st.error("No signals found. Go to Signals page first.")
    st.stop()

fee_bps = st.slider("Fee (bps)", 0.0, 50.0, 5.0, step=1.0)
slippage_bps = st.slider("Slippage (bps)", 0.0, 50.0, 2.0, step=1.0)
initial_capital = st.number_input("Initial capital", min_value=1000.0, max_value=1_000_000.0, value=10_000.0, step=1000.0)

if st.button("Run backtest", type="primary"):
    config = BacktestConfig(
        initial_capital=float(initial_capital),
        fee_bps=float(fee_bps),
        slippage_bps=float(slippage_bps),
    )
    equity, trades, metrics = backtest_from_positions(
        signals,
        positions=signals["position"],
        config=config,
    )
    save_to_session(BACKTEST_KEY, {"equity": equity, "trades": trades, "metrics": metrics, "config": config})
    st.success("Backtest complete.")

bt = load_from_session(BACKTEST_KEY)
if bt is None:
    st.info("Run the backtest to see results.")
    st.stop()

st.subheader("Metrics")
st.json(bt["metrics"])

st.subheader("Equity curve")
eq = bt["equity"]
fig = go.Figure()
fig.add_trace(go.Scatter(x=eq["date"], y=eq["equity"], mode="lines", name="Equity"))
st.plotly_chart(fig, use_container_width=True)

st.subheader("Drawdown")
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=eq["date"], y=eq["drawdown"], mode="lines", name="Drawdown"))
st.plotly_chart(fig2, use_container_width=True)

st.subheader("Trades")
trades = bt["trades"]
if trades.empty:
    st.info("No trades were generated for these parameters.")
else:
    st.dataframe(trades, use_container_width=True)

