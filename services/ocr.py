from __future__ import annotations

import base64
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

import pandas as pd
from PIL import Image, ImageOps


DEFAULT_PROFILE = "qwen25_featherless"
OCR_PROFILES = {
    "qwen25_featherless": {
        "label": "Recommended · Qwen 2.5 VL 3B",
        "model": "Qwen/Qwen2.5-VL-3B-Instruct",
        "provider": "featherless-ai",
        "note": "Good document understanding and structured invoice extraction.",
    },
    "qwen3_featherless": {
        "label": "Higher capacity · Qwen 3 VL 8B",
        "model": "Qwen/Qwen3-VL-8B-Instruct",
        "provider": "featherless-ai",
        "note": "Larger vision model; potentially slower and more expensive.",
    },
    "glm45v_novita": {
        "label": "Provider fallback · GLM 4.5V",
        "model": "zai-org/GLM-4.5V",
        "provider": "novita",
        "note": "Large multimodal fallback served through a different provider.",
    },
}
DEFAULT_MODEL = OCR_PROFILES[DEFAULT_PROFILE]["model"]
DEFAULT_PROVIDER = OCR_PROFILES[DEFAULT_PROFILE]["provider"]

OCR_SCHEMA = {
    "receipt_id": None,
    "transaction_date": None,
    "customer_name": None,
    "phone_number": None,
    "items": [{
        "description_raw": None,
        "brand_raw": None,
        "product_category": None,
        "color": None,
        "quantity": None,
        "unit_price_bhd": None,
        "line_total_bhd": None,
        "alteration_required": None,
        "alteration_details": None,
    }],
    "receipt_total_bhd": None,
    "advance_paid_bhd": None,
    "balance_bhd": None,
    "payment_status": None,
    "balance_paid_date": None,
}

OCR_PROMPT = f"""Extract this handwritten Galleria retail receipt.
Return one valid JSON object only, using this exact schema:
{json.dumps(OCR_SCHEMA, indent=2)}
Use YYYY-MM-DD dates and JSON numbers for BHD amounts.
Keep separate receipt lines as separate items in top-to-bottom order.
Never guess an unreadable value or brand; use null.
payment_status must be Paid, Partially Paid, Unpaid, or null."""


def _image_data_url(image_bytes: bytes, max_size: int = 1800) -> str:
    image = ImageOps.exif_transpose(Image.open(BytesIO(image_bytes))).convert("RGB")
    image.thumbnail((max_size, max_size))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=88, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.S)
    start = cleaned.find("{")
    if start < 0:
        raise ValueError("The model response did not contain JSON.")
    result, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    if not isinstance(result, dict):
        raise ValueError("The model response was not a JSON object.")
    return result


def extract_receipt(
    image_bytes: bytes,
    token: str,
    model: str = DEFAULT_MODEL,
    provider: str = DEFAULT_PROVIDER,
) -> dict[str, Any]:
    if not token:
        raise ValueError("HF_TOKEN is not configured.")
    from huggingface_hub import InferenceClient

    client = InferenceClient(provider=provider, api_key=token)
    response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": _image_data_url(image_bytes)}},
                {"type": "text", "text": OCR_PROMPT},
            ],
        }],
        max_tokens=1400,
        temperature=0.0,
    )
    return _parse_json(response.choices[0].message.content)


def extraction_error_message(error: Exception, model: str, provider: str) -> str:
    """Turn provider exceptions into a short, actionable setup message."""
    raw = str(error)
    lowered = raw.lower()
    if "model_not_supported" in lowered or "not supported by any provider" in lowered:
        return (
            f"{model} is not available through your enabled Hugging Face providers. "
            f"Enable **{provider}** in [Inference Provider settings]"
            "(https://hf.co/settings/inference-providers), or choose the provider fallback above."
        )
    if "401" in lowered or "unauthorized" in lowered or "authentication" in lowered:
        return (
            "The Hugging Face token was rejected. Create a fine-grained token with "
            "**Make calls to Inference Providers** permission and update `HF_TOKEN`."
        )
    if "403" in lowered or "forbidden" in lowered:
        return (
            "This token cannot call the selected inference provider. Check its Inference Providers "
            "permission and the provider settings on Hugging Face."
        )
    if "429" in lowered or "rate limit" in lowered or "quota" in lowered:
        return "The inference allowance is exhausted or temporarily rate-limited. Check Hugging Face billing and retry shortly."
    return f"OCR could not process this receipt: {raw}"


def demo_prediction() -> dict[str, Any]:
    return {
        "receipt_id": "DEMO-001",
        "transaction_date": datetime.now().date().isoformat(),
        "customer_name": "Review before saving",
        "phone_number": None,
        "items": [{
            "description_raw": "Black abaya",
            "brand_raw": None,
            "product_category": "Abaya",
            "color": "Black",
            "quantity": 1,
            "unit_price_bhd": 39.0,
            "line_total_bhd": 39.0,
            "alteration_required": None,
            "alteration_details": None,
        }],
        "receipt_total_bhd": 39.0,
        "advance_paid_bhd": None,
        "balance_bhd": None,
        "payment_status": "Paid",
        "balance_paid_date": None,
    }


def validation_warnings(prediction: dict[str, Any]) -> list[str]:
    warnings = []
    for field in ["receipt_id", "transaction_date", "receipt_total_bhd"]:
        if prediction.get(field) in {None, ""}:
            warnings.append(f"Missing {field.replace('_', ' ')}")
    items = prediction.get("items") or []
    if not items:
        warnings.append("No receipt items were detected")
    known_line_totals = [item.get("line_total_bhd") for item in items if item.get("line_total_bhd") is not None]
    receipt_total = prediction.get("receipt_total_bhd")
    if receipt_total is not None and known_line_totals:
        difference = abs(float(receipt_total) - sum(float(value) for value in known_line_totals))
        if difference > 0.01:
            warnings.append("Receipt total does not match the sum of detected line totals")
    if any(item.get("brand_raw") in {None, "", "Unknown"} for item in items):
        warnings.append("At least one brand needs manual confirmation")
    return warnings


def items_frame(prediction: dict[str, Any]) -> pd.DataFrame:
    columns = [
        "description_raw", "brand_raw", "product_category", "color",
        "quantity", "unit_price_bhd", "line_total_bhd",
        "alteration_required", "alteration_details",
    ]
    items = prediction.get("items") or []
    return pd.DataFrame(items, columns=columns)


def build_verified_payload(
    receipt_fields: dict[str, Any],
    customer_fields: dict[str, Any],
    items: pd.DataFrame,
    source_filename: str,
    ocr_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "verification_id": str(uuid4()),
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_filename": source_filename,
        "receipt": receipt_fields,
        "customer": customer_fields,
        "items": items.where(pd.notna(items), None).to_dict("records"),
    }
    if ocr_metadata:
        payload["ocr"] = ocr_metadata
    return payload


def append_verified_payload(payload: dict[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
