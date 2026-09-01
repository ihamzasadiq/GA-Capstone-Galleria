from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from components.ui import metric_grid, page_header, section_header
from services.data import (
    WALK_IN_CAMPAIGNS,
    business_metrics,
    campaign_dates,
    campaign_recipients,
    customer_profiles,
    promotion_projection,
    to_csv_bytes,
)
from views.common import get_bundle


bundle = get_bundle()
customers = customer_profiles(bundle)
page_header(
    "CUSTOMERS",
    "Bring the right customers back in store",
    "Social media builds awareness. These short, value-led offers give selected customers a reason to walk in.",
)
if customers.empty:
    st.info("Customer groups will appear after receipts are verified.")
    st.stop()

latest_date = customers["last_purchase"].max()
eligible = customers["campaign_audience"].notna()
metric_grid([
    {"label": "Customers", "value": f"{customers['customer_id'].nunique():,}", "note": "Matched by customer ID"},
    {"label": "Campaign eligible", "value": f"{int(eligible.sum()):,}", "note": "One offer at most per customer"},
    {"label": "Contactable with consent", "value": f"{int(customers['contactable_with_consent'].sum()):,}", "note": "Eligible for direct outreach"},
    {"label": "Latest receipt", "value": latest_date.strftime("%d %b %Y"), "note": "Recency is measured from here"},
])

audiences = list(WALK_IN_CAMPAIGNS)
choice = st.segmented_control(
    "Walk-in campaign audience",
    audiences,
    default="Inactive high spender",
    label_visibility="collapsed",
)
selected = customers.loc[customers["campaign_audience"].eq(choice)].copy()
campaign = WALK_IN_CAMPAIGNS[choice]

section_header(choice, f"{len(selected)} customers receive this offer after the priority rules are applied.")
st.caption(
    "Each customer receives only their highest-priority campaign: inactive high spender, inactive customer, "
    "active top spender, alteration customer, then recent or repeat customer. Offers cannot be stacked."
)

table_columns = [
    "customer_id", "preferred_category", "receipts", "total_spend_bhd", "average_order_bhd", "last_purchase", "marketing_consent",
]
table = selected[table_columns].sort_values("total_spend_bhd", ascending=False).copy()
st.dataframe(
    table,
    hide_index=True,
    width="stretch",
    column_config={
        "customer_id": "Customer",
        "preferred_category": "Preferred category",
        "receipts": "Receipts",
        "total_spend_bhd": st.column_config.NumberColumn("Total spend", format="BHD %.3f"),
        "average_order_bhd": st.column_config.NumberColumn("Average receipt", format="BHD %.3f"),
        "last_purchase": st.column_config.DateColumn("Last purchase", format="DD MMM YYYY"),
        "marketing_consent": "Marketing consent",
    },
)

section_header("Walk-in promotion", "Set the campaign dates and planning assumptions before briefing the store team.")
with st.container(border=True):
    intro, controls = st.columns([1.25, 1], gap="large")
    with intro:
        st.markdown(f"### {campaign['promotion_name']}")
        st.write(campaign["offer_terms"])
        st.write(campaign["campaign_reason"])
        st.caption(f"Redeem against: {campaign['redemption_scope']}")
        st.caption("Store only · one-time code · not stackable with another offer")
    with controls:
        campaign_start = st.date_input("Campaign starts", value=date.today(), key=f"campaign-start-{choice}")
        _, expiry = campaign_dates(campaign_start)
        st.caption(f"Redeem in store by {expiry.strftime('%d %b %Y')} (14-day window).")
        response_rate = st.slider(
            "Customers who buy",
            1,
            40,
            int(float(campaign["default_response_rate"]) * 100),
            1,
            format="%d%%",
            key=f"response-rate-{choice}",
        ) / 100
        if bool(campaign["service_offer"]):
            service_values = pd.to_numeric(
                bundle.transactions.loc[
                    bundle.transactions["customer_id"].isin(selected["customer_id"])
                    & bundle.transactions["transaction_type"].fillna("").eq("Alteration"),
                    "line_total_clean",
                ],
                errors="coerce",
            )
            selected_value = service_values[service_values.gt(0)].median()
            fallback_value = float(campaign["fixed_discount_bhd"])
            expected_label = "Expected alteration service value (BHD)"
            value_note = "Alteration-service value before the tailoring credit"
            minimum_value = 1.0
        else:
            selected_value = pd.to_numeric(selected["average_order_bhd"], errors="coerce").median()
            fallback_value = business_metrics(bundle)["aov"]
            expected_label = "Expected sale per order (BHD)"
            value_note = "Product sales before discounts; not Galleria income"
            minimum_value = float(campaign["minimum_spend_bhd"])
        expected_order = st.number_input(
            expected_label,
            min_value=minimum_value,
            value=float(round(max(selected_value if pd.notna(selected_value) else fallback_value, minimum_value), 3)),
            step=1.0,
            key=f"expected-order-{choice}",
        )

    projection = promotion_projection(
        len(selected),
        response_rate,
        expected_order,
        float(campaign["fixed_discount_bhd"]),
        float(campaign["discount_rate"]),
    )
    metric_grid([
        {"label": "Customers selected", "value": f"{len(selected):,}", "note": choice},
        {"label": "Possible orders", "value": f"{projection['expected_orders']:.1f}", "note": f"At {response_rate:.0%} assumed response"},
        {"label": "Potential service value" if bool(campaign["service_offer"]) else "Potential product sales", "value": f"BHD {projection['potential_gmv_bhd']:,.3f}", "note": value_note},
        {"label": "Maximum discount liability", "value": f"BHD {projection['offer_budget_bhd']:,.3f}", "note": f"BHD {projection['discount_per_order_bhd']:,.3f} per assumed order"},
    ])
    st.success(
        f"Planning example: {projection['expected_orders']:.1f} customers buy at BHD {expected_order:,.3f} each. "
        f"That is BHD {projection['potential_gmv_bhd']:,.3f} in {'alteration-service value' if bool(campaign['service_offer']) else 'product sales'} before the offer."
    )

section_header("Consented recipient list", "Only customers with recorded marketing consent receive a code for direct outreach.")
recipients = campaign_recipients(customers, choice, campaign_start)
if recipients.empty:
    st.info(
        "No eligible customer has recorded marketing consent in the loaded data. Campaign recommendations remain available, "
        "but no recipient list or promo codes can be exported until consent is supplied."
    )
else:
    st.dataframe(
        recipients,
        hide_index=True,
        width="stretch",
        column_config={
            "campaign_start": st.column_config.DateColumn("Starts", format="DD MMM YYYY"),
            "expires_on": st.column_config.DateColumn("Expires", format="DD MMM YYYY"),
        },
    )
    st.download_button(
        "Download consented campaign list",
        to_csv_bytes(recipients),
        f"{choice.lower().replace(' ', '_')}_recipients.csv",
        "text/csv",
    )

st.caption(
    "These are planning scenarios, not campaign-response predictions. Galleria earns fixed rent, so product sales are not "
    "automatically Galleria revenue. Store staff/POS should retain the exported code list and record redemption results."
)
