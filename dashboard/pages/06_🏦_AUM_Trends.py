import streamlit as st
import plotly.express as px
from dashboard.components import fund_selector
from mf_analyser.config import FUND_CODE_TO_NAME
from mf_analyser.aum.tracker import scheme_aum_trend, aum_growth_summary
from mf_analyser.cli import _normalize_fund_name

st.title("🏦 AUM Trends")
scheme_code = fund_selector()
fund_name = FUND_CODE_TO_NAME.get(str(scheme_code), f"Scheme {scheme_code}")

st.header(f"AUM Trend: {fund_name}")

col1, col2 = st.columns(2)
start_year = col1.number_input("Start Year", min_value=2010, max_value=2026, value=2015)
combine_variants = col2.checkbox("Combine Sub-scheme Variants", value=True)

with st.spinner("Compiling historical AUM snapshots..."):
    try:
        norm_name = _normalize_fund_name(fund_name)
    except Exception:
        norm_name = fund_name
    
    try:
        df_aum = scheme_aum_trend(
            scheme_name_query=norm_name,
            start_year=start_year,
            combine=combine_variants,
            force_refresh=False
        )
        
        if df_aum.empty:
            st.warning("No AUM data found for this fund in the given period.")
        else:
            df_aum = aum_growth_summary(df_aum)
            
            st.subheader("Quarterly AUM Growth")
            if combine_variants:
                fig = px.bar(df_aum, x="quarter", y="aum_cr", title=f"Total Managed Assets (Cr) - {norm_name}")
            else:
                if "scheme_name" in df_aum.columns:
                    fig = px.bar(df_aum, x="quarter", y="aum_cr", color="scheme_name", barmode='stack', title=f"AUM Trend by Variant - {norm_name}")
                else:
                    fig = px.bar(df_aum, x="quarter", y="aum_cr", title=f"Combined AUM Trend (Cr) - {norm_name}")
                    
            st.plotly_chart(fig, width="stretch")
            
            st.subheader("AUM Data Logs")
            df_display = df_aum.copy()
            df_display.index = range(1, len(df_display) + 1)
            st.dataframe(df_display, width="stretch")
    except Exception as e:
        st.error(f"Error fetching AUM: {e}")
