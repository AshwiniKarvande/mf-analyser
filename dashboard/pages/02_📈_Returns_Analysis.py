import streamlit as st
import plotly.express as px
from dashboard.components import fund_selector
from mf_analyser.data.cache import get_nav
from mf_analyser.analysis.returns import returns_table, rolling_returns, max_drawdown, top_drawdowns
from mf_analyser.config import FUND_CODE_TO_NAME

st.title("📈 Returns Analysis")
scheme_code = fund_selector()
fund_name = FUND_CODE_TO_NAME.get(str(scheme_code), f"Scheme {scheme_code}")

st.header(f"Performance: {fund_name}")

try:
    df_nav = get_nav(scheme_code)
except Exception as e:
    st.error(f"Could not load NAV data for {scheme_code}: {e}")
    st.stop()

if df_nav.empty:
    st.warning("NAV data is empty.")
    st.stop()

# 1. NAV Chart
st.subheader("NAV History")
min_date = df_nav["date"].min().strftime('%Y-%m-%d')
max_date = df_nav["date"].max().strftime('%Y-%m-%d')
fig_nav = px.line(df_nav, x="date", y="nav", title=f"NAV Trend - {fund_name} ({min_date} to {max_date})")
st.plotly_chart(fig_nav, width="stretch")

# 2. Trailing Returns
st.subheader("Trailing Returns")
df_trailing = returns_table(df_nav)
df_trailing.index = range(1, len(df_trailing) + 1)
st.dataframe(df_trailing, width="stretch")

# 3. Drawdown Analysis
st.subheader("Risk: Top 10 Drawdowns")
df_dd = top_drawdowns(df_nav, top_n=10)
if not df_dd.empty:
    st.dataframe(df_dd, width="stretch")
else:
    st.info("No significant drawdowns detected.")

# 4. Rolling Returns
st.subheader("Rolling Returns")
col_sel, _ = st.columns([1, 4])
window_years = col_sel.selectbox("Rolling Window (Years)", options=[1, 2, 3, 5, 7, 10], index=2)
df_roll = rolling_returns(df_nav, window_years=window_years, return_type="cagr")
fig_roll = px.line(df_roll.dropna(), x="date", y=f"rolling_{window_years}y_cagr_pct", title=f"{window_years}-Year Rolling CAGR (%)")
st.plotly_chart(fig_roll, width="stretch")
