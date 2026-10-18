from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


DATA_KEY = "quantlab_df"
SIGNALS_KEY = "quantlab_signals"
BACKTEST_KEY = "quantlab_backtest"


def ensure_df(df: pd.DataFrame | None) -> None:
    if df is None or df.empty:
        st.error("No dataset loaded. Go to the Data page first.")
        st.stop()


def load_from_session(key: str) -> Any:
    return st.session_state.get(key)


def save_to_session(key: str, value: Any) -> None:
    st.session_state[key] = value

