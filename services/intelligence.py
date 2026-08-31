"""Small-sample analytics used by the Intelligence dashboard.

The functions in this module deliberately favour inspectable baselines over
high-capacity models.  They return data frames and plain dictionaries so the
notebook, tests, and Streamlit view use exactly the same calculations.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


PRIVATE_COLUMNS = {
    "customer_name", "phone", "phone_number", "mobile", "email", "address",
    "image_path", "image", "raw_image", "image_bytes", "image_name", "source_filename",
    "raw_prediction", "prediction",
}
NUMERIC_OCR_FIELDS = {
    "quantity", "unit_price_bhd", "line_total_bhd", "receipt_total_bhd",
    "advance_paid_bhd", "balance_bhd",
}


def canonical_image_key(value: object) -> str | None:
    """Normalize image names such as ``receipt-001.JPG`` to ``receipt-1``."""
    if value is None or pd.isna(value):
        return None
    stem = Path(str(value).strip()).stem.lower()
    if not stem:
        return None
    numbers = re.findall(r"\d+", stem)
    prefix = re.sub(r"\d+", "", stem)
    prefix = re.sub(r"[^a-z0-9]+", "-", prefix).strip("-")
    if numbers:
        return f"{prefix or 'receipt'}-{int(numbers[-1])}"
    return re.sub(r"[^a-z0-9]+", "-", stem).strip("-") or None


def assert_public_export(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy only when an export does not expose direct identifiers."""
    exposed = PRIVATE_COLUMNS.intersection(column.lower() for column in frame.columns)
    if exposed:
        raise ValueError(f"Public export contains private columns: {sorted(exposed)}")
    return frame.copy()


def _first_non_null(values: pd.Series) -> Any:
    values = values.dropna()
    return values.iloc[0] if not values.empty else np.nan


