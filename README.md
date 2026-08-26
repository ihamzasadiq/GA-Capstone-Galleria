# Galleria Store Workspace

A focused Streamlit app for four jobs:

1. See recorded sales
2. Add and verify receipts
3. Check product and brand sales
4. Find useful customer groups

The app deliberately does not show forecasting or campaign-profit predictions because the current dataset is too small to support them reliably.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Live receipt reading

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, add your Hugging Face token, and restart Streamlit. The sample receipt flow works without a token.

## Pages

- **Home:** sales totals, charts, and records needing attention
- **Receipts:** upload, extract, correct, and save a receipt
- **Sales:** product breakdown and confirmed brand sales
- **Customers:** current customer groups and a transparent promotion-sales scenario

Customer groups are rebuilt from receipt-level data whenever the app loads. Recency is measured from the latest transaction in the dataset, the top-spender group is limited to the highest 20%, and promotion figures are labelled as planning assumptions rather than predictions.

The included demo data contains no customer names or phone numbers.
