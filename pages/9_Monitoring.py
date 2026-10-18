import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from src.modules.monitoring import MonitoringSystem, LogLevel, AlertType

st.set_page_config(page_title=\"QUANT LAB - Monitoring\", layout=\"wide\")

ORANGE = \"#ff8c00\"
GREEN = \"#00ff88\"
RED = \"#ff4444\"
BLUE = \"#00aaff\"
YELLOW = \"#ffdd00\"
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
    <div><span class=\"logo\">⚡ QUANT LAB</span><span style=\"color: #888; margin-left: 15px;\">SYSTEM MONITORING</span></div>
    <div style=\"display: flex; align-items: center; gap: 10px;\"><div class=\"status-dot\"></div><span style=\"color: {GREEN};\">SYSTEM HEALTH</span><span style=\"color: #888; margin-left: 15px;\">{datetime.now().strftime(\"%Y-%m-%d %H:%M:%S\")}</span></div>
</div>
\'\'\', unsafe_allow_html=True)

if 'monitor' not in st.session_state:
    st.session_state['monitor'] = MonitoringSystem(\"quantlab\")

monitor = st.session_state['monitor']

# Health overview
health = monitor.get_system_health()

st.markdown(\"### System Health\")

col1, col2, col3, col4, col5 = st.columns(5)

status_color = GREEN if health[\"status\"] == \"healthy\" else RED
with col1:
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {status_color};\">{health[\"status\"].upper()}</div>
        <div class=\"metric-label\">System Status</div>
    </div>
    \'\'\', unsafe_allow_html=True)

with col2:
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {BLUE};\">{health[\"uptime_formatted\"]}</div>
        <div class=\"metric-label\">Uptime</div>
    </div>
    \'\'\', unsafe_allow_html=True)

with col3:
    critical = health[\"critical_alerts\"]
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {RED if critical > 0 else GREEN};\">{critical}</div>
        <div class=\"metric-label\">Critical Alerts</div>
    </div>
    \'\'\', unsafe_allow_html=True)

with col4:
    active = health[\"active_alerts\"]
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {YELLOW if active > 0 else GREEN};\">{active}</div>
        <div class=\"metric-label\">Active Alerts</div>
    </div>
    \'\'\', unsafe_allow_html=True)

with col5:
    logs = health[\"total_logs\"]
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {ORANGE};\">{logs}</div>
        <div class=\"metric-label\">Total Logs</div>
    </div>
    \'\'\', unsafe_allow_html=True)

# Portfolio health
pf = health[\"portfolio\"]
st.markdown(\"### Portfolio Health\")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\">\\</div>
        <div class=\"metric-label\">Market Value</div>
    </div>
    \'\'\', unsafe_allow_html=True)
with col2:
    pnl = pf[\"total_unrealized_pnl\"]
    color = GREEN if pnl >= 0 else RED
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {color};\">\\</div>
        <div class=\"metric-label\">Unrealized P&L</div>
    </div>
    \'\'\', unsafe_allow_html=True)
with col3:
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {ORANGE};\">{pf[\"num_positions\"]}</div>
        <div class=\"metric-label\">Positions</div>
    </div>
    \'\'\', unsafe_allow_html=True)
with col4:
    exposure = pf[\"net_exposure\"]
    st.markdown(f\'\'\'
    <div class=\"metric-card\">
        <div class=\"metric-value\" style=\"color: {BLUE};\">\\</div>
        <div class=\"metric-label\">Net Exposure</div>
    </div>
    \'\'\', unsafe_allow_html=True)

# Alerts section
st.markdown(\"### Alerts\")

tabs = st.tabs([\"Active Alerts\", \"All Alerts\", \"Logs\"])

with tabs[0]:
    alerts_df = monitor.get_alerts_df(include_acked=False)
    if not alerts_df.empty:
        st.dataframe(alerts_df, use_container_width=True, hide_index=True)
        
        # Acknowledge button
        alert_ids = alerts_df[\"alert_id\"].tolist() if not alerts_df.empty else []
        if alert_ids:
            selected = st.selectbox(\"Select alert to acknowledge\", alert_ids)
            if st.button(\"Acknowledge\"):
                monitor.acknowledge_alert(selected)
                st.success(f\"Acknowledged {selected}\")
                st.rerun()
    else:
        st.success(\"No active alerts - system is healthy\")

with tabs[1]:
    all_alerts = monitor.get_alerts_df(include_acked=True)
    if not all_alerts.empty:
        st.dataframe(all_alerts, use_container_width=True, hide_index=True)
    else:
        st.info(\"No alerts recorded\")

with tabs[2]:
    logs_df = monitor.get_logs_df(limit=100)
    if not logs_df.empty:
        level_filter = st.selectbox(\"Filter by level\", [\"DEBUG\", \"INFO\", \"WARNING\", \"ERROR\", \"CRITICAL\"])
        filtered = logs_df[logs_df[\"level\"] >= level_filter] if level_filter else logs_df
        st.dataframe(filtered, use_container_width=True, hide_index=True)
    else:
        st.info(\"No logs recorded\")

# Log a test message
st.markdown(\"### Actions\")
c1, c2 = st.columns(2)
with c1:
    if st.button(\"Log Test Info\"):
        monitor.info(\"Test info message\", \"manual\")
        st.success(\"Logged test info\")
        st.rerun()
with c2:
    if st.button(\"Trigger Test Alert\"):
        monitor.create_alert(AlertType.SYSTEM, \"Test alert from monitoring page\", LogLevel.WARNING)
        st.success(\"Created test alert\")
        st.rerun()
