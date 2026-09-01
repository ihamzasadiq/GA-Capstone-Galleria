from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from components.charts import horizontal_bar, line_chart
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

page_header("OVERVIEW", "Store performance", f"{greeting}. Review sales, receipt health, and product mix in one place.")
metric_grid([
    {"label": "Sales recorded", "value": f"BHD {metrics['gmv']:,.3f}", "note": "Product sales, not rental income"},
    {"label": "Receipts", "value": f"{int(metrics['receipts']):,}", "note": f"{int(metrics['units']):,} items and services"},
    {"label": "Average receipt", "value": f"BHD {metrics['aov']:,.3f}", "note": "Receipts with a known total"},
    {"label": "Still unpaid", "value": f"BHD {metrics['outstanding']:,.3f}", "note": "Balance in the receipt data"},
])

section_header("Sales at a glance", "Monthly performance is the primary signal; resolve data gaps before acting on it.")
sales_column, quality_column = st.columns([1.8, 1], gap="large", vertical_alignment="top")
with sales_column:
    if monthly.empty:
        st.info("Monthly sales will appear once receipt totals are available.", icon=":material/show_chart:")
    else:
        st.plotly_chart(line_chart(monthly, "month", "gmv_bhd", "Sales by month"), width="stretch", config={"displayModeBar": False})

with quality_column:
    with st.container(border=True):
        st.subheader("Data quality")
        st.caption("Resolve these checks before relying on the sales view for decisions.")
        if missing_totals:
            st.badge(f"{missing_totals} receipt totals missing", icon=":material/receipt_long:", color="orange")
            st.write("Those receipts are excluded from the recorded sales total.")
        if unknown_brands:
            st.badge(f"{unknown_brands} item rows need a brand", icon=":material/sell:", color="orange")
            st.write("Brand-level analysis remains partial until those items are classified.")
        if not missing_totals and not unknown_brands:
            st.badge("Data checks passed", icon=":material/check_circle:", color="green")
            st.write("Receipt totals and product brands are complete in the current dataset.")
        st.page_link("views/receipt_ocr.py", label="Review receipt data", icon=":material/receipt_long:", width="stretch")

if not bundle.categories.empty:
    section_header("Product mix", "Five leading categories are shown individually; the rest are kept together for a clean comparison.")
    categories = bundle.categories.sort_values("known_value_bhd", ascending=False).copy()
    top_categories = categories.head(5)
    remaining_sales = categories.iloc[5:]["known_value_bhd"].sum()
    if remaining_sales > 0:
        chart_categories = pd.concat([
            pd.DataFrame({"product_category": ["Other categories"], "known_value_bhd": [remaining_sales]}),
            top_categories.iloc[::-1],
        ], ignore_index=True)
    else:
        chart_categories = top_categories.iloc[::-1]
    st.plotly_chart(
        horizontal_bar(
            chart_categories,
            "product_category",
            "known_value_bhd",
            "Sales by product category",
            sort_by_value=False,
        ),
        width="stretch",
        config={"displayModeBar": False},
    )
    st.page_link("views/brand_performance.py", label="Explore product and brand sales", icon=":material/bar_chart:", width="content")
