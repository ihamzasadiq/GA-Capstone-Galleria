from __future__ import annotations

import unittest

import pandas as pd

from services.data import (
    DataBundle,
    WALK_IN_CAMPAIGNS,
    assign_walk_in_campaigns,
    brand_coverage,
    business_metrics,
    campaign_recipients,
    customer_profiles,
    load_bundle,
    monthly_sales,
    preferred_category_by_customer,
    promotion_code,
    promotion_projection,
)
from services.ocr import (
    DEFAULT_PROFILE,
    OCR_PROFILES,
    build_verified_payload,
    demo_prediction,
    extraction_error_message,
    items_frame,
    validation_warnings,
)
from services.intelligence import (
    assert_public_export,
    canonical_image_key,
    canonical_receipts,
    cluster_purchase_patterns,
    forecast_next_week,
    ocr_metric_summary,
)


class DataServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_bundle()

    def test_demo_dataset_shape(self) -> None:
        self.assertEqual(self.bundle.receipts["receipt_id"].nunique(), 224)
        self.assertEqual(len(self.bundle.transactions), 270)

    def test_receipt_level_business_metrics(self) -> None:
        metrics = business_metrics(self.bundle)
        self.assertAlmostEqual(metrics["gmv"], 6292.0, places=3)
        self.assertAlmostEqual(metrics["aov"], 33.6470588, places=3)
        self.assertAlmostEqual(metrics["outstanding"], 441.75, places=3)
        self.assertEqual(metrics["units"], 310.0)

    def test_brand_coverage_is_not_inflated(self) -> None:
        self.assertAlmostEqual(brand_coverage(self.bundle.transactions), 3 / 270)

    def test_monthly_sales_does_not_double_count_receipts(self) -> None:
        monthly = monthly_sales(self.bundle.receipts)
        self.assertAlmostEqual(monthly["gmv_bhd"].sum(), 6187.0, places=3)

    def test_customer_profiles_are_rebuilt_from_receipts(self) -> None:
        profiles = customer_profiles(self.bundle)
        self.assertEqual(len(profiles), 220)
        self.assertEqual(int(profiles["top_spender"].sum()), 44)
        self.assertEqual(int(profiles["repeat_customer"].sum()), 3)
        self.assertEqual(int(profiles["inactive_customer"].sum()), 145)
        self.assertEqual(int(profiles["campaign_audience"].notna().sum()), 196)
        self.assertEqual(int(profiles["contactable_with_consent"].sum()), 0)
        self.assertEqual(int(profiles["days_since_purchase"].min()), 0)

    def test_promotion_projection_is_transparent_arithmetic(self) -> None:
        result = promotion_projection(20, 0.10, 40.0, 5.0)
        self.assertAlmostEqual(result["expected_orders"], 2.0)
        self.assertAlmostEqual(result["potential_gmv_bhd"], 80.0)
        self.assertAlmostEqual(result["offer_budget_bhd"], 10.0)

    def test_inactive_boundary_is_anchored_to_latest_receipt(self) -> None:
        receipts = pd.DataFrame([
            {"receipt_id": "R1", "customer_id": "C1", "transaction_date": "2026-01-08", "receipt_total_clean": 100.0},
            {"receipt_id": "R2", "customer_id": "C2", "transaction_date": "2025-10-10", "receipt_total_clean": 80.0},
            {"receipt_id": "R3", "customer_id": "C3", "transaction_date": "2025-10-11", "receipt_total_clean": 70.0},
            {"receipt_id": "R4", "customer_id": "C4", "transaction_date": "2026-01-07", "receipt_total_clean": 60.0},
            {"receipt_id": "R5", "customer_id": "C5", "transaction_date": "2026-01-06", "receipt_total_clean": 50.0},
        ])
        receipts["transaction_date"] = pd.to_datetime(receipts["transaction_date"])
        bundle = DataBundle(
            transactions=pd.DataFrame(columns=["customer_id"]), receipts=receipts,
            brands=pd.DataFrame(), categories=pd.DataFrame(), ocr_metrics=pd.DataFrame(),
            ocr_evaluation=pd.DataFrame(), source_dir=self.bundle.source_dir,
        )
        profiles = customer_profiles(bundle).set_index("customer_id")
        self.assertTrue(bool(profiles.loc["C2", "inactive_customer"]))
        self.assertFalse(bool(profiles.loc["C3", "inactive_customer"]))

    def test_walk_in_campaigns_are_exclusive_and_codes_are_stable(self) -> None:
        profiles = pd.DataFrame([
            {"customer_id": "C1", "preferred_category": "Abaya", "inactive_customer": True, "top_spender": True, "alteration_customer": True, "recent_customer": False, "repeat_customer": False, "contactable_with_consent": True},
            {"customer_id": "C2", "preferred_category": "Dress", "inactive_customer": True, "top_spender": False, "alteration_customer": False, "recent_customer": False, "repeat_customer": False, "contactable_with_consent": True},
            {"customer_id": "C3", "preferred_category": "Blazer", "inactive_customer": False, "top_spender": True, "alteration_customer": False, "recent_customer": True, "repeat_customer": False, "contactable_with_consent": True},
            {"customer_id": "C4", "preferred_category": "Abaya", "inactive_customer": False, "top_spender": False, "alteration_customer": True, "recent_customer": True, "repeat_customer": False, "contactable_with_consent": False},
            {"customer_id": "C5", "preferred_category": "Abaya", "inactive_customer": False, "top_spender": False, "alteration_customer": False, "recent_customer": False, "repeat_customer": True, "contactable_with_consent": True},
            {"customer_id": "C6", "preferred_category": "Selected merchandise", "inactive_customer": False, "top_spender": False, "alteration_customer": False, "recent_customer": False, "repeat_customer": False, "contactable_with_consent": True},
        ])
        assigned = assign_walk_in_campaigns(profiles)
        audiences = assigned["campaign_audience"].astype(object).where(
            assigned["campaign_audience"].notna(), None
        ).tolist()
        self.assertListEqual(audiences, [
            "Inactive high spender", "Inactive customer", "Active top spender",
            "Alteration customer", "Recent or repeat customer", None,
        ])
        recipients = campaign_recipients(assigned, "Inactive high spender", "2026-09-01")
        self.assertEqual(recipients["customer_id"].tolist(), ["C1"])
        self.assertEqual(recipients["recipient_offer"].iloc[0], "BHD 10 off your next Abaya purchase of BHD 60 or more")
        self.assertEqual(recipients["expires_on"].iloc[0].isoformat(), "2026-09-15")
        self.assertEqual(
            promotion_code("C1", "Inactive high spender", "2026-09-01"),
            promotion_code("C1", "Inactive high spender", "2026-09-01"),
        )
        self.assertNotEqual(
            promotion_code("C1", "Inactive high spender", "2026-09-01"),
            promotion_code("C1", "Inactive high spender", "2026-09-02"),
        )

    def test_preferred_category_uses_sales_then_recency_and_excludes_services(self) -> None:
        transactions = pd.DataFrame([
            {"customer_id": "C1", "product_category": "Abaya", "line_total_clean": 50.0, "transaction_date": "2026-01-01", "transaction_type": "Product Sale"},
            {"customer_id": "C1", "product_category": "Dress", "line_total_clean": 50.0, "transaction_date": "2026-01-02", "transaction_type": "Product Sale"},
            {"customer_id": "C1", "product_category": "Alteration", "line_total_clean": 100.0, "transaction_date": "2026-01-03", "transaction_type": "Alteration"},
            {"customer_id": "C2", "product_category": "Unknown", "line_total_clean": 80.0, "transaction_date": "2026-01-03", "transaction_type": "Product Sale"},
            {"customer_id": "C2", "product_category": "Abaya", "line_total_clean": 0.0, "transaction_date": "2026-01-04", "transaction_type": "Product Sale"},
        ])
        preferred = preferred_category_by_customer(transactions)
        self.assertEqual(preferred.loc["C1"], "Dress")
        self.assertNotIn("C2", preferred.index)
        self.assertEqual(WALK_IN_CAMPAIGNS["Alteration customer"]["minimum_spend_bhd"], 0.0)

    def test_percentage_offer_liability_is_included(self) -> None:
        result = promotion_projection(20, 0.10, 100.0, discount_rate=0.10)
        self.assertAlmostEqual(result["discount_per_order_bhd"], 10.0)
        self.assertAlmostEqual(result["offer_budget_bhd"], 20.0)


