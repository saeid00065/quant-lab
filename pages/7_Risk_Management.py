import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

from src.modules.risk_management import RiskManager, RiskConfig
from pages.common import DATA_KEY, load_from_session, save_to_session

st.set_page_config(page_title=\"QUANT LAB - Risk Management\", layout=\"wide\")

ORANGE = \"#ff8c00\"
GREEN = \"#00ff88\"
RED = \"#ff4444\"
BLUE = \"#00aaff\"
BG_DARK = \"#0d0d0d\"
BG_PANEL = \"#141414\"

st.markdown(f'''
<style>
.metric-card {{ background: {BG_PANEL}; border-left: 3px solid {ORANGE}; padding: 15px; border-radius: 4px; margin-bottom: 10px; }}
.metric-value {{ font-size: 24px; font-weight: bold; color: {GREEN}; }}
.metric-label {{ font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 1px; }}
.panel {{ background: {BG_PANEL}; border: 1px solid #2a2a2a; border-radius: 4px; padding: 15px; }}
</style>
''', unsafe_allow_html=True)

st.markdown(f\'\'\'<div class=\"header-bar\">
    <div><span class=\"logo\">⚡ QUANT LAB</span><span style=\"color: #888; margin-left: 15px;\">RISK MANAGEMENT</span></div>
    <div style=\"display: flex; align-items: center; gap: 10px;\">
        <span style=\"color: {GREEN};\">RISK</span>
        <span style=\"color: #888; margin-left: 15px;\">{datetime.now().strftime(\"%Y-%m-%d %H:%M:%S\")}</span>
    </div>
</div>\'\'\', unsafe_allow_html=True)

if 'risk_manager' not in st.session_state:
    st.session_state['risk_manager'] = RiskManager(
        config=RiskConfig(),
        portfolio_value=st.session_state.get('portfolio_value', 1_000_000.0)
    )

risk_mgr = st.session_state['risk_manager']

with st.sidebar:
    st.markdown(\"### Risk Configuration\")
    max_position_pct = st.slider(\"Max Position %\", 0.01, 0.50, 0.10, 0.01)
    max_daily_loss = st.slider(\"Max Daily Loss %\", 0.01, 0.20, 0.05, 0.01)
    min_cash_pct = st.slider(\"Min Cash Reserve %\", 0.01, 0.20, 0.05, 0.01)
    
    if st.button(\"Update Risk Config\", type=\"primary\"):
        risk_mgr.config = RiskConfig(
            max_position_pct=max_position_pct,
            max_daily_loss_pct=max_daily_loss,
            min_cash_pct=min_cash_pct,
        )
        st.success(\"Risk config updated\")

# Risk Overview
st.markdown(\"### Risk Overview\")

df = load_from_session(DATA_KEY)
positions = risk_mgr.positions

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\">\\</div>
        <div class=\"metric-label\">Portfolio Value</div>
    </div>
    \'\'\', unsafe_allow_html=True)

with col2:
    exposure = risk_mgr.get_total_exposure()
    exposure_pct = exposure / risk_mgr.portfolio_value * 100
    color = GREEN if exposure_pct < 50 else ORANGE if exposure_pct < 80 else RED
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {color};\">\\</div>
        <div class=\"metric-label\">Total Exposure ({exposure_pct:.1f}%)</div>
    </div>
    \'\'\', unsafe_allow_html=True)

with col3:
    cash = risk_mgr.get_cash_available()
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {BLUE};\">\\</div>
        <div class=\"metric-label\">Cash Available</div>
    </div>
    \'\'\', unsafe_allow_html=True)

with col4:
    daily_pnl = risk_mgr.daily_pnl
    daily_pnl_pct = daily_pnl / risk_mgr.daily_start * 100 if risk_mgr.daily_start > 0 else 0
    color = GREEN if daily_pnl >= 0 else RED
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {color};\">\\</div>
        <div class=\"metric-label\">Daily P&L ({daily_pnl_pct:+.1f}%)</div>
    </div>
    \'\'\', unsafe_allow_html=True)

with col5:
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {ORANGE};\">{len(positions)}</div>
        <div class=\"metric-label\">Open Positions</div>
    </div>
    \'\'\', unsafe_allow_html=True)

# Position sizing calculator
st.markdown(\"### Position Sizer\")
col1, col2, col3 = st.columns(3)
with col1:
    entry_price = st.number_input(\"Entry Price\", min_value=0.01, value=100.0, step=1.0)
with col2:
    risk_pct = st.number_input(\"Risk Per Trade %\", min_value=0.001, max_value=0.10, value=0.02, step=0.005)
with col3:
    recommended_size = risk_mgr.calculate_position_size(entry_price, risk_pct)
    st.markdown(f\'\'\'
    <div class=\"panel\">
        <div style=\"font-size: 12px; color: #888; margin-bottom: 5px;\">RECOMMENDED SIZE</div>
        <div style=\"font-size: 28px; font-weight: bold; color: {ORANGE};\">{recommended_size:,.0f} shares</div>
        <div style=\"font-size: 11px; color: #888;\">\\ notional</div>
    </div>
    \'\'\', unsafe_allow_html=True)

# Sector exposure
st.markdown(\"### Sector Exposure\")
sector_exp = risk_mgr.get_sector_exposure()
if sector_exp:
    sectors = list(sector_exp.keys())
    values = [sector_exp[s] for s in sectors]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sectors,
        y=values,
        marker_color=[ORANGE, BLUE, GREEN, RED, ORANGE],
        text=[f\"\\\" for v in values],
        textposition='auto',
    ))
    fig.update_layout(
        template=\"plotly_dark\",
        paper_bgcolor=BG_PANEL,
        plot_bgcolor=BG_PANEL,
        margin=dict(l=20, r=20, t=40, b=20),
        height=300,
        xaxis=dict(title=\"\", color=\"#888\"),
        yaxis=dict(title=\"Exposure\", color=\"#888\"),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info(\"No positions to display\")

# Risk checks
st.markdown(\"### Risk Checks\")
check1, check2, check3, check4 = st.columns(4)

with check1:
    check, msg = risk_mgr.check_daily_loss()
    color = GREEN if check else RED
    st.markdown(f\'\'\'
    <div class=\"panel\">
        <div style=\"font-size: 11px; color: #888; margin-bottom: 5px;\">DAILY LOSS LIMIT</div>
        <div style=\"font-size: 16px; font-weight: bold; color: {color};\">{'PASSED' if check else 'BREACHED'}</div>
        <div style=\"font-size: 10px; color: #666;\">{msg}</div>
    </div>
    \'\'\', unsafe_allow_html=True)

with check2:
    max_pct = risk_mgr.config.max_position_pct * 100
    st.markdown(f\'\'\'
    <div class=\"panel\">
        <div style=\"font-size: 11px; color: #888; margin-bottom: 5px;\">POSITION LIMITS</div>
        <div style=\"font-size: 16px; font-weight: bold; color: {ORANGE};\">MAX {max_pct:.0f}%</div>
        <div style=\"font-size: 10px; color: #666;\">Per position</div>
    </div>
    \'\'\', unsafe_allow_html=True)

with check3:
    leverage = risk_mgr.config.max_leverage
    st.markdown(f\'\'\'
    <div class=\"panel\">
        <div style=\"font-size: 11px; color: #888; margin-bottom: 5px;\">LEVERAGE LIMIT</div>
        <div style=\"font-size: 16px; font-weight: bold; color: {BLUE};\">{leverage:.1f}x</div>
        <div style=\"font-size: 10px; color: #666;\">Max exposure</div>
    </div>
    \'\'\', unsafe_allow_html=True)

with check4:
    min_cash = risk_mgr.config.min_cash_pct * 100
    st.markdown(f\'\'\'
    <div class=\"panel\">
        <div style=\"font-size: 11px; color: #888; margin-bottom: 5px;\">CASH RESERVE</div>
        <div style=\"font-size: 16px; font-weight: bold; color: {GREEN};\">MIN {min_cash:.0f}%</div>
        <div style=\"font-size: 10px; color: #666;\">Must maintain</div>
    </div>
    \'\'\', unsafe_allow_html=True)
