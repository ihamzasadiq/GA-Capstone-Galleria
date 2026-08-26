from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data" / "demo"


@dataclass
class DataBundle:
    transactions: pd.DataFrame
    receipts: pd.DataFrame
    brands: pd.DataFrame
    categories: pd.DataFrame
    ocr_metrics: pd.DataFrame
    ocr_evaluation: pd.DataFrame
    source_dir: Path


def resolve_data_dir() -> Path:
    configured = os.getenv("GALLERIA_DATA_DIR")
    return Path(configured).expanduser().resolve() if configured else DEFAULT_DATA_DIR


def _read_csv(data_dir: Path, filename: str) -> pd.DataFrame:
    path = data_dir / filename
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def safe_number(value: object, default: float = 0.0) -> float:
    """Convert a scalar to float without leaking NaN into interface metrics."""
    parsed = pd.to_numeric(value, errors="coerce")
    return float(default) if pd.isna(parsed) else float(parsed)


def _normalize_transactions(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if "transaction_date" in frame:
        frame["transaction_date"] = pd.to_datetime(frame["transaction_date"], errors="coerce")
    for column in ["quantity", "unit_price_bhd", "line_total_clean", "receipt_total_bhd"]:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _normalize_receipts(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if "transaction_date" in frame:
        frame["transaction_date"] = pd.to_datetime(frame["transaction_date"], errors="coerce")
    for column in ["units", "receipt_total_clean", "amount_paid_bhd", "current_outstanding_bhd"]:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _derive_brand_summary(transactions: pd.DataFrame) -> pd.DataFrame:
    if transactions.empty or "brand_clean" not in transactions:
        return pd.DataFrame(columns=["brand_clean", "item_rows", "units", "known_value_bhd", "average_unit_price_bhd"])
    known = transactions[~transactions["brand_clean"].fillna("Unknown").eq("Unknown")]
    return known.groupby("brand_clean", as_index=False).agg(
        item_rows=("receipt_id", "size"),
        units=("quantity", "sum"),
        known_value_bhd=("line_total_clean", "sum"),
        average_unit_price_bhd=("unit_price_bhd", "mean"),
    )


def _derive_category_summary(transactions: pd.DataFrame) -> pd.DataFrame:
    if transactions.empty:
        return pd.DataFrame(columns=["product_category", "item_rows", "units", "known_value_bhd"])
    working = transactions.assign(product_category=transactions["product_category"].fillna("Unknown"))
    return working.groupby("product_category", as_index=False).agg(
        item_rows=("receipt_id", "size"),
        units=("quantity", "sum"),
        known_value_bhd=("line_total_clean", "sum"),
    ).sort_values("known_value_bhd", ascending=False)


def load_bundle(data_dir: Path | None = None) -> DataBundle:
    data_dir = Path(data_dir or resolve_data_dir())
    transactions = _normalize_transactions(_read_csv(data_dir, "transactions_clean_public.csv"))
    receipts = _normalize_receipts(_read_csv(data_dir, "receipts_clean_public.csv"))
    brands = _read_csv(data_dir, "brand_summary.csv")
    categories = _read_csv(data_dir, "category_summary.csv")
    ocr_metrics = _read_csv(data_dir, "ocr_metrics_by_field.csv")
    ocr_evaluation = _read_csv(data_dir, "ocr_evaluation_public.csv")

    brands = brands if not brands.empty else _derive_brand_summary(transactions)
    categories = categories if not categories.empty else _derive_category_summary(transactions)
    return DataBundle(
        transactions, receipts, brands, categories, ocr_metrics, ocr_evaluation, data_dir,
    )


def monthly_sales(receipts: pd.DataFrame) -> pd.DataFrame:
    if receipts.empty:
        return pd.DataFrame(columns=["month", "gmv_bhd", "receipts"])
    valid = receipts.dropna(subset=["transaction_date", "receipt_total_clean"]).copy()
    valid["month"] = valid["transaction_date"].dt.to_period("M").dt.to_timestamp()
    return valid.groupby("month", as_index=False).agg(
        gmv_bhd=("receipt_total_clean", "sum"),
        receipts=("receipt_id", "nunique"),
    )


def business_metrics(bundle: DataBundle) -> dict[str, float]:
    receipts = bundle.receipts
    transactions = bundle.transactions
    return {
        "receipts": float(receipts["receipt_id"].nunique()) if not receipts.empty else 0.0,
        "gmv": safe_number(receipts["receipt_total_clean"].sum(min_count=1)) if not receipts.empty else 0.0,
        "aov": safe_number(receipts["receipt_total_clean"].mean()) if not receipts.empty else 0.0,
        "units": safe_number(transactions["quantity"].sum(min_count=1)) if not transactions.empty else 0.0,
        "outstanding": safe_number(receipts["current_outstanding_bhd"].sum(min_count=1)) if not receipts.empty else 0.0,
        "customers": float(receipts["customer_id"].nunique()) if not receipts.empty else 0.0,
    }


def customer_profiles(bundle: DataBundle) -> pd.DataFrame:
    """Build current customer metrics from verified receipts instead of stale exports."""
    receipts = bundle.receipts.dropna(subset=["customer_id"]).copy()
    if receipts.empty:
        return pd.DataFrame()

    profiles = receipts.groupby("customer_id", as_index=False).agg(
        receipts=("receipt_id", "nunique"),
        total_spend_bhd=("receipt_total_clean", lambda values: values.sum(min_count=1)),
        average_order_bhd=("receipt_total_clean", "mean"),
        first_purchase=("transaction_date", "min"),
        last_purchase=("transaction_date", "max"),
    )
    latest_date = receipts["transaction_date"].max()
    profiles["days_since_purchase"] = (latest_date - profiles["last_purchase"]).dt.days
    profiles["repeat_customer"] = profiles["receipts"].ge(2)
    profiles["recent_customer"] = profiles["days_since_purchase"].le(30)

    ranked = profiles["total_spend_bhd"].fillna(-1).rank(method="first", ascending=False)
    top_count = max(1, math.ceil(len(profiles) * 0.20))
    profiles["top_spender"] = ranked.le(top_count)

    transactions = bundle.transactions.dropna(subset=["customer_id"]).copy()
    if not transactions.empty and "alteration_required" in transactions:
        alteration = transactions["alteration_required"].fillna("").astype(str).str.lower().isin(
            {"yes", "true", "1", "required"}
        )
        alteration_by_customer = alteration.groupby(transactions["customer_id"]).any()
        profiles["alteration_customer"] = profiles["customer_id"].map(alteration_by_customer).fillna(False)
    else:
        profiles["alteration_customer"] = False
    return profiles


def promotion_projection(
    audience_size: int,
    response_rate: float,
    expected_order_bhd: float,
    offer_cost_per_order_bhd: float = 0.0,
) -> dict[str, float]:
    """Transparent planning arithmetic; this is a scenario, not a prediction."""
    expected_orders = max(audience_size, 0) * max(response_rate, 0.0)
    potential_gmv = expected_orders * max(expected_order_bhd, 0.0)
    offer_budget = expected_orders * max(offer_cost_per_order_bhd, 0.0)
    return {
        "expected_orders": expected_orders,
        "potential_gmv_bhd": potential_gmv,
        "offer_budget_bhd": offer_budget,
    }


def brand_coverage(transactions: pd.DataFrame) -> float:
    if transactions.empty or "brand_clean" not in transactions:
        return 0.0
    return float((~transactions["brand_clean"].fillna("Unknown").eq("Unknown")).mean())


def to_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8")
