import streamlit as st
import plotly.graph_objects as go

from src.data_loader import normalize_ohlcv
from src.indicators import add_indicators
from pages.common import DATA_KEY, SIGNALS_KEY, ensure_df, load_from_session, save_to_session


st.header("2) Indicators")

df = load_from_session(DATA_KEY)
ensure_df(df)

col1, col2 = st.columns(2)
with col1:
    tab = st.radio(
        "Indicator set",
        ["SMA/EMA", "RSI", "MACD", "SMA + RSI"],
        horizontal=True,
    )
with col2:
    st.write("")

out = df.copy()

if tab in {"SMA/EMA", "SMA + RSI"}:
    sma_fast = st.slider("SMA fast", 2, 200, 20)
    sma_slow = st.slider("SMA slow", 5, 300, 50)
    ema_len = st.slider("EMA length", 2, 200, 21)
    which = "all"
    out = add_indicators(out, sma_fast=sma_fast, sma_slow=sma_slow, ema_length=ema_len, which=which)
else:
    sma_fast = sma_slow = ema_len = None

if tab in {"RSI", "SMA + RSI"}:
    rsi_len = st.slider("RSI length", 2, 60, 14)
    out = add_indicators(out, rsi_length=rsi_len, which="rsi")

if tab == "MACD":
    macd_fast = st.slider("MACD fast", 2, 40, 12)
    macd_slow = st.slider("MACD slow", 5, 80, 26)
    macd_signal = st.slider("MACD signal", 2, 40, 9)
    out = add_indicators(out, macd_fast=macd_fast, macd_slow=macd_slow, macd_signal=macd_signal, which="macd")

st.subheader("Chart")

fig = go.Figure()
fig.add_trace(go.Scatter(x=out["date"], y=out["close"], mode="lines", name="Close"))

if tab in {"SMA/EMA", "SMA + RSI"}:
    fig.add_trace(go.Scatter(x=out["date"], y=out[f"sma_{sma_fast}"], mode="lines", name=f"SMA {sma_fast}"))
    fig.add_trace(go.Scatter(x=out["date"], y=out[f"sma_{sma_slow}"], mode="lines", name=f"SMA {sma_slow}"))
    fig.add_trace(go.Scatter(x=out["date"], y=out[f"ema_{ema_len}"], mode="lines", name=f"EMA {ema_len}"))

st.plotly_chart(fig, use_container_width=True)

if tab in {"RSI", "SMA + RSI"}:
    st.subheader("RSI")
    fig2 = go.Figure()
    rsi_col = [c for c in out.columns if c.startswith("rsi_")][0]
    fig2.add_trace(go.Scatter(x=out["date"], y=out[rsi_col], mode="lines", name=rsi_col))
    fig2.add_hline(y=70, line_dash="dash", line_color="red")
    fig2.add_hline(y=30, line_dash="dash", line_color="green")
    st.plotly_chart(fig2, use_container_width=True)

if tab == "MACD":
    st.subheader("MACD")
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=out["date"], y=out["macd"], mode="lines", name="MACD"))
    fig3.add_trace(go.Scatter(x=out["date"], y=out["macd_signal"], mode="lines", name="Signal"))
    fig3.add_trace(go.Bar(x=out["date"], y=out["macd_hist"], name="Histogram"))
    st.plotly_chart(fig3, use_container_width=True)

st.divider()
latest_cols = [c for c in out.columns if c.startswith("sma_") or c.startswith("ema_") or c.startswith("rsi_")]
if latest_cols:
    st.subheader("Latest values")
    st.dataframe(out[["date"] + latest_cols].tail(10).reset_index(drop=True), use_container_width=True)

