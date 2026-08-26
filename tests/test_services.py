from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
