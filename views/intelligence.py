from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from components.charts import style_figure
from components.ui import metric_grid, page_header, section_header
from services.intelligence import (
    canonical_receipts,
    forecast_next_week,
    ocr_metric_summary,
)
from views.common import get_bundle


def _intelligence_receipts(bundle) -> pd.DataFrame:
    """Enrich the transaction-derived canonical table with verified payment state."""
    receipts = canonical_receipts(bundle.transactions)
    if receipts.empty or bundle.receipts.empty:
        return receipts
    public = bundle.receipts.copy()
    public["receipt_id"] = public["receipt_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    payment_columns = [column for column in ["receipt_id", "final_payment_status", "current_outstanding_bhd"] if column in public]
    if len(payment_columns) == 1:
        return receipts
    receipts = receipts.merge(public[payment_columns].drop_duplicates("receipt_id"), on="receipt_id", how="left")
    if "final_payment_status" in receipts:
        receipts["payment_state"] = receipts["final_payment_status"].combine_first(receipts["payment_state"])
        receipts = receipts.drop(columns="final_payment_status")
    if "current_outstanding_bhd" in receipts:
        receipts["outstanding_balance_bhd"] = receipts["current_outstanding_bhd"].combine_first(receipts["outstanding_balance_bhd"])
        receipts = receipts.drop(columns="current_outstanding_bhd")
    return receipts


bundle = get_bundle()
receipts = _intelligence_receipts(bundle)
page_header(
    "INTELLIGENCE",
    "Exploratory signals",
    "A one-week GMV estimate and a transparent OCR benchmark.",
)
st.caption(
    "These are small-data exploratory analyses. The GMV estimate is not a seasonal or long-range forecast."
)

forecast_tab, ocr_tab = st.tabs(["Weekly GMV Forecast", "OCR Evaluation"])

with forecast_tab:
    forecast = forecast_next_week(receipts)
    section_header("Next-week GMV", "Valid receipt totals are aggregated into Monday-anchored weeks. Missing calendar weeks are never assumed to be zero sales.")
    if forecast["gap_detected"]:
        st.warning("A historical data gap was detected. Only the latest continuous weekly period is used for training.")
    if not forecast["available"]:
        st.info(forecast["warning"])
        if not forecast["weekly"].empty:
            chart = px.line(forecast["weekly"], x="week", y="gmv_bhd", markers=True, title="Observed weekly GMV")
            chart.update_layout(xaxis_title="", yaxis_title="BHD")
            st.plotly_chart(style_figure(chart), width="stretch", config={"displayModeBar": False})
    else:
        metric_grid([
            {"label": "Exploratory next week", "value": f"BHD {forecast['forecast_gmv_bhd']:,.3f}", "note": str(forecast["selected_model"])},
            {"label": "Training weeks", "value": str(forecast["training_weeks"]), "note": "Latest continuous period"},
            {"label": "Evaluation weeks", "value": str(forecast["evaluation_weeks"]), "note": "Expanding-window back-test"},
        ])
        scores = forecast["scores"].copy()
        st.dataframe(scores, hide_index=True, width="stretch", column_config={
            "mae_bhd": st.column_config.NumberColumn("MAE", format="BHD %.3f"),
            "wape": st.column_config.NumberColumn("WAPE", format="%.1%"),
        })
        observed = forecast["training"].rename(columns={"gmv_bhd": "Observed GMV"})
        next_week = pd.DataFrame({"week": [forecast["next_week"]], "Exploratory estimate": [forecast["forecast_gmv_bhd"]]})
        chart_data = observed.merge(next_week, on="week", how="outer")
        chart = px.line(chart_data, x="week", y=["Observed GMV", "Exploratory estimate"], markers=True, title="Latest continuous weekly GMV")
        chart.update_layout(xaxis_title="", yaxis_title="BHD")
        st.plotly_chart(style_figure(chart), width="stretch", config={"displayModeBar": False})
        st.caption("Selection uses the lowest expanding-window MAE across last-week value, four-week moving average, and simple exponential smoothing.")

with ocr_tab:
    summary = ocr_metric_summary(bundle.ocr_evaluation)
    section_header("Pretrained OCR benchmark", "Qwen 2.5-VL is the primary document-to-JSON extractor. PaddleOCR PP-StructureV3 is the planned second structured-document benchmark.")
    if not summary["evaluated_receipts"]:
        st.info("No held-out OCR evaluation has been exported yet. Run the fixed 60-development / 22-held-out receipt benchmark after all 82 images are available.")
        st.caption("The current evaluation template is intentionally not presented as an accuracy claim.")
    else:
        item = summary["line_item"]
        metric_grid([
            {"label": "Held-out receipts", "value": str(summary["evaluated_receipts"]), "note": "Fixed evaluation split"},
            {"label": "Field values", "value": str(summary["evaluated_field_values"]), "note": "Known ground-truth values"},
            {"label": "Valid JSON", "value": f"{summary['valid_json_rate']:.1%}", "note": "Receipt-level outputs"},
            {"label": "Line-item F1", "value": f"{item['f1']:.1%}" if pd.notna(item["f1"]) else "—", "note": "Precision / recall matching"},
        ])
        st.caption(f"Missing-field rate: {summary['missing_field_rate']:.1%} · Median processing time: {summary['median_processing_seconds']:.2f}s")
        st.dataframe(summary["metrics"], hide_index=True, width="stretch", column_config={
            "exact_accuracy": st.column_config.NumberColumn("Normalized exact match", format="%.1%"),
            "numeric_accuracy": st.column_config.NumberColumn("Numeric accuracy (±BHD 0.001)", format="%.1%"),
        })
        if not summary["errors"].empty:
            st.dataframe(summary["errors"].head(20), hide_index=True, width="stretch")
