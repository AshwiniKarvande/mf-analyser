import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dashboard.components import fund_selector
from mf_analyser.data.cache import get_nav
from mf_analyser.analysis.strategies import sip, lump_sum, momentum_ma, sip_with_stop_loss, value_averaging, sip_buy_on_dip
from mf_analyser.config import FUND_CODE_TO_NAME

st.title("🤖 Strategy Backtester")
scheme_code = fund_selector()
fund_name = FUND_CODE_TO_NAME.get(str(scheme_code), f"Scheme {scheme_code}")

st.header(f"Backtesting on: {fund_name}")

try:
    df_nav = get_nav(scheme_code)
except Exception as e:
    st.error(f"Could not load NAV data for {scheme_code}: {e}")
    st.stop()

if df_nav.empty:
    st.warning("No NAV data available.")
    st.stop()

# 1. Global Parameters
st.subheader("Simulation Period")
col_min, col_max = st.columns(2)
start_date = col_min.date_input("Start Date", value=pd.to_datetime("2020-01-01").date())
end_date = col_max.date_input("End Date", value=pd.to_datetime("today").date())

st.markdown("---")

# 2. Strategy Config
strategy = st.selectbox("Select Strategy", ["SIP", "Lump Sum", "Value Averaging", "SIP + Buy on Dip", "Momentum (MA Crossover)", "SIP with Stop-Loss"])

with st.expander(f"ℹ️ How **{strategy}** works", expanded=False):
    if strategy == "SIP":
        st.markdown("Invests a fixed amount periodically irrespective of market conditions. It naturally averages costs by accumulating more units when the NAV is low and fewer units when the NAV is high (Rupee Cost Averaging).")
    elif strategy == "Lump Sum":
        st.markdown("Deploys the entire investment amount strictly on the single start date. It relies purely on the asset's overall long-term market growth from that specific day forward without staggering entry points.")
    elif strategy == "Value Averaging":
        st.markdown("Calculates a calculated *Target Portfolio Value* that grows linearly each month via the defined Growth Percentage. It dynamically reacts to market phases: investing heavier cash when the actual value falls below target, and investing less — or actively selling out to cash — if your holdings overshoot the target.")
    elif strategy == "SIP + Buy on Dip":
        st.markdown("Combines standard monthly SIP cost-averaging with an aggressive tactical cash reserve overlay. It tracks the historic all-time **Highest Peak NAV**. When the market drops by the primary trigger (e.g. 5%), it automatically fires a large 'Buy on Dip' using the configured Multiplier amount.\n\nIf the market keeps falling, it fires subsequent purchases every time the NAV drops off your *last dip buy* point. A cooldown timer stops it from blowing all reserves in 3 days. The tracking system resets natively back to the 1st Dip Trigger upon rallying to a new absolute peak.")
    elif strategy == "Momentum (MA Crossover)":
        st.markdown("A pure structural trend-following algorithm that monitors algorithmic Moving Averages. It buys your entire budget when the Fast MA actively crosses *above* the Slow MA (**Golden Cross**), riding the upward momentum. It defensively stops out and liquidates the whole position to cash if the Fast MA crosses *below* the Slow MA (**Death Cross**).")
    elif strategy == "SIP with Stop-Loss":
        st.markdown("Maintains a regular monthly SIP structure but heavily shields capital using a rolling, dynamic stop-loss protocol. If the current NAV falls violently from its recent peak point, it sells 100% of the portfolio to lock in cash equivalents. It pauses all market exposure—storing regular monthly SIP installments strictly as untracked cash—until the fund rebounds safely above the Re-Entry Recovery curve, where it funnels everything back into the market.")

st.subheader(f"{strategy} Parameters")

params = {}
if strategy == "SIP":
    col1, col2 = st.columns(2)
    params["monthly_amount"] = col1.number_input("Monthly SIP Amount (₹)", value=5000, step=1000)
    params["sip_day"] = col2.number_input("SIP Day of Month", min_value=1, max_value=28, value=1, step=1)
    
elif strategy == "Lump Sum":
    params["amount"] = st.number_input("Total Investment Amount (₹)", value=100000, step=10000)

elif strategy == "Value Averaging":
    col1, col2 = st.columns(2)
    params["start_amount"] = col1.number_input("Initial Target Amount (₹)", value=10000, step=1000)
    params["monthly_target_growth"] = col2.number_input("Monthly Target Growth (%)", value=1.0, step=0.1, format="%.2f")

elif strategy == "SIP + Buy on Dip":
    col1, col2 = st.columns(2)
    params["monthly_amount"] = col1.number_input("Regular Monthly SIP Amount (₹)", value=5000, step=1000)
    params["sip_day"] = col2.number_input("SIP Day of Month", min_value=1, max_value=28, value=1, step=1)
    
    col3, col4 = st.columns(2)
    params["dip_drop_pct"] = col3.number_input("1st Dip Trigger (% drop from peak)", value=5.0, step=1.0)
    params["subsequent_dip_drop_pct"] = col4.number_input("Subsequent Trigger (% drop from prev dip buy)", value=2.0, step=1.0)
    
    col5, col6 = st.columns(2)
    params["dip_multiplier"] = col5.number_input("Dip Buy Multiplier (x SIP)", value=2.0, step=0.5)
    params["cooldown_days"] = col6.number_input("Cooldown (Days)", value=15, step=5)

