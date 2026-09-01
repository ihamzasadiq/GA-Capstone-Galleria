# Galleria Store Intelligence

**Turn paper receipts into verified sales, brand, and customer insights.**

![Streamlit](https://img.shields.io/badge/interface-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-16%20passing-2E755E?style=for-the-badge)

Upload a receipt, verify the extracted fields, and use the clean data to understand what is selling and who is buying.

---

## What It Does

Galleria Concept rents display space to independent abaya brands. Sales were previously recorded on paper receipts, which made brand reporting and customer analysis slow and inconsistent.

This project converts those receipts into structured transaction data and presents the results in a focused five-page dashboard.

### Highlights

| Capability | Details |
| --- | --- |
| Receipt capture | Upload an image or take a photo from the browser |
| AI extraction | Extract receipt details and line items using a vision-language model |
| Human verification | Correct every extracted field before saving |
| Sales overview | Recorded product sales, receipt count, average receipt, and outstanding balance |
| Product analysis | Sales and units by product category |
| Brand analysis | Confirmed brand sales, units, average price, and downloadable statement |
| Walk-in campaigns | Exclusive, rule-based audiences for lapsed, high-value, alteration, and returning customers |
| Promotion planning | Consent-gated store-only codes and a transparent sales/discount scenario |
| Intelligence | Exploratory purchase patterns, guarded next-week GMV baselines, and OCR benchmark reporting |
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

| Campaign audience | Rule |
| --- | --- |
| Inactive high spender | Highest 20% by recorded spend and no purchase for 90+ days |
| Inactive customer | No purchase for 90+ days |
| Active top spender | Highest 20% by recorded spend, but not inactive |
| Alteration customer | At least one transaction with a confirmed alteration request, with no higher-priority campaign |
| Recent or repeat customer | Purchase within 30 days or two or more receipts, with no higher-priority campaign |

Recency and inactivity are anchored to the latest transaction in the dataset, not the current date. Each customer receives their first matching campaign only, so offers do not stack.

### Intelligence

The Intelligence page makes its uncertainty explicit:

- **Purchase Patterns** clusters complete receipts—not people—using standardized GMV, units, line count, product/alteration mix, payment state, and outstanding balance. K-Means considers 2–6 groups and selects the highest silhouette score. Labels describe the observed receipt profile only.
- **Weekly GMV Forecast** is a one-week exploratory estimate. It compares last-week value, four-week moving average, and simple exponential smoothing with expanding-window MAE and WAPE. A historical gap is not converted into zero-sales weeks; only the newest continuous weekly period can train the model, and fewer than eight weeks shows an unavailable state.
- **OCR Evaluation** displays only saved, de-identified benchmark results. It reports held-out receipt and field counts, JSON and missing-field rates, normalized field accuracy, BHD ±0.001 numeric accuracy, line-item precision/recall/F1, processing time, and error examples.

The current workbook scope is **82 receipt IDs, 96 transaction lines, and 79 purchasing customer IDs**. Seventy-seven of those customers have one recorded receipt, so RFM frequency is descriptive rather than evidence of stable customer behaviour. The two active date periods are separated by 201 days; forecasting remains exploratory. The bundled public demo is a larger 224-receipt fixture used for application tests and does not replace the capstone workbook.

## Promotion Example

The Customers page uses social media for product awareness and presents store-only offers as a reason to walk in. It assigns one of five priority audiences to an eligible customer and creates a 14-day, one-time promotion code only for customers with recorded marketing consent. Each merchandise offer uses the customer's preferred category: the highest recorded product-sales value, with the most recent purchase breaking a tie. Alteration, delivery, unknown, and zero-value rows do not establish a preference.

The scenario planner estimates possible orders, product sales before discounts, and the offer liability from two editable assumptions:

- Percentage of selected customers who purchase
- Expected value of each resulting order

For example, using the included demo data:

```text
Campaign audience:       Inactive high spender
Customers selected:      30
Promotion:               BHD 10 off a preferred-category purchase of BHD 60+
Assumed response rate:   8%
Possible orders:         2.4
Expected order value:    BHD 60.000
Potential product sales: BHD 144.000
Maximum discount liability: BHD 24.000
```

The calculation is:

```text
Possible orders = selected customers × assumed response rate
Potential sales = possible orders × expected order value
Offer liability  = possible orders × discount per converted customer
```

This is a planning scenario, not a machine-learning prediction. Product sales are also not automatically Galleria revenue because Galleria currently earns fixed rental fees rather than sales commission.

## Included Demo Snapshot

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

## OCR Evaluation and Benchmark Protocol

Qwen 2.5-VL remains the primary document-to-JSON extractor. It will be benchmarked against PaddleOCR PP-StructureV3, an optional structured-document dependency. The deployed dashboard reads saved de-identified results and never needs OCR benchmark dependencies or private receipt images.

Once the 82 receipt images are available, normalize every image name to a canonical image key, then use a fixed receipt-level split:

- 60 development receipts for prompt/parser configuration
- 22 held-out receipts for the final evaluation

Do not tune either pipeline on the held-out receipts. The evaluation reports:

- Normalized exact accuracy by field and numeric accuracy within BHD 0.001
- Evaluated receipt and field-value counts, valid-JSON and missing-field rates
- Line-item precision, recall, and F1
- Median processing time and a de-identified error-type table with image examples held in protected storage

This is an evaluation of pretrained models, not fine-tuning. Original images, names, phones, and raw predictions remain outside Git and outside public dashboard exports.

## Run Locally

```bash
git clone <your-github-repository-url>
cd Galleria_Intelligence_App

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-notebook.txt

streamlit run app.py
```

For the optional local PaddleOCR PP-StructureV3 benchmark only (not required to run the dashboard):

```bash
python -m pip install -r requirements-ocr-benchmark.txt
```

### Run the notebook locally

Use the virtual environment created above, not a separately installed Homebrew Jupyter. Put the private workbook and receipt images in a local folder outside the repository, then run:

```bash
bash scripts/run_notebook.sh /absolute/path/to/Galleria_Capstone
```

The script uses that folder as `GALLERIA_PROJECT_DIR`, saves the executed notebook to its `outputs/` directory, and produces public dashboard exports in `outputs/public/`.

On Windows, activate the environment with:

```powershell
.venv\Scripts\activate
```

Streamlit will print a local address, normally `http://localhost:8501`.

## Project Layout

```text
.
|-- app.py                         # Application shell and five-page navigation
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
|   `-- intelligence.py            # Exploratory patterns, forecast, and OCR evaluation
|-- services/
|   |-- data.py                    # Data loading and business calculations
|   `-- ocr.py                     # OCR profiles, extraction, and validation
|   `-- intelligence.py            # Canonical receipts, modelling, and safe benchmark metrics
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
- Inactive customers have not purchased for 90+ days relative to the latest receipt in the dataset.
- Campaign priority prevents a customer from receiving more than one offer.
- Preferred merchandise categories are calculated from confirmed positive-value product sales; alteration customers instead receive a tailoring-service credit.
- Direct recipient exports and promotion codes require recorded marketing consent.
- Promotion outputs are labelled as scenarios rather than forecasts.
- Partner product sales are separated from Galleria rental income.
- Purchase-pattern clusters are exploratory receipt groups, not customer segments.
- Missing dates and totals are kept as quality flags and excluded from modelling; they are never imputed.
- Public exports must exclude names, phone numbers, addresses, emails, and receipt images.

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
- Canonical receipt aggregation, duplicate protection, model gating, OCR metrics, and public-export privacy
- Rendering of all five pages

## Limitations

- Only 3 of 51 demo transaction lines currently have a confirmed brand.
- The demo covers approximately one month, so the Intelligence page correctly leaves the forecast unavailable.
- The capstone's two observed date periods have a 201-day gap, which rules out a seasonal or long-range forecast.
- Seventy-seven of 79 capstone customers currently have one recorded receipt; customer repeat behaviour cannot yet be modelled reliably.
- Promotion results remain estimates until Galleria records campaign recipients, redemptions, and actual purchases.
- Hosted OCR availability and cost depend on the selected inference provider.

## Built With

[Streamlit](https://streamlit.io/) · [pandas](https://pandas.pydata.org/) · [Plotly](https://plotly.com/python/) · [Hugging Face Inference Providers](https://huggingface.co/docs/inference-providers/index) · [Qwen2.5-VL](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct)
