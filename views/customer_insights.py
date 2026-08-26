from __future__ import annotations

import pandas as pd
import streamlit as st

from components.ui import metric_grid, page_header, section_header
from services.data import business_metrics, customer_profiles, promotion_projection, to_csv_bytes
from views.common import get_bundle

bundle = get_bundle()
customers = customer_profiles(bundle)
page_header("CUSTOMERS", "Who shops with you", "Find useful customer groups and plan one relevant reason to return.")
if customers.empty:
    st.info("Customer groups will appear after receipts are verified.")
    st.stop()

latest_date = customers["last_purchase"].max()
metric_grid([
    {"label": "Customers", "value": f"{customers['customer_id'].nunique():,}", "note": "Matched by customer ID"},
    {"label": "Repeat customers", "value": f"{int(customers['repeat_customer'].sum()):,}", "note": "Two or more receipts"},
    {"label": "Top spenders", "value": f"{int(customers['top_spender'].sum()):,}", "note": "Highest 20% by spend"},
    {"label": "Latest receipt", "value": latest_date.strftime("%d %b %Y"), "note": "Recency is measured from here"},
])

groups = {
    "Everyone": customers,
    "Top spenders": customers[customers["top_spender"]],
    "Recent buyers": customers[customers["recent_customer"]],
    "Repeat customers": customers[customers["repeat_customer"]],
    "Needed alterations": customers[customers["alteration_customer"]],
}
choice = st.segmented_control("Customer group", list(groups), default="Top spenders", label_visibility="collapsed")
selected = groups[choice]

ideas = {
    "Everyone": ("New arrivals weekend", "Share a focused edit of new pieces instead of a blanket discount.", 8, 0.0),
    "Top spenders": ("Private collection preview", "Invite them before the public launch and offer personal styling.", 20, 0.0),
    "Recent buyers": ("Bring-a-friend preview", "Use their recent interest to introduce one new customer.", 12, 3.0),
    "Repeat customers": ("Early collection access", "Reward loyalty with access and service, not a price cut.", 18, 0.0),
    "Needed alterations": ("Complimentary alteration", "Remove a service friction already visible in their history.", 12, 5.0),
}
promotion_name, promotion_copy, default_response, default_cost = ideas[choice]

section_header(choice, f"{len(selected)} customers match this rule.")
table_columns = ["customer_id", "receipts", "total_spend_bhd", "average_order_bhd", "last_purchase"]
table = selected[table_columns].sort_values("total_spend_bhd", ascending=False).copy()
st.dataframe(table, hide_index=True, width="stretch", column_config={
    "customer_id": "Customer", "receipts": "Receipts",
    "total_spend_bhd": st.column_config.NumberColumn("Total spend", format="BHD %.3f"),
    "average_order_bhd": st.column_config.NumberColumn("Average receipt", format="BHD %.3f"),
    "last_purchase": st.column_config.DateColumn("Last purchase", format="DD MMM YYYY"),
})

section_header("Promotion example", "Change the two assumptions to see a simple sales range.")
with st.container(border=True):
    intro, controls = st.columns([1.25, 1], gap="large")
    with intro:
        st.markdown(f"### {promotion_name}")
        st.write(promotion_copy)
        st.caption("Planning example only. Contact customers only after marketing consent is recorded.")
    with controls:
        response_rate = st.slider("Customers who buy", 1, 40, default_response, 1, format="%d%%") / 100
        selected_aov = pd.to_numeric(selected["average_order_bhd"], errors="coerce").median()
        fallback_aov = business_metrics(bundle)["aov"]
        expected_order = st.number_input(
            "Expected sale per order (BHD)", min_value=1.0,
            value=float(round(selected_aov if pd.notna(selected_aov) else fallback_aov, 3)), step=1.0,
        )

    projection = promotion_projection(len(selected), response_rate, expected_order, default_cost)
    metric_grid([
        {"label": "Customers selected", "value": f"{len(selected):,}", "note": choice},
        {"label": "Possible orders", "value": f"{projection['expected_orders']:.1f}", "note": f"At {response_rate:.0%} assumed response"},
        {"label": "Potential product sales", "value": f"BHD {projection['potential_gmv_bhd']:,.3f}", "note": "Product GMV, not Galleria income"},
        {"label": "Estimated offer cost", "value": f"BHD {projection['offer_budget_bhd']:,.3f}", "note": f"BHD {default_cost:.3f} per order"},
    ])
    rounded_orders = round(projection["expected_orders"])
    st.success(
        f"Example: invite {len(selected)} {choice.lower()}. If around {rounded_orders} buy and spend "
        f"BHD {expected_order:,.3f} each, that produces about BHD {projection['potential_gmv_bhd']:,.3f} in product sales."
    )

st.caption(
    "Because Galleria currently earns fixed rent, these product sales are not automatically Galleria revenue. "
    "The business value is stronger footfall, happier partner brands, and better renewal conversations."
)
st.download_button("Download customer list", to_csv_bytes(table), f"{choice.lower().replace(' ', '_')}.csv", "text/csv")
