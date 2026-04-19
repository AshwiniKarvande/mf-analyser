import streamlit as st
from mf_analyser.config import DEFAULT_FUNDS
from mf_analyser.data.cache import search_cached_schemes

def fund_selector(key: str = "fund_selector") -> str:
    """
    Provides a reusable fund selector sidebar component.
    Defaults to the DEFAULT_FUNDS universe.
    Returns the selected scheme code as a string.
    """
    st.sidebar.markdown("### Fund Selection")
    mode = st.sidebar.radio("Selection Mode", ["Default Funds", "Search Amfi"], key=f"mode_{key}")
    
    if mode == "Default Funds":
        fund_names = list(DEFAULT_FUNDS.keys())
        selected_name = st.sidebar.selectbox(
            "Select Fund", 
            options=fund_names,
            index=0,
            key=f"select_{key}"
        )
        code = DEFAULT_FUNDS[selected_name]["scheme_code"]
        st.sidebar.caption(f"Code: `{code}` | Category: {DEFAULT_FUNDS[selected_name]['category']}")
        return code
    else:
        query = st.sidebar.text_input("Search Fund by Name", value="Mirae Asset", key=f"search_{key}")
        if len(query) >= 3:
            results = search_cached_schemes(query, top_n=10)
            if results.empty:
                st.sidebar.warning("No funds found.")
                # fallback
                return DEFAULT_FUNDS["Mirae Asset Large Cap Fund"]["scheme_code"]
            
            # format options
            options = {f"{row['scheme_name']} ({row['scheme_code']})": str(row['scheme_code']) for _, row in results.iterrows()}
            selected_option = st.sidebar.selectbox(
                "Search Results",
                options=list(options.keys()),
                key=f"search_select_{key}"
            )
            return options[selected_option]
        else:
            st.sidebar.info("Type at least 3 characters to search.")
            return DEFAULT_FUNDS["Mirae Asset Large Cap Fund"]["scheme_code"]
