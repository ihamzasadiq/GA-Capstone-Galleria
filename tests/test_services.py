from __future__ import annotations

import unittest

import pandas as pd

from services.data import (
    brand_coverage,
    business_metrics,
    customer_profiles,
    load_bundle,
    monthly_sales,
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
        self.assertEqual(self.bundle.receipts["receipt_id"].nunique(), 45)
        self.assertEqual(len(self.bundle.transactions), 51)

    def test_receipt_level_business_metrics(self) -> None:
        metrics = business_metrics(self.bundle)
        self.assertAlmostEqual(metrics["gmv"], 1081.0, places=3)
        self.assertAlmostEqual(metrics["aov"], 27.025, places=3)
        self.assertAlmostEqual(metrics["outstanding"], 121.5, places=3)
        self.assertEqual(metrics["units"], 55.0)

    def test_brand_coverage_is_not_inflated(self) -> None:
        self.assertAlmostEqual(brand_coverage(self.bundle.transactions), 3 / 51)

    def test_monthly_sales_does_not_double_count_receipts(self) -> None:
        monthly = monthly_sales(self.bundle.receipts)
        self.assertAlmostEqual(monthly["gmv_bhd"].sum(), 1081.0, places=3)

    def test_customer_profiles_are_rebuilt_from_receipts(self) -> None:
        profiles = customer_profiles(self.bundle)
        self.assertEqual(len(profiles), 45)
        self.assertEqual(int(profiles["top_spender"].sum()), 9)
        self.assertEqual(int(profiles["repeat_customer"].sum()), 0)
        self.assertEqual(int(profiles["days_since_purchase"].min()), 0)

    def test_promotion_projection_is_transparent_arithmetic(self) -> None:
        result = promotion_projection(20, 0.10, 40.0, 5.0)
        self.assertAlmostEqual(result["expected_orders"], 2.0)
        self.assertAlmostEqual(result["potential_gmv_bhd"], 80.0)
        self.assertAlmostEqual(result["offer_budget_bhd"], 10.0)


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
