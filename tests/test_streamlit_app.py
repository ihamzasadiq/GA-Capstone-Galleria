from __future__ import annotations

from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class StreamlitSmokeTests(unittest.TestCase):
    def test_every_registered_page_renders(self) -> None:
        pages = [
            "views/overview.py",
            "views/receipt_ocr.py",
            "views/brand_performance.py",
            "views/customer_insights.py",
            "views/intelligence.py",
        ]
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.code), 0, "Overview rendered generated HTML as a code block")
        for page in pages[1:]:
            app.switch_page(page).run()
            self.assertEqual(len(app.exception), 0, f"{page} did not render cleanly")
            self.assertEqual(len(app.code), 0, f"{page} rendered generated HTML as a code block")

    def test_ocr_demo_opens_review_state(self) -> None:
        app = (
            AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
            .run()
            .switch_page("views/receipt_ocr.py")
            .run()
        )
        demo_button = next(button for button in app.button if button.label == "Try demo result")
        demo_button.click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("brand needs manual confirmation" in warning.value for warning in app.warning))


if __name__ == "__main__":
    unittest.main()
