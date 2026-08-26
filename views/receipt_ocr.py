from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from components.charts import horizontal_bar
from components.ui import callout, empty_state, metric_grid, page_header, section_header, stepper
from services.ocr import (
    DEFAULT_PROFILE,
    OCR_PROFILES,
    append_verified_payload,
    build_verified_payload,
    demo_prediction,
    extract_receipt,
    extraction_error_message,
    items_frame,
    validation_warnings,
)
from views.common import get_bundle


ROOT = Path(__file__).resolve().parents[1]
bundle = get_bundle()


def get_setting(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, os.getenv(name, default)))
    except (FileNotFoundError, KeyError):
        return os.getenv(name, default)


def parsed_date(value) -> date:
    parsed = pd.to_datetime(value, errors="coerce")
    return date.today() if pd.isna(parsed) else parsed.date()


page_header("RECEIPTS", "Add a receipt", "Upload a photo, check what was read, then save it.")

with st.expander("OCR accuracy test", expanded=False):
    if bundle.ocr_metrics.empty:
        empty_state(
            "Accuracy appears after a real benchmark run",
            "Run the notebook's OCR extraction and evaluation sections. The app will automatically load ocr_metrics_by_field.csv from the dashboard output folder; no unmeasured score is invented here.",
            "%",
        )
    else:
        metrics = bundle.ocr_metrics.copy()
        metrics["evaluated_values"] = pd.to_numeric(metrics["evaluated_values"], errors="coerce").fillna(0)
        metrics["exact_accuracy"] = pd.to_numeric(metrics["exact_accuracy"], errors="coerce")
        usable = metrics.dropna(subset=["exact_accuracy"]).copy()
        evaluated_values = int(usable["evaluated_values"].sum())
        weighted_correct = (usable["exact_accuracy"] * usable["evaluated_values"]).sum()
        overall_accuracy = weighted_correct / evaluated_values if evaluated_values else 0.0
        evaluated_receipts = (
            bundle.ocr_evaluation["image_key"].nunique()
            if not bundle.ocr_evaluation.empty and "image_key" in bundle.ocr_evaluation else 0
        )
        metric_grid([
            {"label": "Overall field accuracy", "value": f"{overall_accuracy:.1%}", "note": "Weighted exact-match accuracy"},
            {"label": "Evaluated values", "value": f"{evaluated_values:,}", "note": "Missing ground truth excluded"},
            {"label": "Evaluated receipts", "value": f"{evaluated_receipts:,}", "note": "Public benchmark comparison"},
            {"label": "Fields measured", "value": f"{usable['field'].nunique():,}", "note": "Receipt and item fields"},
        ])
        chart_data = usable.copy()
        chart_data["weighted_correct"] = chart_data["exact_accuracy"] * chart_data["evaluated_values"]
        chart_data = chart_data.groupby("field", as_index=False).agg(
            evaluated_values=("evaluated_values", "sum"),
            weighted_correct=("weighted_correct", "sum"),
        )
        chart_data["accuracy_percent"] = (
            chart_data["weighted_correct"] / chart_data["evaluated_values"].replace(0, pd.NA) * 100
        )
        st.plotly_chart(
            horizontal_bar(chart_data, "field", "accuracy_percent", "Exact OCR accuracy by field"),
            width="stretch",
            config={"displayModeBar": False},
        )

upload_tab, camera_tab = st.tabs(["Upload receipt", "Use camera"])
with upload_tab:
    uploaded_file = st.file_uploader(
        "Choose a receipt image",
        type=["jpg", "jpeg", "png", "webp"],
        help="Images are processed in memory and are not included in public dashboard exports.",
    )
with camera_tab:
    camera_file = st.camera_input("Photograph a receipt")

source_file = uploaded_file or camera_file
image_bytes = source_file.getvalue() if source_file else None
source_name = source_file.name if source_file else "demo-receipt.jpg"

token = get_setting("HF_TOKEN")
configured_profile = get_setting("HF_OCR_PROFILE", DEFAULT_PROFILE)
default_profile = configured_profile if configured_profile in OCR_PROFILES else DEFAULT_PROFILE

with st.expander("Advanced OCR settings", expanded=False):
    profile_ids = list(OCR_PROFILES)
    selected_profile = st.selectbox(
        "Extraction profile",
        profile_ids,
        index=profile_ids.index(default_profile),
        format_func=lambda profile_id: OCR_PROFILES[profile_id]["label"],
    )
    selected_config = OCR_PROFILES[selected_profile]
    st.caption(
        f"{selected_config['note']}  ·  Model: {selected_config['model']}  ·  "
        f"Provider: {selected_config['provider']}"
    )

model = str(selected_config["model"])
provider = str(selected_config["provider"])

action_one, action_two, action_space = st.columns([1, 1, 3])
with action_one:
    extract_clicked = st.button(
        "Extract with AI",
        type="primary",
        width="stretch",
        disabled=image_bytes is None,
    )
with action_two:
    demo_clicked = st.button("Try demo result", width="stretch")

