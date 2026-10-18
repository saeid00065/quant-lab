import streamlit as st

from src.data_loader import (
    fetch_yfinance_ohlcv,
    generate_synthetic_ohlcv,
    load_csv_bytes,
)
from pages.common import DATA_KEY, save_to_session


st.header("1) Data")

mode = st.radio(
    "Choose data source",
    ["Use synthetic data", "Upload CSV", "Fetch with yfinance"],
    horizontal=True,
)

df = None

if mode == "Use synthetic data":
    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.text_input("Start", value="2020-01-01")
        periods = st.number_input("Periods", min_value=200, max_value=10000, value=1000, step=50)
    with col2:
        volatility = st.number_input("Volatility", min_value=0.001, max_value=0.2, value=0.02, step=0.005)
        drift = st.number_input("Drift", min_value=-0.01, max_value=0.01, value=0.0002, step=0.0002)
    with col3:
        seed = st.number_input("Seed", min_value=0, max_value=9999, value=42, step=1)

    if st.button("Generate", type="primary"):
        df = generate_synthetic_ohlcv(start=start, periods=int(periods), seed=int(seed), volatility=float(volatility), drift=float(drift))

elif mode == "Upload CSV":
    uploaded = st.file_uploader("Upload OHLCV CSV", type=["csv"], accept_multiple_files=False)
    if uploaded is not None and st.button("Load CSV", type="primary"):
        df = load_csv_bytes(uploaded.getvalue())

elif mode == "Fetch with yfinance":
    symbol = st.text_input("Symbol", value="SPY")
    col1, col2 = st.columns(2)
    with col1:
        start = st.text_input("Start", value="2020-01-01")
    with col2:
        end = st.text_input("End (optional)", value="")
    interval = st.selectbox("Interval", ["1d", "1wk"], index=0)
    if st.button("Fetch", type="primary"):
        df = fetch_yfinance_ohlcv(symbol, start=start, end=end or None, interval=interval)


if df is not None:
    save_to_session(DATA_KEY, df)
    save_to_session("quantlab_metadata", {"source": mode})
    save_to_session("quantlab_signals", None)
    save_to_session("quantlab_backtest", None)
    st.success(f"Loaded {len(df)} rows.")

st.subheader("Current dataset")
current = st.session_state.get(DATA_KEY)
if current is not None:
    st.dataframe(current.tail(200), use_container_width=True)
else:
    st.info("Load a dataset to unlock the other pages.")

