import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
from src.modules.monitoring import PortfolioTracker

st.set_page_config(page_title=\"QUANT LAB - Portfolio\", layout=\"wide\")

ORANGE = \"#ff8c00\"
GREEN = \"#00ff88\"
RED = \"#ff4444\"
BLUE = \"#00aaff\"
BG_DARK = \"#0d0d0d\"
BG_PANEL = \"#141414\"

st.markdown(f\'\'\'
<style>
.metric-card {{ background: {BG_PANEL}; border-left: 3px solid {ORANGE}; padding: 15px; border-radius: 4px; margin-bottom: 10px; }}
.metric-value {{ font-size: 24px; font-weight: bold; color: {GREEN}; }}
.metric-label {{ font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 1px; }}
.panel {{ background: {BG_PANEL}; border: 1px solid #2a2a2a; border-radius: 4px; padding: 15px; }}
</style>
<div class=\"header-bar\">
    <div><span class=\"logo\">⚡ QUANT LAB</span><span style=\"color: #888; margin-left: 15px;\">PORTFOLIO MANAGEMENT</span></div>
    <div style=\"display: flex; align-items: center; gap: 10px;\"><div class=\"status-dot\"></div><span style=\"color: {GREEN};\">ACTIVE</span><span style=\"color: #888; margin-left: 15px;\">{datetime.now().strftime(\"%Y-%m-%d %H:%M:%S\")}</span></div>
</div>
\'\'\', unsafe_allow_html=True)

if 'portfolio_tracker' not in st.session_state:
    st.session_state['portfolio_tracker'] = PortfolioTracker(\"main\")

tracker = st.session_state['portfolio_tracker']

with st.sidebar:
    st.markdown(\"### Portfolio Actions\")
    
    # Add position form
    st.markdown(\"#### Add Position\")
    sym = st.text_input(\"Symbol\", value=\"SPY\").upper()
    qty = st.number_input(\"Quantity\", min_value=1, value=100)
    price = st.number_input(\"Price\", min_value=0.01, value=100.0)
    comm = st.number_input(\"Commission\", min_value=0.0, value=0.0)
    
    if st.button(\"Add/Update Position\", type=\"primary\"):
        tracker.update_position(sym, qty, price, comm)
        st.success(f\"Position {sym} updated\")
    
    st.markdown(\"---Remove Position\")
    remove_sym = st.text_input(\"Symbol to Remove\").upper()
    if st.button(\"Remove\"):
        tracker.update_position(remove_sym, 0, 0)
        st.success(f\"Position {remove_sym} removed\")

# Portfolio summary
summary = tracker.get_portfolio_summary()

st.markdown(\"### Portfolio Overview\")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    mv = summary[\"total_market_value\"]
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {GREEN};\">\\</div>
        <div class=\"metric-label\">Total Value</div>
    </div>
    \'\'\', unsafe_allow_html=True)

with col2:
    pnl = summary[\"total_unrealized_pnl\"]
    color = GREEN if pnl >= 0 else RED
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {color};\">\\</div>
        <div class=\"metric-label\">Unrealized P&L</div>
    </div>
    \'\'\', unsafe_allow_html=True)

with col3:
    cost = summary[\"total_cost_basis\"]
    pnl_pct = (pnl / cost * 100) if cost > 0 else 0
    color = GREEN if pnl_pct >= 0 else RED
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {color};\">{pnl_pct:+.1f}%</div>
        <div class=\"metric-label\">Return %</div>
    </div>
    \'\'\', unsafe_allow_html=True)

with col4:
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {ORANGE};\">{summary[\"num_positions\"]}</div>
        <div class=\"metric-label\">Positions</div>
    </div>
    \'\'\', unsafe_allow_html=True)

with col5:
    le = summary[\"long_exposure\"]
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {BLUE};\">\\</div>
        <div class=\"metric-label\">Long Exposure</div>
    </div>
    \'\'\', unsafe_allow_html=True)

# Positions table
st.markdown(\"### Current Positions\")
positions_df = tracker.get_positions_dataframe()
if not positions_df.empty:
    # Style the dataframe
    def color_pnl(val):
        if val > 0:
            return f\"color: {GREEN}\"
        elif val < 0:
            return f\"color: {RED}\"
        return \"\"
    
    styled = positions_df.style.applymap(color_pnl, subset=['unrealized_pnl', 'unrealized_pnl_pct'])
    st.dataframe(styled.format({
        'avg_price': '\\',
        'current_price': '\\',
        'market_value': '\\',
        'unrealized_pnl': '\\',
        'unrealized_pnl_pct': '{:+.1f}%'
    }), use_container_width=True, hide_index=True)
else:
    st.info(\"No positions yet. Add positions using the sidebar.\")

# Pie chart of allocation
st.markdown(\"### Allocation\")
if not positions_df.empty:
    fig = px.pie(
        positions_df,
        values='market_value',
        names='symbol',
        color_discrete_sequence=[ORANGE, BLUE, GREEN, RED, YELLOW, '#9b59b6', '#3498db', '#e74c3c'],
    )
    fig.update_layout(
        template=\"plotly_dark\",
        paper_bgcolor=BG_PANEL,
        margin=dict(l=20, r=20, t=40, b=20),
        height=350,
    )
    st.plotly_chart(fig, use_container_width=True)

# Recent transactions
st.markdown(\"### Recent Transactions\")
tx_df = tracker.get_transactions_df(days=30)
if not tx_df.empty:
    st.dataframe(tx_df, use_container_width=True, hide_index=True)
else:
    st.info(\"No recent transactions\")

# P&L over time (simulated)
st.markdown(\"### P&L History\")
if len(tx_df) > 1:
    # Create cumulative P&L chart
    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
    pnl_series = pd.Series([
        sum(float(t.get('quantity', 0)) * float(t.get('price', 0)) * (0.001 * i) 
            for t in tx_df.head(i)) if i > 0 else 0 
        for i in range(len(dates))
    ], index=dates)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pnl_series.index,
        y=pnl_series.values,
        fill='tozeroy',
        mode='lines',
        line=dict(color=ORANGE, width=2),
        fillcolor=f\"{ORANGE}33\",
    ))
    fig.update_layout(
        template=\"plotly_dark\",
        paper_bgcolor=BG_PANEL,
        plot_bgcolor=BG_PANEL,
        margin=dict(l=20, r=20, t=40, b=20),
        height=300,
        xaxis=dict(title=\"Date\", color=\"#888\"),
        yaxis=dict(title=\"P&L\", color=\"#888\"),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info(\"Need more transactions to show P&L history\")
