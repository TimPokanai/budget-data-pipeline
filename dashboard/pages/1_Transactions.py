"""Phase 5 dashboard -- Transactions page.

Transaction-level drill-down the source workbook's Monthly Budget Summary
sheet never offered -- that sheet only ever showed the SUMIFS total, never
the rows behind it. Reads marts.fct_transactions and marts.dim_categories
directly. See docs/phase-5-dashboard.md.
"""

from __future__ import annotations

import streamlit as st

from queries import available_months, category_names, transactions_for_month

st.set_page_config(page_title="Transactions", page_icon="🧾", layout="wide")

st.title("Transactions")

months = available_months()
if not months:
    st.warning("No transactions found yet.")
    st.stop()

col1, col2 = st.columns(2)
selected_month = col1.selectbox("Month", months, index=0)
selected_category = col2.selectbox(
    "Category", ["All categories"] + category_names(), index=0
)

df = transactions_for_month(selected_month, selected_category)

st.caption(f"{len(df)} transaction(s)")
st.dataframe(
    df.style.format({"amount": "${:,.2f}"}),
    use_container_width=True,
    hide_index=True,
)
