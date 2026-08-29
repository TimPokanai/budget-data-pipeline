"""Phase 5 dashboard -- Overview page.

Replaces the source workbook's `Monthly Budget Summary` sheet: pick a
month, see planned vs. actual vs. difference per category -- the same
numbers docs/phase-3-transformation.md's verification query already
reproduces by hand. Two more pages (see dashboard/pages/) add
transaction-level drill-down and a multi-month trend view, neither of
which the sheet ever structurally supported. See docs/phase-5-dashboard.md
for the full design.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from queries import available_months, budget_actuals_for_month

st.set_page_config(page_title="Budget Overview", page_icon="💰", layout="wide")

st.title("Budget Overview")

months = available_months()
if not months:
    st.warning(
        "No budget months found in marts.fct_budget_actuals yet -- ingest a "
        "workbook and run `dbt build` before this page has anything to show."
    )
    st.stop()

selected_month = st.selectbox("Month", months, index=0)

df = budget_actuals_for_month(selected_month)

income_actual = df.loc[df["category_type"] == "income", "actual_amount"].sum()
expense_actual = df.loc[df["category_type"] == "expense", "actual_amount"].sum()
net = income_actual + expense_actual  # expenses are already negative

col1, col2, col3 = st.columns(3)
col1.metric("Income", f"${income_actual:,.2f}")
col2.metric("Expenses", f"${expense_actual:,.2f}")
col3.metric("Net", f"${net:,.2f}")

st.subheader("Planned vs. Actual by Category")
st.caption(
    "Bars show absolute magnitude for readability; the table below keeps "
    "the real signed values (positive = income, negative = expense)."
)

# Expenses are stored negative (the project's signed-amount convention --
# see PROJECT_PLAN.md). Flipped to positive magnitudes here purely for this
# chart's readability; the table below keeps the real signed values so
# nothing about the underlying data is misrepresented anywhere but here.
chart_df = df.copy()
chart_df["planned_display"] = chart_df["planned_amount"].abs()
chart_df["actual_display"] = chart_df["actual_amount"].abs()

melted = chart_df.melt(
    id_vars=["category_name"],
    value_vars=["planned_display", "actual_display"],
    var_name="type",
    value_name="amount",
)
melted["type"] = melted["type"].map(
    {"planned_display": "Planned", "actual_display": "Actual"}
)

fig = px.bar(
    melted,
    x="category_name",
    y="amount",
    color="type",
    barmode="group",
    labels={"category_name": "Category", "amount": "Amount (CAD)", "type": ""},
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Detail")
st.dataframe(
    df.style.format(
        {
            "planned_amount": "${:,.2f}",
            "actual_amount": "${:,.2f}",
            "difference_amount": "${:,.2f}",
        },
        na_rep="—",
    ),
    use_container_width=True,
    hide_index=True,
)
