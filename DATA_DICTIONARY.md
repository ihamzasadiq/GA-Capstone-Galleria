# Data dictionary

## Transaction-level fields

| Field | Meaning |
|---|---|
| `image_key` | Normalized receipt image identifier |
| `receipt_id` | Business receipt number |
| `line_number` | Item order within the receipt |
| `transaction_date` | Verified sale date |
| `customer_id` | Anonymized customer identifier |
| `transaction_type` | Product sale or alteration/service |
| `brand_clean` | Verified brand; `Unknown` when not confirmed |
| `description_raw` | Receipt item description |
| `product_category` | Standardized merchandise/service category |
| `quantity` | Units on the receipt line |
| `unit_price_bhd` | Unit price in Bahraini dinar |
| `line_total_clean` | Verified line value |
| `receipt_total_bhd` | Receipt-level total repeated for audit only; do not sum by line |
| `payment_status` | Original line/receipt payment label |
| `alteration_required` | Whether an alteration is recorded |

## Receipt-level fields

| Field | Meaning |
|---|---|
| `receipt_total_clean` | One verified total per receipt, used for GMV |
| `receipt_total_source` | Whether the total came from receipt evidence or remains missing |
| `amount_paid_bhd` | Derived amount paid using verified status |
| `current_outstanding_bhd` | Current balance, not the original formula placeholder |
| `final_payment_status` | Standardized latest payment state |

## Customer-level fields

| Field | Meaning |
|---|---|
| `receipts` | Count of verified receipts linked to the customer |
| `total_spend_bhd` | Sum of valid receipt totals |
| `last_purchase` | Most recent verified transaction date |
| `high_value` | Transparent top-spend rule from the notebook |
| `inactive` | Customer is beyond the current inactivity threshold |
| `alteration_customer` | At least one linked alteration transaction |
| `primary_audience` | Main campaign-planning segment |

Names, phone numbers, consent evidence, and receipt images are private operational data and are not part of public analytics exports.