class OCRServiceTests(unittest.TestCase):
    def test_default_profile_pins_a_real_provider(self) -> None:
        profile = OCR_PROFILES[DEFAULT_PROFILE]
        self.assertEqual(profile["provider"], "featherless-ai")
        self.assertEqual(profile["model"], "Qwen/Qwen2.5-VL-3B-Instruct")

    def test_provider_error_is_actionable(self) -> None:
        error = RuntimeError("model_not_supported: not supported by any provider you have enabled")
        message = extraction_error_message(error, "model", "featherless-ai")
        self.assertIn("Inference Provider settings", message)
        self.assertIn("featherless-ai", message)

    def test_demo_prediction_has_review_warning(self) -> None:
        prediction = demo_prediction()
        self.assertIn("At least one brand needs manual confirmation", validation_warnings(prediction))
        self.assertEqual(len(items_frame(prediction)), 1)

    def test_verified_payload_keeps_private_data_separate(self) -> None:
        prediction = demo_prediction()
        payload = build_verified_payload(
            {"receipt_id": "TEST-1", "receipt_total_bhd": 39.0},
            {"customer_name": "Private", "phone_number": "Private"},
            items_frame(prediction),
            "receipt.jpg",
        )
        self.assertIn("customer", payload)
        self.assertNotIn("customer_name", payload["receipt"])
        self.assertEqual(payload["source_filename"], "receipt.jpg")


