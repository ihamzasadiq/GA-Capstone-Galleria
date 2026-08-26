from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from components.charts import donut_chart, line_chart
from components.ui import metric_grid, page_header, section_header
from services.data import business_metrics, monthly_sales
from views.common import get_bundle

bundle = get_bundle()
metrics = business_metrics(bundle)
monthly = monthly_sales(bundle.receipts)
missing_totals = int(bundle.receipts["receipt_total_clean"].isna().sum())
unknown_brands = int(bundle.transactions["brand_clean"].fillna("Unknown").eq("Unknown").sum())
hour = datetime.now(ZoneInfo("Asia/Bahrain")).hour
greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"

page_header("STORE SUMMARY", greeting, "Here is what is recorded in Galleria so far.")
metric_grid([
    {"label": "Sales recorded", "value": f"BHD {metrics['gmv']:,.3f}", "note": "Product sales, not rental income"},
    {"label": "Receipts", "value": f"{int(metrics['receipts']):,}", "note": f"{int(metrics['units']):,} items and services"},
    {"label": "Average receipt", "value": f"BHD {metrics['aov']:,.3f}", "note": "Receipts with a known total"},
    {"label": "Still unpaid", "value": f"BHD {metrics['outstanding']:,.3f}", "note": "Balance in the receipt data"},
])

section_header("Sales at a glance")
left, right = st.columns([1.55, 1], gap="large")
with left:
    if not monthly.empty:
        st.plotly_chart(line_chart(monthly, "month", "gmv_bhd", "Sales by month"), width="stretch", config={"displayModeBar": False})
with right:
    if not bundle.categories.empty:
        st.plotly_chart(donut_chart(bundle.categories.head(6), "product_category", "known_value_bhd", "What sold"), width="stretch", config={"displayModeBar": False})

section_header("Needs attention")
if missing_totals:
    st.warning(f"{missing_totals} receipts are missing a total")
if unknown_brands:
    st.warning(f"{unknown_brands} item rows do not have a confirmed brand")
if not missing_totals and not unknown_brands:
    st.success("Everything recorded so far is complete.")

st.page_link("views/receipt_ocr.py", label="Add a receipt", icon=":material/add:")
