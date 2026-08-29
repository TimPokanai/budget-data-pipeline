"""Phase 5 dashboard -- Trends page.

Multi-month view across every ingested month -- something the source
workbook structurally couldn't show, since it only ever represented one
month per file (see docs/phase-1-schema-design.md's source-structure
table). Reads marts.fct_budget_actuals. See docs/phase-5-dashboard.md.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from queries import budget_actuals_all_months

st.set_page_config(page_title="Trends", page_icon="📈", layout="wide")

st.title("Trends")

df = budget_actuals_all_months()
if df.empty:
    st.warning("No budget history found yet.")
    st.stop()

st.subheader("Income vs. Expenses by Month")
st.caption(
    "Absolute magnitude per month, summed across all income or all expense "
    "categories."
)

monthly = (
    df.groupby(["budget_month", "category_type"])["actual_amount"]
    .sum()
    .reset_index()
)
monthly["actual_display"] = monthly["actual_amount"].abs()
monthly["category_type"] = monthly["category_type"].str.capitalize()

fig = px.line(
    monthly,
    x="budget_month",
    y="actual_display",
    color="category_type",
    markers=True,
    labels={
        "budget_month": "Month",
        "actual_display": "Amount (CAD)",
        "category_type": "",
    },
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Spend by Category Over Time")
st.caption(
    "Real signed values -- expenses are negative, per the project's "
    "signed-amount convention. A lower (more negative) point means more "
    "spend that month."
)

expenses = df[df["category_type"] == "expense"]
fig2 = px.line(
    expenses,
    x="budget_month",
    y="actual_amount",
    color="category_name",
    markers=True,
    labels={
        "budget_month": "Month",
        "actual_amount": "Amount (CAD)",
        "category_name": "Category",
    },
)
st.plotly_chart(fig2, use_container_width=True)