class IntelligenceServiceTests(unittest.TestCase):
    def test_canonical_receipts_deduplicates_lines_and_preserves_missing_flags(self) -> None:
        transactions = pd.DataFrame([
            {"receipt_id": "1", "line_number": 1, "transaction_date": "2025-01-06", "receipt_total_bhd": 10, "quantity": 1, "line_total_clean": 10},
            {"receipt_id": "1", "line_number": 1, "transaction_date": "2025-01-06", "receipt_total_bhd": 10, "quantity": 1, "line_total_clean": 10},
            {"receipt_id": "2", "line_number": 1, "transaction_date": None, "receipt_total_bhd": None, "quantity": 1, "line_total_clean": None},
        ])
        receipts = canonical_receipts(transactions)
        self.assertEqual(len(receipts), 2)
        self.assertEqual(int(receipts.loc[receipts["receipt_id"].eq("1"), "duplicate_line_count"].iloc[0]), 2)
        self.assertTrue(bool(receipts.loc[receipts["receipt_id"].eq("2"), "missing_date"].iloc[0]))
        self.assertTrue(bool(receipts.loc[receipts["receipt_id"].eq("2"), "missing_total"].iloc[0]))

    def test_purchase_clusters_are_deterministic(self) -> None:
        rows = []
        for number in range(8):
            rows.append({
                "receipt_id": str(number), "receipt_total_clean": 10 + number * 10,
                "units": 1 + number % 2, "line_count": 1, "product_mix": "Abaya" if number < 4 else "Dress",
                "alteration_mix": "No alteration", "payment_state": "Paid", "outstanding_balance_bhd": 0,
            })
        first, scores = cluster_purchase_patterns(pd.DataFrame(rows))
        second, _ = cluster_purchase_patterns(pd.DataFrame(rows))
        self.assertFalse(scores.empty)
        self.assertListEqual(first["pattern_cluster"].tolist(), second["pattern_cluster"].tolist())

    def test_forecast_gates_short_history_and_reports_gap(self) -> None:
        short = pd.DataFrame({"transaction_date": pd.date_range("2025-01-06", periods=7, freq="7D"), "receipt_total_clean": range(10, 17)})
        self.assertFalse(forecast_next_week(short)["available"])
        dates = list(pd.date_range("2025-01-06", periods=4, freq="7D")) + list(pd.date_range("2025-03-03", periods=8, freq="7D"))
        long = pd.DataFrame({"transaction_date": dates, "receipt_total_clean": range(12, 24)})
        result = forecast_next_week(long)
        self.assertTrue(result["available"])
        self.assertTrue(result["gap_detected"])
        self.assertEqual(result["evaluation_weeks"], 4)

    def test_image_key_and_public_ocr_metrics(self) -> None:
        self.assertEqual(canonical_image_key("Receipt_001.JPG"), "receipt-1")
        evaluation = pd.DataFrame([
            {"image_key": "receipt-001.jpg", "split": "Holdout test", "field": "receipt_total_bhd", "actual": 10.0, "predicted": 10.0005, "valid_json": True, "processing_seconds": 1.2},
            {"image_key": "receipt-001.jpg", "split": "Holdout test", "field": "item_count", "actual": 2, "predicted": 1, "valid_json": True, "processing_seconds": 1.2},
        ])
        summary = ocr_metric_summary(evaluation)
        self.assertEqual(summary["evaluated_receipts"], 1)
        total_metric = summary["metrics"].loc[summary["metrics"]["field"].eq("receipt_total_bhd"), "exact_accuracy"].iloc[0]
        self.assertAlmostEqual(total_metric, 1.0)
        with self.assertRaises(ValueError):
            assert_public_export(pd.DataFrame({"customer_name": ["Private"]}))


if __name__ == "__main__":
    unittest.main()
