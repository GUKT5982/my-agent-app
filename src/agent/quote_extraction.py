"""Parse a price quotation's free-form text into structured fields.

Quotations from different vendors never share one fixed layout, so this
uses the project's existing Gemma/Ollama model to read the raw extracted
text and return structured JSON, rather than hand-written regex that would
only match one vendor's template.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from langchain_ollama import ChatOllama

SYSTEM_PROMPT = """You extract structured data from price quotation documents.
Read the quotation text and return ONLY a single JSON object (no prose, no \
markdown fences) with exactly this shape:

{
  "vendor_name": string,
  "quote_no": string,
  "quote_date": string,
  "buyer_name": string,
  "items": [
    {"description": string, "qty": string, "unit_price": string, "amount": string}
  ],
  "subtotal": string,
  "vat": string,
  "grand_total": string
}

Use "" for any field you cannot find. Keep numbers as they appear in the \
source text (including thousands separators). Do not invent values."""


@dataclass
class QuoteItem:
    """One line item on a quotation."""

    description: str = ""
    qty: str = ""
    unit_price: str = ""
    amount: str = ""


@dataclass
class QuoteFields:
    """Structured fields parsed out of a quotation's text."""

    vendor_name: str = ""
    quote_no: str = ""
    quote_date: str = ""
    buyer_name: str = ""
    items: list[QuoteItem] = field(default_factory=list)
    subtotal: str = ""
    vat: str = ""
    grand_total: str = ""
    error: str | None = None


def _strip_code_fence(text: str) -> str:
    """Remove a ```json ... ``` fence if the model wrapped its output in one."""
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    return match.group(1) if match else text


async def extract_quote_fields(
    text: str,
    *,
    model: str,
    base_url: str,
) -> QuoteFields:
    """Ask the configured Gemma model to parse quotation text into QuoteFields.

    Never raises: a model or parsing failure is reported via
    ``QuoteFields.error`` with an otherwise-empty result, so callers always
    get a usable object.
    """
    llm = ChatOllama(model=model, base_url=base_url, temperature=0)
    try:
        response = await llm.ainvoke(
            [("system", SYSTEM_PROMPT), ("human", text)],
        )
    except Exception as exc:  # noqa: BLE001 - surface as a field, never crash the graph
        return QuoteFields(error=f"Model call failed: {exc}")

    raw = _strip_code_fence(str(response.content)).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return QuoteFields(error=f"Model did not return valid JSON: {exc}")

    items = [
        QuoteItem(
            description=str(item.get("description", "")),
            qty=str(item.get("qty", "")),
            unit_price=str(item.get("unit_price", "")),
            amount=str(item.get("amount", "")),
        )
        for item in data.get("items", [])
        if isinstance(item, dict)
    ]
    return QuoteFields(
        vendor_name=str(data.get("vendor_name", "")),
        quote_no=str(data.get("quote_no", "")),
        quote_date=str(data.get("quote_date", "")),
        buyer_name=str(data.get("buyer_name", "")),
        items=items,
        subtotal=str(data.get("subtotal", "")),
        vat=str(data.get("vat", "")),
        grand_total=str(data.get("grand_total", "")),
    )


def quote_fields_to_form_values(quote: QuoteFields) -> dict[str, str]:
    """Flatten a QuoteFields into the field-name -> value shape a form expects.

    Item rows map positionally onto item_<n>_desc / _qty / _price / _amount
    field names, matching the convention used by scripts/generate_form_demo.py.
    """
    values: dict[str, str] = {
        "vendor_name": quote.vendor_name,
        "quote_no": quote.quote_no,
        "quote_date": quote.quote_date,
        "buyer_name": quote.buyer_name,
        "subtotal": quote.subtotal,
        "vat": quote.vat,
        "grand_total": quote.grand_total,
    }
    for i, item in enumerate(quote.items, start=1):
        values[f"item_{i}_desc"] = item.description
        values[f"item_{i}_qty"] = item.qty
        values[f"item_{i}_price"] = item.unit_price
        values[f"item_{i}_amount"] = item.amount
    return values
