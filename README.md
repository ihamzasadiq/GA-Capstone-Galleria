# Galleria Store Intelligence

**Turn paper receipts into verified sales, brand, and customer insights.**

![Streamlit](https://img.shields.io/badge/interface-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-12%20passing-2E755E?style=for-the-badge)

Upload a receipt, verify the extracted fields, and use the clean data to understand what is selling and who is buying.

---

## What It Does

Galleria Concept rents display space to independent abaya brands. Sales were previously recorded on paper receipts, which made brand reporting and customer analysis slow and inconsistent.

This project converts those receipts into structured transaction data and presents the results in a focused four-page dashboard.

### Highlights

| Capability | Details |
| --- | --- |
| Receipt capture | Upload an image or take a photo from the browser |
| AI extraction | Extract receipt details and line items using a vision-language model |
| Human verification | Correct every extracted field before saving |
| Sales overview | Recorded product sales, receipt count, average receipt, and outstanding balance |
| Product analysis | Sales and units by product category |
| Brand analysis | Confirmed brand sales, units, average price, and downloadable statement |
| Customer groups | Top spenders, recent buyers, repeat customers, and alteration customers |
| Promotion planning | Transparent potential-sales scenario for a selected customer group |
| Privacy | Public demo files exclude names, phone numbers, email addresses, and physical addresses |

## Application Pages

### Home

A compact store summary showing:

- Recorded product sales
- Verified receipt count
- Average receipt value
- Outstanding customer balance
- Monthly sales movement
- Product sales mix
- Missing totals and unconfirmed brands requiring attention

### Receipts

The receipt workflow supports:

1. Uploading an image or taking a camera photo.
2. Sending the image to the configured OCR model.
3. Reviewing receipt details, customer information, and line items.
4. Flagging missing brands, totals, or inconsistent values.
5. Correcting the extracted result.
6. Saving only the verified transaction.

The OCR result is treated as a draft. Human confirmation remains part of the workflow.

### Sales

The Sales page separates two useful views:

- **Products:** value and units sold by category.
- **Brands:** confirmed sales, units, average price, transaction detail, and CSV export for a selected partner brand.

Unknown brands are excluded from brand comparisons instead of being guessed. The interface displays brand coverage so incomplete rankings are not presented as final results.

### Customers

Customer profiles are rebuilt from verified receipts whenever the application loads.

| Group | Rule |
| --- | --- |
| Top spenders | Highest 20% by recorded customer spend |
| Recent buyers | Last purchase within 30 days of the latest receipt in the dataset |
| Repeat customers | Two or more unique receipts |
| Needed alterations | At least one transaction with a confirmed alteration request |

Recency is anchored to the latest transaction in the dataset, not the current date. This prevents historical demo data from incorrectly making every customer appear inactive.

## Promotion Example

The Customers page includes a small scenario planner. It estimates possible orders and product sales from two editable assumptions:

- Percentage of selected customers who purchase
- Expected value of each resulting order

For example, using the included demo data:

```text
Customer group:          Top spenders
Customers selected:      9
Promotion:               Private collection preview
Assumed response rate:   20%
Possible orders:         1.8
Expected order value:    BHD 50.000
Potential product sales: BHD 90.000
```

The calculation is:

```text
Possible orders = selected customers × assumed response rate
Potential sales = possible orders × expected order value
Offer cost       = possible orders × cost per converted customer
```

This is a planning scenario, not a machine-learning prediction. Product sales are also not automatically Galleria revenue because Galleria currently earns fixed rental fees rather than sales commission.

## Current Data Snapshot

The anonymized demonstration dataset contains:

| Measure | Current value |
| --- | ---: |
| Verified receipts | 45 |
| Transaction lines | 51 |
| Recorded units and services | 55 |
| Known product sales | BHD 1,081.000 |
| Average known receipt | BHD 27.025 |
| Outstanding balance | BHD 121.500 |
| Confirmed brand rows | 3 of 51 |
| Date coverage | 20 March to 20 April 2025 |

The sample is suitable for demonstrating the workflow and validating calculations. It is not sufficient for reliable sales forecasting or complete brand ranking.

## OCR Configuration

Live receipt extraction uses Hugging Face Inference Providers. Create a fine-grained Hugging Face token with **Make calls to Inference Providers** permission.

Copy the example secrets file:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Then add:

```toml
HF_TOKEN = "hf_your_private_token"
HF_OCR_PROFILE = "qwen25_featherless"
```

Never commit `.streamlit/secrets.toml` or share the token publicly.

The default OCR profile uses:

| Setting | Value |
| --- | --- |
| Model | `Qwen/Qwen2.5-VL-3B-Instruct` |
| Provider | `featherless-ai` |
| Task | Structured receipt and line-item extraction |

The app also includes a sample extraction flow that works without a token.

## OCR Evaluation

The included notebook uses labelled receipt entries as ground truth. It can calculate:

- Exact accuracy by field
- Overall weighted field accuracy
- Number of evaluated values
- Number of evaluated receipts
- Receipt and item-field error examples

The dashboard does not invent an accuracy score. Results appear only after real OCR predictions are compared with verified answers and exported to `ocr_metrics_by_field.csv`.

## Run Locally

```bash
git clone <your-github-repository-url>
cd Galleria_Intelligence_App

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

streamlit run app.py
```

On Windows, activate the environment with:

```powershell
.venv\Scripts\activate
```

Streamlit will print a local address, normally `http://localhost:8501`.

## Project Layout

```text
.
|-- app.py                         # Application shell and four-page navigation
|-- assets/
|   `-- styles.css                 # Production-style visual system
|-- components/
|   |-- charts.py                  # Shared Plotly charts
|   `-- ui.py                      # Shared interface components
|-- views/
|   |-- overview.py                # Store summary
|   |-- receipt_ocr.py             # OCR and verification workflow
|   |-- brand_performance.py       # Product and brand sales
|   `-- customer_insights.py       # Customer groups and promotion scenario
|-- services/
|   |-- data.py                    # Data loading and business calculations
|   `-- ocr.py                     # OCR profiles, extraction, and validation
|-- data/demo/                     # Anonymized demonstration exports
|-- notebooks/
|   `-- Galleria_Intelligence_Clean_Capstone_Colab.ipynb
|-- scripts/
|   `-- check_app.py               # App, privacy, and calculation checks
|-- tests/                         # Service and page-rendering tests
|-- requirements.txt               # Runtime dependencies
`-- README.md
```

## Business Rules

- Store GMV is calculated once per receipt, not once per line item.
- Missing receipt totals are excluded from GMV and average receipt calculations.
- Brand comparisons use confirmed brand rows only.
- Customer spend is grouped by anonymized customer ID.
- The top-spender group contains the highest 20% of current profiles.
- Promotion outputs are labelled as scenarios rather than forecasts.
- Partner product sales are separated from Galleria rental income.

## Validation

Run the automated tests:

```bash
python -m unittest discover -s tests -v
```

Run the full application check:

```bash
python scripts/check_app.py
```

The checks cover:

- Receipt-level sales calculations
- Duplicate-safe monthly totals
- Brand coverage
- Customer profile rebuilding
- Promotion arithmetic
- OCR configuration and review payloads
- Public-demo privacy
- Rendering of all four pages

## Limitations

- Only 3 of 51 demo transaction lines currently have a confirmed brand.
- The demo covers approximately one month, so forecasting is intentionally excluded.
- Customer matching depends on a consistent private identifier, normally a normalized phone number converted into a customer ID.
- Promotion results remain estimates until Galleria records campaign recipients, redemptions, and actual purchases.
- Hosted OCR availability and cost depend on the selected inference provider.

## Built With

[Streamlit](https://streamlit.io/) · [pandas](https://pandas.pydata.org/) · [Plotly](https://plotly.com/python/) · [Hugging Face Inference Providers](https://huggingface.co/docs/inference-providers/index) · [Qwen2.5-VL](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct)
