import streamlit as st

st.set_page_config(
    page_title="MF Analyser",
    page_icon="📊",
    layout="wide",
)

pages = {
    "Dashboards": [
        st.Page("pages/01_🏠_Overview.py", title="Overview"),
        st.Page("pages/02_📈_Returns_Analysis.py", title="Returns Analysis"),
        st.Page("pages/03_🤖_Strategy_Backtest.py", title="Strategy Backtest"),
        st.Page("pages/04_⚔️_Peer_Comparison.py", title="Peer Comparison"),
        st.Page("pages/05_💼_Portfolio_Holdings.py", title="Portfolio Holdings"),
        st.Page("pages/06_🏦_AUM_Trends.py", title="AUM Trends"),
    ]
}

pg = st.navigation(pages)
pg.run()