if extract_clicked:
    if not token:
        st.error("HF_TOKEN is not configured. Add it to Streamlit secrets before using live OCR.")
    else:
        with st.spinner("Reading receipt and structuring the fields…"):
            try:
                st.session_state["ocr_prediction"] = extract_receipt(
                    image_bytes=image_bytes,
                    token=token,
                    model=model,
                    provider=provider,
                )
                st.session_state["ocr_source_name"] = source_name
                st.session_state["ocr_config_used"] = {
                    "profile": selected_profile,
                    "model": model,
                    "provider": provider,
                    "mode": "live",
                }
            except Exception as error:
                st.error(extraction_error_message(error, model, provider))

if demo_clicked:
    st.session_state["ocr_prediction"] = demo_prediction()
    st.session_state["ocr_source_name"] = "demo-receipt.jpg"
    st.session_state["ocr_config_used"] = {"profile": "demo", "mode": "demo"}

prediction = st.session_state.get("ocr_prediction")

if not token:
    callout(
        "Live receipt reading is not connected",
        "Add your Hugging Face token in Streamlit secrets. You can still try the sample receipt below.",
    )

if prediction:
    section_header("Check the receipt", "Fix anything that was read incorrectly before saving.")
    image_col, review_col = st.columns([0.85, 1.5], gap="large")
    with image_col:
        if image_bytes:
            st.image(image_bytes, caption=source_name, width="stretch")
        else:
            empty_state("Demo extraction", "Attach a real image to compare the draft with the original receipt.", "▣")

        warnings = validation_warnings(prediction)
        if warnings:
            st.markdown("#### Review flags")
            for warning in warnings:
                st.warning(warning)
        else:
            st.success("No automatic validation warnings found.")

    with review_col:
        with st.form("receipt_review_form", clear_on_submit=False):
            first, second = st.columns(2)
            with first:
                receipt_id = st.text_input("Receipt number", value=str(prediction.get("receipt_id") or ""))
                transaction_date = st.date_input("Transaction date", value=parsed_date(prediction.get("transaction_date")))
                payment_status = st.selectbox(
                    "Payment status",
                    ["Paid", "Partially Paid", "Unpaid", "Unknown"],
                    index=["Paid", "Partially Paid", "Unpaid", "Unknown"].index(
                        prediction.get("payment_status") if prediction.get("payment_status") in {"Paid", "Partially Paid", "Unpaid"} else "Unknown"
                    ),
                )
            with second:
                receipt_total = st.number_input(
                    "Receipt total (BHD)", min_value=0.0,
                    value=float(prediction.get("receipt_total_bhd") or 0.0), step=0.5, format="%.3f",
                )
                advance_paid = st.number_input(
                    "Advance paid (BHD)", min_value=0.0,
                    value=float(prediction.get("advance_paid_bhd") or 0.0), step=0.5, format="%.3f",
                )
                balance = st.number_input(
                    "Balance (BHD)", min_value=0.0,
                    value=float(prediction.get("balance_bhd") or 0.0), step=0.5, format="%.3f",
                )

            st.markdown("#### Customer details · private")
            customer_one, customer_two = st.columns(2)
            with customer_one:
                customer_name = st.text_input("Customer name", value=str(prediction.get("customer_name") or ""))
            with customer_two:
                phone_number = st.text_input("Phone number", value=str(prediction.get("phone_number") or ""))

            st.markdown("#### Receipt lines")
            edited_items = st.data_editor(
                items_frame(prediction),
                num_rows="dynamic",
                width="stretch",
                hide_index=True,
                column_config={
                    "description_raw": st.column_config.TextColumn("Description", required=True),
                    "brand_raw": st.column_config.TextColumn("Brand"),
                    "product_category": st.column_config.TextColumn("Category"),
                    "quantity": st.column_config.NumberColumn("Qty", min_value=0, step=1),
                    "unit_price_bhd": st.column_config.NumberColumn("Unit price", format="BHD %.3f"),
                    "line_total_bhd": st.column_config.NumberColumn("Line total", format="BHD %.3f"),
                },
            )
            verified = st.form_submit_button("Save verified receipt", type="primary", width="stretch")

        if verified:
            receipt_fields = {
                "receipt_id": receipt_id,
                "transaction_date": transaction_date.isoformat(),
                "receipt_total_bhd": receipt_total,
                "advance_paid_bhd": advance_paid,
                "balance_bhd": balance,
                "payment_status": payment_status,
            }
            customer_fields = {"customer_name": customer_name, "phone_number": phone_number}
            payload = build_verified_payload(
                receipt_fields,
                customer_fields,
                edited_items,
                st.session_state.get("ocr_source_name", source_name),
                ocr_metadata=st.session_state.get("ocr_config_used"),
            )
            append_verified_payload(payload, ROOT / "data" / "private" / "verified_receipts.jsonl")
            st.session_state["last_verified_payload"] = payload
            st.success("Receipt verified and saved to the private review file.")

    if st.session_state.get("last_verified_payload"):
        st.download_button(
            "Download latest verified receipt",
            data=json.dumps(st.session_state["last_verified_payload"], indent=2, default=str),
            file_name="verified_galleria_receipt.json",
            mime="application/json",
        )
else:
    section_header("Start with one receipt", "The review workflow remains visible and understandable at every step.")
    empty_state(
        "Upload or photograph a receipt",
        "The scanner extracts receipt details, customer information, line items, payment status, brands, and alterations. Nothing enters the analytics until a person verifies it.",
        "▣",
    )
