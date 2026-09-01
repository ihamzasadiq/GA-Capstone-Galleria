from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import math
import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data" / "demo"
CAMPAIGN_WINDOW_DAYS = 14

# These offers are intentionally small, store-only incentives. Product discovery
# remains public on social media; the offer is the reason to make a walk-in visit.
WALK_IN_CAMPAIGNS: dict[str, dict[str, object]] = {
    "Inactive high spender": {
        "promotion_name": "Return voucher",
        "offer_terms": "BHD 10 off BHD 60 or more in the customer's preferred product category",
        "campaign_reason": "Bring a valuable customer back with an offer that reflects what they buy.",
        "recipient_offer_template": "BHD 10 off your next {category} purchase of BHD 60 or more",
        "minimum_spend_bhd": 60.0,
        "fixed_discount_bhd": 10.0,
        "discount_rate": 0.0,
        "default_response_rate": 0.08,
        "redemption_scope": "Preferred product category",
        "service_offer": False,
        "code_prefix": "RETURN10",
    },
    "Inactive customer": {
        "promotion_name": "Walk-back voucher",
        "offer_terms": "BHD 5 off BHD 35 or more in the customer's preferred product category",
        "campaign_reason": "Make a return visit achievable at the customer's usual spend level.",
        "recipient_offer_template": "BHD 5 off your next {category} purchase of BHD 35 or more",
        "minimum_spend_bhd": 35.0,
        "fixed_discount_bhd": 5.0,
        "discount_rate": 0.0,
        "default_response_rate": 0.05,
        "redemption_scope": "Preferred product category",
        "service_offer": False,
        "code_prefix": "BACK5",
    },
    "Active top spender": {
        "promotion_name": "Wardrobe credit",
        "offer_terms": "BHD 10 wardrobe credit on BHD 75 or more in the customer's preferred product category",
        "campaign_reason": "Thank an active high-value customer in the category they already choose.",
        "recipient_offer_template": "BHD 10 wardrobe credit on your next {category} purchase of BHD 75 or more",
        "minimum_spend_bhd": 75.0,
        "fixed_discount_bhd": 10.0,
        "discount_rate": 0.0,
        "default_response_rate": 0.10,
        "redemption_scope": "Preferred product category",
        "service_offer": False,
        "code_prefix": "WARDROBE10",
    },
    "Alteration customer": {
        "promotion_name": "Tailoring return credit",
        "offer_terms": "BHD 5 tailoring credit against one alteration service",
        "campaign_reason": "Remove the service friction already visible in the customer's history.",
        "recipient_offer_template": "BHD 5 tailoring credit against your next alteration service",
        "minimum_spend_bhd": 0.0,
        "fixed_discount_bhd": 5.0,
        "discount_rate": 0.0,
        "default_response_rate": 0.12,
        "redemption_scope": "One alteration service",
        "service_offer": True,
        "code_prefix": "TAILOR5",
    },
    "Recent or repeat customer": {
        "promotion_name": "Return credit",
        "offer_terms": "BHD 5 return credit on BHD 35 or more in the customer's preferred product category",
        "campaign_reason": "Turn recent interest or repeat behaviour into another in-store visit.",
        "recipient_offer_template": "BHD 5 return credit on your next {category} purchase of BHD 35 or more",
        "minimum_spend_bhd": 35.0,
        "fixed_discount_bhd": 5.0,
        "discount_rate": 0.0,
        "default_response_rate": 0.15,
        "redemption_scope": "Preferred product category",
        "service_offer": False,
        "code_prefix": "RETURN5",
    },
}


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
    profiles["inactive_customer"] = profiles["days_since_purchase"].ge(90)

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

    profiles["preferred_category"] = profiles["customer_id"].map(
        preferred_category_by_customer(transactions)
    ).fillna("Selected merchandise")

    profiles["marketing_consent"] = _marketing_consent_by_customer(bundle, profiles["customer_id"])
    profiles["contactable_with_consent"] = profiles["marketing_consent"].str.lower().eq("yes")
    return assign_walk_in_campaigns(profiles)


def preferred_category_by_customer(transactions: pd.DataFrame) -> pd.Series:
    """Select a customer's strongest verified merchandise category.

    Categories are ranked by recorded product-sales value. When values tie, the
    most recently purchased category wins; a final alphabetical sort keeps the
    result deterministic when dates also tie.
    """
    required = {"customer_id", "product_category", "line_total_clean"}
    if transactions.empty or not required.issubset(transactions.columns):
        return pd.Series(dtype="string")

    products = transactions.dropna(subset=["customer_id"]).copy()
    products["product_category"] = products["product_category"].fillna("Unknown").astype(str).str.strip()
    products["line_total_clean"] = pd.to_numeric(products["line_total_clean"], errors="coerce")
    excluded_categories = {"alteration", "delivery", "unknown"}
    category_key = products["product_category"].str.lower()
    valid = products["line_total_clean"].gt(0) & ~category_key.isin(excluded_categories)
    if "transaction_type" in products:
        valid &= products["transaction_type"].fillna("").astype(str).str.lower().eq("product sale")
    products = products.loc[valid].copy()
    if products.empty:
        return pd.Series(dtype="string")

    if "transaction_date" in products:
        products["transaction_date"] = pd.to_datetime(products["transaction_date"], errors="coerce")
    else:
        products["transaction_date"] = pd.NaT
    ranked = products.groupby(["customer_id", "product_category"], as_index=False).agg(
        category_sales_bhd=("line_total_clean", "sum"),
        category_last_purchase=("transaction_date", "max"),
    )
    ranked = ranked.sort_values(
        ["customer_id", "category_sales_bhd", "category_last_purchase", "product_category"],
        ascending=[True, False, False, True],
        na_position="last",
    )
    return ranked.drop_duplicates("customer_id").set_index("customer_id")["product_category"].astype("string")


