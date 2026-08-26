from __future__ import annotations

import pandas as pd
import streamlit as st

from components.charts import horizontal_bar
from components.ui import metric_grid, page_header, section_header
from services.data import brand_coverage, safe_number, to_csv_bytes
from views.common import get_bundle

bundle = get_bundle()
coverage = brand_coverage(bundle.transactions)
page_header("SALES", "What is selling", "See sales by product and brand. Nothing here is estimated.")
metric_grid([
    {"label": "Brand coverage", "value": f"{coverage:.0%}", "note": "Items with a confirmed brand"},
    {"label": "Products sold", "value": f"{int(pd.to_numeric(bundle.transactions['quantity'], errors='coerce').sum()):,}", "note": "Includes recorded services"},
    {"label": "Known brands", "value": f"{len(bundle.brands):,}", "note": "Confirmed names only"},
])

tab_products, tab_brands = st.tabs(["Products", "Brands"])
with tab_products:
    section_header("Top products")
    products = bundle.categories.sort_values("known_value_bhd", ascending=False).copy()
    st.plotly_chart(horizontal_bar(products, "product_category", "known_value_bhd", "Sales by product"), width="stretch", config={"displayModeBar": False})
    st.dataframe(products, hide_index=True, width="stretch", column_config={
        "product_category": "Product", "item_rows": "Lines", "units": "Units",
        "known_value_bhd": st.column_config.NumberColumn("Sales", format="BHD %.3f"),
    })
with tab_brands:
    if bundle.brands.empty:
        st.info("No brand names have been confirmed yet.")
    else:
        if coverage < .5:
            st.warning(f"Only {coverage:.0%} of items have a brand. Use this as a partial view.")
        names = sorted(bundle.brands["brand_clean"].dropna().astype(str).unique())
        selected_brand = st.selectbox("Brand", names)
        row = bundle.brands[bundle.brands["brand_clean"].eq(selected_brand)].iloc[0]
        items = bundle.transactions[bundle.transactions["brand_clean"].eq(selected_brand)].copy()
        metric_grid([
            {"label": "Sales", "value": f"BHD {safe_number(row.get('known_value_bhd')):,.3f}", "note": "Confirmed items"},
            {"label": "Units", "value": f"{safe_number(row.get('units')):,.0f}", "note": "Recorded quantity"},
            {"label": "Average price", "value": f"BHD {safe_number(row.get('average_unit_price_bhd')):,.3f}", "note": "Per unit"},
        ])
        cols = [c for c in ["transaction_date", "description_raw", "product_category", "quantity", "unit_price_bhd", "line_total_clean"] if c in items]
        statement = items[cols].copy()
        st.dataframe(statement, hide_index=True, width="stretch")
        st.download_button("Download brand sales", to_csv_bytes(statement), f"{selected_brand.lower().replace(' ', '_')}_sales.csv", "text/csv")
