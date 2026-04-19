import streamlit as st
from dashboard.components import fund_selector
from mf_analyser.analysis.comparison import discover_peers, compare_returns
from mf_analyser.config import FUND_CODE_TO_NAME

st.title("⚔️ Peer Comparison")
scheme_code = fund_selector()
fund_name = FUND_CODE_TO_NAME.get(str(scheme_code), f"Scheme {scheme_code}")

st.header(f"Comparing: {fund_name}")

with st.spinner("Discovering peers and computing comparative performance..."):
    peers = discover_peers(scheme_code, limit=5)
    
    if not peers:
        st.warning("Could not automatically discover peers for this category.")
    else:
        peer_codes = [str(scheme_code)] + [str(p[0]) for p in peers]
        df_comp = compare_returns(peer_codes)
        
        if not df_comp.empty:
            code_to_name = {str(scheme_code): fund_name}
            for p in peers:
                code_to_name[str(p[0])] = str(p[1])
                
            df_comp.insert(0, "Fund Name", df_comp["scheme_code"].map(code_to_name))
            df_comp = df_comp.drop(columns=["scheme_name", "scheme_code"], errors="ignore")
            df_comp.index = range(1, len(df_comp) + 1)
            
            st.subheader("Performance vs Category Rivals")
            st.dataframe(df_comp, width="stretch")
            
            import plotly.express as px
            period_cols = [c for c in df_comp.columns if c.endswith("_cagr_pct")]
            if period_cols:
                # Rename the columns to strip the unneeded suffix inside the plot
                rename_map = {c: c.replace("_cagr_pct", "") for c in period_cols}
                df_plot = df_comp.rename(columns=rename_map)
                clean_cols = list(rename_map.values())
                
                # Reshape data to put Periods on the X axis and Funds as the grouped bars
                df_melted = df_plot.melt(id_vars=["Fund Name"], value_vars=clean_cols, var_name="Period", value_name="CAGR (%)")
                
                fig = px.bar(
                    df_melted, 
                    x="Period", 
                    y="CAGR (%)", 
                    color="Fund Name",
                    barmode="group",
                    title="CAGR (%) Comparison Across Periods"
                )
                st.plotly_chart(fig, width="stretch")
