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
from typing import Any

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

DEFAULT_MAX_ATTEMPTS = 3


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
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> QuoteFields:
    """Ask the configured Gemma model to parse quotation text into QuoteFields.

    A reply that isn't a JSON object is retried up to ``max_attempts`` times.
    A failed model call is not retried: it means the model is unreachable,
    and retrying would only multiply the wait.

    Never raises: a model or parsing failure is reported via
    ``QuoteFields.error`` with an otherwise-empty result, so callers always
    get a usable object.
    """
    llm = ChatOllama(model=model, base_url=base_url, temperature=0)
    messages: list[tuple[str, str]] = [("system", SYSTEM_PROMPT), ("human", text)]

    last_error: ValueError | None = None
    for _ in range(max_attempts):
        try:
            response = await llm.ainvoke(messages)
        except Exception as exc:  # noqa: BLE001 - surface as a field, never crash the graph
            return QuoteFields(error=f"Model call failed: {exc}")

        reply = str(response.content)
        try:
            data = json.loads(_strip_code_fence(reply).strip())
            if not isinstance(data, dict):
                raise ValueError(f"expected a JSON object, got {type(data).__name__}")
        except ValueError as exc:  # JSONDecodeError is a ValueError subclass
            last_error = exc
            # At temperature=0 re-sending the same prompt yields the same bad
            # reply, so show the model what it sent and why it was rejected.
            messages += [
                ("ai", reply),
                (
                    "human",
                    f"That reply was rejected: {exc}. Respond with ONLY the "
                    "JSON object described in the instructions.",
                ),
            ]
            continue
        return _quote_fields_from_json(data)

    return QuoteFields(
        error=f"Model did not return a valid JSON object after "
        f"{max_attempts} attempts: {last_error}"
    )


def _quote_fields_from_json(data: dict[str, Any]) -> QuoteFields:
    """Build QuoteFields from the model's parsed JSON object."""
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
