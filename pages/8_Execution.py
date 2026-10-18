import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
from src.modules.execution import ExecutionManager, Order, OrderType, OrderSide

st.set_page_config(page_title=\"QUANT LAB - Execution\", layout=\"wide\")

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
    <div><span class=\"logo\">⚡ QUANT LAB</span><span style=\"color: #888; margin-left: 15px;\">EXECUTION TERMINAL</span></div>
    <div style=\"display: flex; align-items: center; gap: 10px;\"><div class=\"status-dot\"></div><span style=\"color: {GREEN};\">LIVE</span><span style=\"color: #888; margin-left: 15px;\">{datetime.now().strftime(\"%Y-%m-%d %H:%M:%S\")}</span></div>
</div>
\'\'\', unsafe_allow_html=True)

if 'execution_mgr' not in st.session_state:
    st.session_state['execution_mgr'] = ExecutionManager(fee_bps=1.0, slippage_bps=2.0)

exec_mgr = st.session_state['execution_mgr']

with st.sidebar:
    st.markdown(\"### Order Configuration\")
    fee_bps = st.slider(\"Fee (bps)\", 0.0, 10.0, 1.0, 0.5)
    slippage_bps = st.slider(\"Slippage (bps)\", 0.0, 10.0, 2.0, 0.5)
    
    if st.button(\"Update Config\", type=\"primary\"):
        exec_mgr.fee_bps = fee_bps
        exec_mgr.slippage_bps = slippage_bps
        st.success(\"Config updated\")

st.markdown(\"### Order Entry\")

col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
with col1:
    symbol = st.text_input(\"Symbol\", value=\"SPY\").upper()
with col2:
    side = st.selectbox(\"Side\", [\"buy\", \"sell\"])
with col3:
    order_type = st.selectbox(\"Type\", [\"market\", \"limit\", \"stop\", \"stop_limit\"])
with col4:
    quantity = st.number_input(\"Quantity\", min_value=1, value=100)

price = None
stop_price = None

if order_type in [\"limit\", \"stop_limit\"]:
    price = st.number_input(\"Limit Price\", min_value=0.01, value=100.0, step=1.0)

if order_type in [\"stop\", \"stop_limit\"]:
    stop_price = st.number_input(\"Stop Price\", min_value=0.01, value=95.0, step=1.0)

if st.button(\"Submit Order\", type=\"primary\"):
    order = exec_mgr.create_order(
        symbol=symbol,
        side=side,
        quantity=float(quantity),
        order_type=order_type,
        price=float(price) if price else None,
        stop_price=float(stop_price) if stop_price else None,
    )
    st.success(f\"Order submitted: {order.order_id}\")

# Pending orders
st.markdown(\"### Pending Orders\")
pending = exec_mgr.get_pending_orders()
if pending:
    pending_df = pd.DataFrame([
        {
            \"Order ID\": o.order_id,
            \"Symbol\": o.symbol,
            \"Side\": o.side,
            \"Type\": o.order_type,
            \"Qty\": o.quantity,
            \"Price\": f\"\\\" if o.price else \"MKT\",
            \"Stop\": f\"\\\" if o.stop_price else \"-\",
        }
        for o in pending
    ])
    st.dataframe(pending_df, use_container_width=True, hide_index=True)
    
    # Process orders button
    if st.button(\"Process Pending Orders\"):
        current_price = 100.0  # Would come from live data
        prices = exec_mgr._current_prices
        for order in pending:
            price = prices.get(order.symbol, current_price)
            fill = exec_mgr.process_order(order.order_id, price)
            if fill:
                st.success(f\"Filled {order.order_id}: {fill.quantity} @ \\\")
else:
    st.info(\"No pending orders\")

# Execution stats
st.markdown(\"### Execution Statistics\")
stats = exec_mgr.get_execution_stats()

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\">{stats[\"total_orders\"]}</div>
        <div class=\"metric-label\">Total Orders</div>
    </div>
    \'\'\', unsafe_allow_html=True)
with col2:
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {GREEN};\">{stats[\"filled_orders\"]}</div>
        <div class=\"metric-label\">Filled</div>
    </div>
    \'\'\', unsafe_allow_html=True)
with col3:
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {RED};\">{stats[\"cancelled_orders\"]}</div>
        <div class=\"metric-label\">Cancelled</div>
    </div>
    \'\'\', unsafe_allow_html=True)
with col4:
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {ORANGE};\">{stats[\"pending_orders\"]}</div>
        <div class=\"metric-label\">Pending</div>
    </div>
    \'\'\', unsafe_allow_html=True)
with col5:
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {BLUE};\">\\</div>
        <div class=\"metric-label\">Commission</div>
    </div>
    \'\'\', unsafe_allow_html=True)

# Recent fills
st.markdown(\"### Recent Fills\")
fills_df = exec_mgr.get_fills()
if not fills_df.empty:
    st.dataframe(fills_df, use_container_width=True, hide_index=True)
else:
    st.info(\"No fills yet\")

# Order history chart
st.markdown(\"### Order Flow\")
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=list(range(len(pending))) if pending else [],
    y=[o.quantity for o in pending] if pending else [],
    mode='markers',
    marker=dict(size=12, color=[GREEN if o.side == 'buy' else RED for o in pending]),
    text=[f\"{o.symbol}\" for o in pending],
    name='Pending'
))
fig.update_layout(
    template=\"plotly_dark\",
    paper_bgcolor=BG_PANEL,
    plot_bgcolor=BG_PANEL,
    margin=dict(l=20, r=20, t=40, b=20),
    height=300,
    xaxis=dict(title=\"Order\", color=\"#888\"),
    yaxis=dict(title=\"Quantity\", color=\"#888\"),
)
st.plotly_chart(fig, use_container_width=True)
