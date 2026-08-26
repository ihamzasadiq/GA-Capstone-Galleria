from __future__ import annotations

import compileall
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.data import business_metrics, load_bundle  # noqa: E402


REQUIRED_FILES = [
    "app.py",
    "requirements.txt",
    "README.md",
    "assets/styles.css",
    "views/overview.py",
    "views/receipt_ocr.py",
    "views/brand_performance.py",
    "views/customer_insights.py",
    "data/demo/transactions_clean_public.csv",
    "data/demo/receipts_clean_public.csv",
]
PRIVATE_COLUMNS = {"customer_name", "phone", "phone_number", "mobile", "email", "address"}


def fail(message: str) -> None:
    raise SystemExit(f"CHECK FAILED: {message}")


def main() -> None:
    missing = [relative for relative in REQUIRED_FILES if not (ROOT / relative).exists()]
    if missing:
        fail(f"missing required files: {', '.join(missing)}")

    if not compileall.compile_dir(ROOT, quiet=1):
        fail("one or more Python files did not compile")

    for csv_path in sorted((ROOT / "data" / "demo").glob("*.csv")):
        columns = {column.strip().lower() for column in pd.read_csv(csv_path, nrows=0).columns}
        exposed = columns & PRIVATE_COLUMNS
        if exposed:
            fail(f"{csv_path.name} exposes private columns: {sorted(exposed)}")

    bundle = load_bundle(ROOT / "data" / "demo")
    metrics = business_metrics(bundle)
    if int(metrics["receipts"]) != 45 or len(bundle.transactions) != 51:
        fail("demo record counts do not match the verified benchmark")
    if round(metrics["gmv"], 3) != 1081.000:
        fail("GMV is not calculated at receipt level")

    print("All application, data, privacy, and calculation checks passed.")


if __name__ == "__main__":
    main()
