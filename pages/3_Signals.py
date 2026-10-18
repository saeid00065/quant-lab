import streamlit as st
import plotly.graph_objects as go

from src.strategy import sma_crossover_signals
from pages.common import DATA_KEY, SIGNALS_KEY, BACKTEST_KEY, ensure_df, load_from_session, save_to_session


st.header("3) Signals")

df = load_from_session(DATA_KEY)
ensure_df(df)

strategy = st.selectbox("Strategy", ["SMA Crossover (Long-only)"])

fast = st.slider("Fast SMA", 2, 100, 20)
slow = st.slider("Slow SMA", 5, 200, 50)

col1, col2 = st.columns(2)
with col1:
    if st.button("Generate signals", type="primary"):
        sig = sma_crossover_signals(df, fast=fast, slow=slow)
        save_to_session(SIGNALS_KEY, sig)
        save_to_session(BACKTEST_KEY, None)
        st.success("Signals generated.")
    else:
        st.caption("Generate signals to unlock Backtesting.")


signals = load_from_session(SIGNALS_KEY)
if signals is None:
    st.info("Generate signals to unlock Backtesting.")
    st.stop()

st.subheader("Position / trades")
fig = go.Figure()
fig.add_trace(go.Scatter(x=signals["date"], y=signals["close"], mode="lines", name="Close"))
fig.add_trace(
    go.Scatter(
        x=signals["date"],
        y=signals["close"].where(signals["position"] == 1),
        mode="markers",
        marker=dict(size=3),
        name="Long",
    )
)

entries = signals[signals["trade"] == 1]
exits = signals[signals["trade"] == -1]
if not entries.empty:
    fig.add_trace(
        go.Scatter(
            x=entries["date"],
            y=entries["close"],
            mode="markers",
            marker=dict(color="green", size=8),
            name="Entry",
        )
    )
if not exits.empty:
    fig.add_trace(
        go.Scatter(
            x=exits["date"],
            y=exits["close"],
            mode="markers",
            marker=dict(color="red", size=8),
            name="Exit",
        )
    )

st.plotly_chart(fig, use_container_width=True)

st.subheader("Signals table")
st.dataframe(signals[["date", "close", "position", "trade"]].tail(200), use_container_width=True)