elif strategy == "Momentum (MA Crossover)":
    params["amount"] = st.number_input("Total Investment Budget (₹)", value=100000, step=10000)
    col1, col2 = st.columns(2)
    params["fast_window"] = col1.number_input("Fast MA Window (Days)", value=50, step=10)
    params["slow_window"] = col2.number_input("Slow MA Window (Days)", value=200, step=10)

elif strategy == "SIP with Stop-Loss":
    col1, col2, col3 = st.columns(3)
    params["monthly_amount"] = col1.number_input("Monthly SIP Amount (₹)", value=5000, step=1000)
    params["stop_loss_pct"] = col2.number_input("Stop-Loss Drop (%)", value=20.0, step=1.0)
    params["re_entry_pct"] = col3.number_input("Re-Entry Recovery (%)", value=10.0, step=1.0)
    params["sip_day"] = st.number_input("SIP Day of Month", min_value=1, max_value=28, value=1, step=1)

# 3. Execution
if st.button("Run Simulation", type="primary"):
    with st.spinner("Running simulation..."):
        res = None
        try:
            if strategy == "SIP":
                res = sip(df_nav, start_date=start_date, end_date=end_date, **params)
            elif strategy == "Lump Sum":
                res = lump_sum(df_nav, start_date=start_date, end_date=end_date, **params)
            elif strategy == "Value Averaging":
                res = value_averaging(df_nav, start_date=start_date, end_date=end_date, **params)
            elif strategy == "SIP + Buy on Dip":
                res = sip_buy_on_dip(df_nav, start_date=start_date, end_date=end_date, **params)
            elif strategy == "Momentum (MA Crossover)":
                res = momentum_ma(df_nav, start_date=start_date, end_date=end_date, **params)
            elif strategy == "SIP with Stop-Loss":
                res = sip_with_stop_loss(df_nav, start_date=start_date, end_date=end_date, **params)
        except Exception as e:
            st.error(f"Simulation failed: {e}")

        if res:
            st.markdown("---")
            st.subheader("Strategy Results")
            met1, met2, met3 = st.columns(3)
            met1.metric("Invested Amount", f"₹{res.total_invested:,.2f}")
            met2.metric("Final Value", f"₹{res.final_value:,.2f}", f"₹{res.gain_loss:,.2f} gain")
            met3.metric("Annualized CAGR", f"{res.cagr_pct}%")

            st.subheader("NAV & Strategy Execution Timeline")
            # Slice NAV to timeframe
            df_nav_plot = df_nav[(df_nav["date"] >= pd.Timestamp(start_date)) & (df_nav["date"] <= pd.Timestamp(end_date))]
            
            fig = go.Figure()
            # Render foundational NAV Background
            fig.add_trace(go.Scatter(x=df_nav_plot["date"], y=df_nav_plot["nav"], mode="lines", name="NAV Sequence", line=dict(color="#4a90e2", width=2)))
            
            # Type classification metadata for traces
            color_map = {
                "BUY": "green", "SIP-BUY": "#2ecc71", "DIP-BUY": "#9b59b6",
                "RE-ENTRY": "yellow", "SELL": "#e74c3c", "STOP-LOSS-SELL": "red"
            }
            symbol_map = {
                "BUY": "triangle-up", "SIP-BUY": "circle", "DIP-BUY": "star",
                "RE-ENTRY": "diamond", "SELL": "triangle-down", "STOP-LOSS-SELL": "x"
            }
            
            # Map respective event dots identically onto timeline intersecting NAV
            df_txns = res.transactions.copy()
            for t_type in df_txns["type"].unique():
                t_df = df_txns[df_txns["type"] == t_type]
                hover_texts = []
                for _, row in t_df.iterrows():
                    h_text = f"Amount: ₹{row['amount']:,.2f}"
                    if "note" in row and pd.notna(row["note"]) and row["note"]:
                        h_text += f"<br>Note: {row['note']}"
                    hover_texts.append(h_text)
                    
                fig.add_trace(go.Scatter(
                    x=t_df["date"], y=t_df["nav"], mode="markers", name=t_type,
                    marker=dict(
                        color=color_map.get(t_type, "gray"),
                        symbol=symbol_map.get(t_type, "circle"),
                        size=10,
                        line=dict(color="white", width=1)
                    ),
                    hovertext=hover_texts,
                    hoverinfo="text+x+y+name"
                ))
            
            fig.update_layout(height=500, hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig, width="stretch")

            st.subheader("Transaction Log")
            df_txns.index = range(1, len(df_txns) + 1)
            st.dataframe(df_txns, width="stretch")
