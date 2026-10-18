import json

import pandas as pd
import streamlit as st

from pages.common import BACKTEST_KEY, load_from_session


st.header("6) Reports")

bt = load_from_session(BACKTEST_KEY)
if bt is None:
    st.info("Run Backtesting first to generate reports.")
    st.stop()

metrics = bt["metrics"]
trades = bt["trades"]

st.subheader("Metrics")
st.json(metrics)

if trades is not None and not trades.empty:
    st.subheader("Trades")
    st.dataframe(trades, use_container_width=True)

st.divider()
st.subheader("Download")

col1, col2 = st.columns(2)
with col1:
    if st.button("Download metrics JSON"):
        st.download_button(
            "Download metrics JSON",
            data=json.dumps(metrics, indent=2),
            file_name="metrics.json",
            mime="application/json",
        )
with col2:
    csv = None
    if trades is not None and not trades.empty:
        csv = trades.to_csv(index=False)
    if st.button("Download trades CSV", disabled=(csv is None)):
        st.download_button(
            "Download trades CSV",
            data=csv,
            file_name="trades.csv",
            mime="text/csv",
        )

