import streamlit as st
import plotly.express as px
import pandas as pd
from dashboard.components import fund_selector
from mf_analyser.data.cache import get_holdings
from mf_analyser.analysis.holdings import get_sector_allocation, get_top_holdings
from mf_analyser.config import FUND_CODE_TO_NAME

st.title("💼 Portfolio Holdings")
scheme_code = fund_selector()
fund_name = FUND_CODE_TO_NAME.get(str(scheme_code), f"Scheme {scheme_code}")

st.header(f"Holdings: {fund_name}")

try:
    data = get_holdings(scheme_code)
except Exception as e:
    st.error(f"Could not load Holdings data for {scheme_code}: {e}")
    st.stop()
    
# Display Top Holdings
st.subheader("Top 10 Holdings")
top_h = get_top_holdings(data, top_n=10)
df_top = pd.DataFrame(top_h)
df_top.index = range(1, len(df_top) + 1)
st.dataframe(df_top, width="stretch")

# Sector Allocation
st.subheader("Sector Allocation")
df_sectors = get_sector_allocation(data)
if not df_sectors.empty:
    fig_pie = px.pie(df_sectors, values='weightage', names='sector', title="Sector Distribution")
    st.plotly_chart(fig_pie, width="stretch")

# Full Treemap
st.subheader("Portfolio Treemap")
df_all = pd.DataFrame(data["holdings"])
if not df_all.empty:
    fig_tree = px.treemap(df_all, path=[px.Constant("Portfolio"), 'sector', 'name'], values='weightage',
                          color='weightage', color_continuous_scale='RdYlGn',
                          title="Holdings Treemap")
    st.plotly_chart(fig_tree, width="stretch")