def _complete_line_total(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce")
    return float(numeric.sum()) if numeric.notna().all() and len(numeric) else np.nan


def canonical_receipts(transactions: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate transaction lines into a receipt-level, quality-aware table.

    An explicit receipt total wins over derived item totals.  Missing dates and
    totals are intentionally retained with flags; downstream models decide
    whether a row is eligible rather than silently filling a value.
    """
    columns = [
        "receipt_id", "transaction_date", "customer_id", "receipt_total_clean",
        "receipt_total_source", "units", "line_count", "product_mix", "alteration_mix",
        "payment_state", "outstanding_balance_bhd", "missing_date", "missing_total",
        "duplicate_line_count",
    ]
    if transactions.empty or "receipt_id" not in transactions:
        return pd.DataFrame(columns=columns)

    working = transactions.copy()
    working["receipt_id"] = working["receipt_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    working = working[working["receipt_id"].ne("") & working["receipt_id"].ne("nan")].copy()
    if working.empty:
        return pd.DataFrame(columns=columns)
    for name in ("transaction_date",):
        if name in working:
            working[name] = pd.to_datetime(working[name], errors="coerce")
    for name in ("receipt_total_bhd", "receipt_total_clean", "line_total_clean", "quantity", "current_outstanding_bhd"):
        if name in working:
            working[name] = pd.to_numeric(working[name], errors="coerce")

    has_line_numbers = "line_number" in working
    line_key = ["receipt_id", "line_number"] if has_line_numbers else ["receipt_id"]
    duplicated = working.duplicated(line_key, keep=False) if has_line_numbers else pd.Series(False, index=working.index)
    working["_duplicate_line"] = duplicated
    working["_duplicate_line_count"] = working.groupby("receipt_id")["_duplicate_line"].transform("sum")
    # A repeated receipt-line is an import duplicate, not a second item.  Keep
    # its quality flag while preventing it from inflating derived totals/units.
    if has_line_numbers:
        working = working.drop_duplicates(line_key, keep="first")
    records: list[dict[str, Any]] = []
    for receipt_id, group in working.groupby("receipt_id", sort=True, dropna=False):
        dates = group.get("transaction_date", pd.Series(dtype="datetime64[ns]"))
        explicit = group.get("receipt_total_clean", group.get("receipt_total_bhd", pd.Series(dtype=float)))
        explicit = pd.to_numeric(explicit, errors="coerce")
        if explicit.notna().any():
            total, source = float(explicit.dropna().iloc[0]), "Receipt"
        else:
            derived = _complete_line_total(group.get("line_total_clean", pd.Series(dtype=float)))
            total, source = (derived, "Derived from complete item lines") if pd.notna(derived) else (np.nan, "Missing")
        product_values = group.get("product_category", pd.Series(dtype=object)).dropna().astype(str)
        product_values = sorted({value.strip() for value in product_values if value.strip() and value.strip().lower() != "unknown"})
        alteration_values = group.get("alteration_required", pd.Series(dtype=object)).fillna("").astype(str).str.lower()
        transaction_type = group.get("transaction_type", pd.Series(dtype=object)).fillna("").astype(str).str.lower()
        has_alteration = alteration_values.isin({"yes", "true", "1", "required"}).any() or transaction_type.str.contains("alteration").any()
        payment = group.get("final_payment_status", group.get("payment_status", pd.Series(dtype=object)))
        outstanding = group.get("current_outstanding_bhd", pd.Series(dtype=float))
        if outstanding.empty and "balance_bhd" in group:
            outstanding = group["balance_bhd"]
        records.append({
            "receipt_id": receipt_id,
            "transaction_date": dates.min() if not dates.empty else pd.NaT,
            "customer_id": _first_non_null(group.get("customer_id", pd.Series(dtype=object))),
            "receipt_total_clean": total,
            "receipt_total_source": source,
            "units": pd.to_numeric(group.get("quantity", pd.Series(dtype=float)), errors="coerce").sum(min_count=1),
            "line_count": int(len(group)),
            "product_mix": " | ".join(product_values) or "Unknown",
            "alteration_mix": "Alteration" if has_alteration else "No alteration",
            "payment_state": _first_non_null(payment),
            "outstanding_balance_bhd": pd.to_numeric(outstanding, errors="coerce").max() if not outstanding.empty else np.nan,
            "missing_date": bool(dates.isna().all()) if not dates.empty else True,
            "missing_total": bool(pd.isna(total)),
            "duplicate_line_count": int(group["_duplicate_line_count"].iloc[0]),
        })
    return pd.DataFrame(records, columns=columns)


def rfm_summary(receipts: pd.DataFrame) -> pd.DataFrame:
    """Create an interpretable customer RFM table without inferring loyalty."""
    required = {"customer_id", "receipt_id", "transaction_date", "receipt_total_clean"}
    if receipts.empty or not required.issubset(receipts.columns):
        return pd.DataFrame(columns=["customer_id", "recency_days", "frequency", "monetary_bhd", "rfm_note"])
    usable = receipts.dropna(subset=["customer_id", "transaction_date", "receipt_total_clean"]).copy()
    if usable.empty:
        return pd.DataFrame(columns=["customer_id", "recency_days", "frequency", "monetary_bhd", "rfm_note"])
    latest = usable["transaction_date"].max()
    result = usable.groupby("customer_id", as_index=False).agg(
        frequency=("receipt_id", "nunique"), monetary_bhd=("receipt_total_clean", "sum"), last_purchase=("transaction_date", "max"),
    )
    result["recency_days"] = (latest - result["last_purchase"]).dt.days
    result["rfm_note"] = np.where(
        result["frequency"].ge(2), "Repeat evidence recorded", "One recorded receipt; repeat evidence is limited",
    )
    return result.sort_values(["monetary_bhd", "customer_id"], ascending=[False, True]).reset_index(drop=True)


def purchase_pattern_features(receipts: pd.DataFrame) -> pd.DataFrame:
    """Create explainable receipt features for exploratory purchase patterns."""
    required = {"receipt_id", "receipt_total_clean", "units", "line_count"}
    if receipts.empty or not required.issubset(receipts.columns):
        return pd.DataFrame()
    frame = receipts.dropna(subset=["receipt_total_clean"]).copy()
    if frame.empty:
        return pd.DataFrame()
    output = frame[["receipt_id", "receipt_total_clean", "units", "line_count"]].copy()
    output["units"] = pd.to_numeric(output["units"], errors="coerce").fillna(0)
    output["line_count"] = pd.to_numeric(output["line_count"], errors="coerce").fillna(0)
    outstanding = frame["outstanding_balance_bhd"] if "outstanding_balance_bhd" in frame else pd.Series(0, index=frame.index)
    alterations = frame["alteration_mix"] if "alteration_mix" in frame else pd.Series("", index=frame.index)
    categories = frame["product_mix"] if "product_mix" in frame else pd.Series("Unknown", index=frame.index)
    payments = frame["payment_state"] if "payment_state" in frame else pd.Series("Unknown", index=frame.index)
    output["outstanding_balance_bhd"] = pd.to_numeric(outstanding, errors="coerce").fillna(0).to_numpy()
    output["has_alteration"] = alterations.astype(str).eq("Alteration").astype(int).to_numpy()
    categories = categories.fillna("Unknown").astype(str)
    payments = payments.fillna("Unknown").astype(str)
    category_dummies = pd.get_dummies(categories, prefix="product", dtype=int)
    payment_dummies = pd.get_dummies(payments, prefix="payment", dtype=int)
    return pd.concat([output.reset_index(drop=True), category_dummies.reset_index(drop=True), payment_dummies.reset_index(drop=True)], axis=1)


def cluster_purchase_patterns(receipts: pd.DataFrame, random_state: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select 2–6 K-Means groups by silhouette score when data permits."""
    features = purchase_pattern_features(receipts)
    empty_scores = pd.DataFrame(columns=["clusters", "silhouette_score"])
    if len(features) < 3:
        return pd.DataFrame(), empty_scores
    identifiers = features[["receipt_id"]].copy()
    matrix = features.drop(columns="receipt_id").astype(float)
    scaled = StandardScaler().fit_transform(matrix)
    candidates = range(2, min(6, len(features) - 1) + 1)
    scores: list[dict[str, float]] = []
    models: dict[int, KMeans] = {}
    for count in candidates:
        model = KMeans(n_clusters=count, random_state=random_state, n_init=20)
        labels = model.fit_predict(scaled)
        if len(set(labels)) > 1:
            scores.append({"clusters": count, "silhouette_score": float(silhouette_score(scaled, labels))})
            models[count] = model
    score_frame = pd.DataFrame(scores, columns=["clusters", "silhouette_score"])
    if score_frame.empty:
        return pd.DataFrame(), score_frame
    best_count = int(score_frame.sort_values(["silhouette_score", "clusters"], ascending=[False, True]).iloc[0]["clusters"])
    labels = models[best_count].predict(scaled)
    labelled = receipts.merge(identifiers.assign(pattern_cluster=labels), on="receipt_id", how="inner")
    profile = labelled.groupby("pattern_cluster", as_index=False).agg(
        receipt_count=("receipt_id", "nunique"),
        median_gmv_bhd=("receipt_total_clean", "median"),
        median_units=("units", "median"),
        median_line_count=("line_count", "median"),
        median_outstanding_bhd=("outstanding_balance_bhd", "median"),
    )
    overall_gmv = profile["median_gmv_bhd"].median()
    overall_units = profile["median_units"].median()
    profile["pattern_label"] = [
        ("Higher-value" if row.median_gmv_bhd >= overall_gmv else "Lower-value")
        + (" multi-item" if row.median_units >= overall_units else " focused")
        + " purchase"
        for row in profile.itertuples()
    ]
    return labelled.merge(profile[["pattern_cluster", "pattern_label"]], on="pattern_cluster", how="left"), score_frame


def weekly_gmv(receipts: pd.DataFrame) -> pd.DataFrame:
    """Aggregate valid receipts into Monday-anchored weeks without inventing zeros."""
    if receipts.empty or not {"transaction_date", "receipt_total_clean"}.issubset(receipts.columns):
        return pd.DataFrame(columns=["week", "gmv_bhd"])
    valid = receipts.dropna(subset=["transaction_date", "receipt_total_clean"]).copy()
    if valid.empty:
        return pd.DataFrame(columns=["week", "gmv_bhd"])
    valid["week"] = valid["transaction_date"].dt.normalize() - pd.to_timedelta(valid["transaction_date"].dt.weekday, unit="D")
    return valid.groupby("week", as_index=False)["receipt_total_clean"].sum().rename(columns={"receipt_total_clean": "gmv_bhd"}).sort_values("week").reset_index(drop=True)


def latest_continuous_weeks(weekly: pd.DataFrame) -> pd.DataFrame:
    """Return the most recent contiguous run of observed calendar weeks."""
    if weekly.empty:
        return weekly.copy()
    data = weekly.sort_values("week").reset_index(drop=True)
    breaks = data["week"].diff().dt.days.ne(7)
    breaks.iloc[0] = True
    return data.loc[breaks.cumsum().eq(breaks.cumsum().iloc[-1])].reset_index(drop=True)


def _ses_forecast(values: Iterable[float], alpha: float = 0.3) -> float:
    iterator = iter(values)
    level = float(next(iterator))
    for value in iterator:
        level = alpha * float(value) + (1 - alpha) * level
    return level


def forecast_next_week(receipts: pd.DataFrame, min_weeks: int = 8) -> dict[str, Any]:
    """Evaluate three transparent one-week baselines using expanding windows."""
    weekly = weekly_gmv(receipts)
    continuous = latest_continuous_weeks(weekly)
    gap_detected = len(continuous) < len(weekly)
    base: dict[str, Any] = {
        "available": False, "weekly": weekly, "training": continuous, "gap_detected": gap_detected,
        "warning": "A gap in observed weeks was excluded; no zero-sales weeks were invented.",
        "scores": pd.DataFrame(columns=["model", "mae_bhd", "wape", "evaluation_weeks"]),
    }
    if len(continuous) < min_weeks:
        base["warning"] = f"Forecast unavailable: {len(continuous)} continuous valid weeks are available; at least {min_weeks} are required."
        return base
    values = continuous["gmv_bhd"].to_numpy(dtype=float)
    predictions = {"Last-week value": [], "Four-week moving average": [], "Simple exponential smoothing": []}
    actuals: list[float] = []
    for index in range(4, len(values)):
        train = values[:index]
        actuals.append(float(values[index]))
        predictions["Last-week value"].append(float(train[-1]))
        predictions["Four-week moving average"].append(float(train[-4:].mean()))
        predictions["Simple exponential smoothing"].append(_ses_forecast(train))
    if not actuals:
        base["warning"] = "Forecast unavailable: not enough observations for an expanding-window back-test."
        return base
    rows = []
    actual = np.asarray(actuals)
    for name, values_pred in predictions.items():
        error = np.abs(actual - np.asarray(values_pred))
        rows.append({"model": name, "mae_bhd": float(error.mean()), "wape": float(error.sum() / np.abs(actual).sum()) if np.abs(actual).sum() else np.nan, "evaluation_weeks": len(actual)})
    scores = pd.DataFrame(rows).sort_values(["mae_bhd", "model"]).reset_index(drop=True)
    selected = scores.iloc[0]["model"]
    next_value = {
        "Last-week value": values[-1],
        "Four-week moving average": values[-4:].mean(),
        "Simple exponential smoothing": _ses_forecast(values),
    }[selected]
    base.update({
        "available": True, "scores": scores, "selected_model": selected,
        "forecast_gmv_bhd": max(float(next_value), 0.0), "next_week": continuous["week"].max() + pd.Timedelta(days=7),
        "training_weeks": len(continuous), "evaluation_weeks": len(actual),
    })
    return base


def _normalise_value(value: object, field: str) -> object:
    if value is None or pd.isna(value) or str(value).strip().lower() in {"", "nan", "none", "null", "unknown", "n/a"}:
        return None
    if field in NUMERIC_OCR_FIELDS:
        parsed = pd.to_numeric(value, errors="coerce")
        return None if pd.isna(parsed) else float(parsed)
    if "date" in field:
        parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
        return None if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")
    return re.sub(r"\s+", " ", str(value).strip().lower())


def ocr_metric_summary(evaluation: pd.DataFrame) -> dict[str, Any]:
    """Summarise de-identified, field-level OCR evaluation exports."""
    empty = pd.DataFrame(columns=["field", "evaluated_values", "exact_accuracy", "numeric_accuracy"])
    if evaluation.empty:
        return {"evaluated_receipts": 0, "evaluated_field_values": 0, "valid_json_rate": np.nan, "missing_field_rate": np.nan, "metrics": empty, "line_item": {"precision": np.nan, "recall": np.nan, "f1": np.nan}, "median_processing_seconds": np.nan, "errors": pd.DataFrame()}
    frame = assert_public_export(evaluation)
    if "image_key" in frame:
        frame["image_key"] = frame["image_key"].map(canonical_image_key)
    if "split" in frame:
        frame = frame[frame["split"].astype(str).str.lower().isin({"holdout", "holdout test", "evaluation", "test"})].copy()
    if frame.empty:
        return {"evaluated_receipts": 0, "evaluated_field_values": 0, "valid_json_rate": np.nan, "missing_field_rate": np.nan, "metrics": empty, "line_item": {"precision": np.nan, "recall": np.nan, "f1": np.nan}, "median_processing_seconds": np.nan, "errors": pd.DataFrame()}
    actual = frame.get("actual", pd.Series(index=frame.index, dtype=object))
    predicted = frame.get("predicted", pd.Series(index=frame.index, dtype=object))
    fields = frame.get("field", pd.Series("unknown", index=frame.index)).astype(str)
    normalized_actual = pd.Series([_normalise_value(v, f) for v, f in zip(actual, fields)], index=frame.index)
    normalized_predicted = pd.Series([_normalise_value(v, f) for v, f in zip(predicted, fields)], index=frame.index)
    evaluated = normalized_actual.notna()
    exact = pd.Series(False, index=frame.index)
    numeric = fields.isin(NUMERIC_OCR_FIELDS)
    exact.loc[evaluated & ~numeric] = normalized_actual[evaluated & ~numeric].eq(normalized_predicted[evaluated & ~numeric])
    exact.loc[evaluated & numeric] = (normalized_actual[evaluated & numeric].astype(float) - normalized_predicted[evaluated & numeric].astype(float)).abs().le(0.001).fillna(False)
    working = frame.assign(_evaluated=evaluated, _exact=exact, _missing=normalized_predicted.isna())
    metric_rows = []
    for field, group in working[working["_evaluated"]].groupby("field"):
        metric_rows.append({"field": field, "evaluated_values": len(group), "exact_accuracy": group["_exact"].mean(), "numeric_accuracy": group["_exact"].mean() if field in NUMERIC_OCR_FIELDS else np.nan})
    metrics = pd.DataFrame(metric_rows, columns=empty.columns).sort_values("field") if metric_rows else empty
    receipt_keys = working.get("image_key", pd.Series(dtype=object)).dropna().unique()
    valid_json = working.get("valid_json", pd.Series(True, index=working.index)).fillna(False).astype(bool)
    item_counts = working[working.get("field", pd.Series("", index=working.index)).astype(str).eq("item_count")]
    true_items = pd.to_numeric(item_counts.get("actual", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    predicted_items = pd.to_numeric(item_counts.get("predicted", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    matched_items = min(true_items, predicted_items)
    precision = matched_items / predicted_items if predicted_items else np.nan
    recall = matched_items / true_items if true_items else np.nan
    f1 = 2 * precision * recall / (precision + recall) if pd.notna(precision) and pd.notna(recall) and precision + recall else np.nan
    errors = working[working["_evaluated"] & ~working["_exact"]].copy()
    return {
        "evaluated_receipts": len(receipt_keys), "evaluated_field_values": int(evaluated.sum()),
        "valid_json_rate": float(valid_json.mean()), "missing_field_rate": float(working.loc[evaluated, "_missing"].mean()),
        "metrics": metrics, "line_item": {"precision": precision, "recall": recall, "f1": f1},
        "median_processing_seconds": pd.to_numeric(working.get("processing_seconds", pd.Series(dtype=float)), errors="coerce").median(),
        "errors": errors.drop(columns=["_evaluated", "_exact", "_missing"], errors="ignore"),
    }
