import streamlit as st
import pandas as pd
from mf_analyser.config import DEFAULT_FUNDS

st.title("🏠 Overview")

st.markdown("### Default Funds Universe")
df = pd.DataFrame.from_dict(DEFAULT_FUNDS, orient='index').reset_index(names="Fund")
df.index = range(1, len(df) + 1)
st.dataframe(df, width="stretch")