def _marketing_consent_by_customer(bundle: DataBundle, customer_ids: pd.Series) -> pd.Series:
    """Use consent if supplied with future receipt or transaction imports.

    The public fixture intentionally has no contact or consent data, so unknown is
    the safe default and no customer becomes eligible for direct outreach.
    """
    consent_lookup = pd.Series(dtype="string")
    for frame in (bundle.receipts, bundle.transactions):
        consent_column = next(
            (column for column in ("marketing_consent", "consent_for_marketing") if column in frame),
            None,
        )
        if consent_column is None or "customer_id" not in frame:
            continue
        values = frame.dropna(subset=["customer_id", consent_column]).copy()
        if values.empty:
            continue
        latest = values.groupby("customer_id")[consent_column].last().astype("string")
        consent_lookup = consent_lookup.combine_first(latest)
    return customer_ids.map(consent_lookup).fillna("Unknown").astype("string")


def assign_walk_in_campaigns(profiles: pd.DataFrame) -> pd.DataFrame:
    """Assign at most one explainable store campaign to each customer profile."""
    assigned = profiles.copy()
    if assigned.empty:
        return assigned

    assigned["campaign_audience"] = pd.Series(pd.NA, index=assigned.index, dtype="string")
    audience_rules = [
        ("Inactive high spender", assigned["inactive_customer"] & assigned["top_spender"]),
        ("Inactive customer", assigned["inactive_customer"]),
        ("Active top spender", assigned["top_spender"] & ~assigned["inactive_customer"]),
        ("Alteration customer", assigned["alteration_customer"]),
        ("Recent or repeat customer", assigned["recent_customer"] | assigned["repeat_customer"]),
    ]
    for audience, matches in audience_rules:
        unassigned = assigned["campaign_audience"].isna()
        assigned.loc[unassigned & matches, "campaign_audience"] = audience

    for field in (
        "promotion_name", "offer_terms", "campaign_reason", "minimum_spend_bhd",
        "fixed_discount_bhd", "discount_rate", "default_response_rate", "code_prefix",
        "redemption_scope", "service_offer",
    ):
        assigned[field] = assigned["campaign_audience"].map(
            {audience: details[field] for audience, details in WALK_IN_CAMPAIGNS.items()}
        )
    return assigned


def campaign_dates(campaign_start: date | str | pd.Timestamp | None = None) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Timestamp(campaign_start or date.today()).normalize()
    return start, start + pd.Timedelta(days=CAMPAIGN_WINDOW_DAYS)


def promotion_code(customer_id: object, campaign_audience: str, campaign_start: date | str | pd.Timestamp) -> str:
    """Create a reproducible code for one customer and one dated campaign."""
    start, _ = campaign_dates(campaign_start)
    prefix = str(WALK_IN_CAMPAIGNS[campaign_audience]["code_prefix"])
    source = f"{customer_id}|{campaign_audience}|{start.date().isoformat()}"
    suffix = hashlib.sha256(source.encode("utf-8")).hexdigest()[:8].upper()
    return f"GLR-{prefix}-{start:%y%m%d}-{suffix}"


def campaign_recipients(
    profiles: pd.DataFrame,
    campaign_audience: str,
    campaign_start: date | str | pd.Timestamp,
) -> pd.DataFrame:
    """Return only consented recipients with store-redemption details."""
    columns = [
        "customer_id", "campaign_audience", "preferred_category", "recipient_offer", "promotion_name",
        "offer_terms", "promo_code", "campaign_start", "expires_on",
    ]
    if campaign_audience not in WALK_IN_CAMPAIGNS:
        return pd.DataFrame(columns=columns)
    selected = profiles.loc[
        profiles["campaign_audience"].eq(campaign_audience)
        & profiles["contactable_with_consent"].fillna(False)
    ].copy()
    if selected.empty:
        return pd.DataFrame(columns=columns)
    start, expiry = campaign_dates(campaign_start)
    template = str(WALK_IN_CAMPAIGNS[campaign_audience]["recipient_offer_template"])
    selected["preferred_category"] = selected["preferred_category"].fillna("Selected merchandise")
    selected["recipient_offer"] = selected["preferred_category"].map(
        lambda category: template.format(category=category)
    )
    selected["promo_code"] = selected["customer_id"].map(
        lambda customer_id: promotion_code(customer_id, campaign_audience, start)
    )
    selected["campaign_start"] = start.date()
    selected["expires_on"] = expiry.date()
    return selected[columns].sort_values("customer_id").reset_index(drop=True)


def promotion_projection(
    audience_size: int,
    response_rate: float,
    expected_order_bhd: float,
    offer_cost_per_order_bhd: float = 0.0,
    discount_rate: float = 0.0,
) -> dict[str, float]:
    """Transparent planning arithmetic; this is a scenario, not a prediction."""
    expected_orders = max(audience_size, 0) * max(response_rate, 0.0)
    potential_gmv = expected_orders * max(expected_order_bhd, 0.0)
    discount_per_order = max(offer_cost_per_order_bhd, 0.0) + (
        max(expected_order_bhd, 0.0) * max(discount_rate, 0.0)
    )
    offer_budget = expected_orders * discount_per_order
    return {
        "expected_orders": expected_orders,
        "potential_gmv_bhd": potential_gmv,
        "offer_budget_bhd": offer_budget,
        "discount_per_order_bhd": discount_per_order,
    }


def brand_coverage(transactions: pd.DataFrame) -> float:
    if transactions.empty or "brand_clean" not in transactions:
        return 0.0
    return float((~transactions["brand_clean"].fillna("Unknown").eq("Unknown")).mean())


def to_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8")
