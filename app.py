import streamlit as st
import pandas as pd
st.set_page_config(layout='wide')
if 'portfolio_value' not in st.session_state: st.session_state['portfolio_value'] = 1250000.0
page = st.sidebar.radio('Navigation', ['DASHBOARD', 'RISK MGMT', 'EXECUTION', 'PORTFOLIO', 'MONITORING'])
if page == 'DASHBOARD':
    st.metric('Portfolio Value', f'')
else:
    st.write(f'## {page}')
