"""LangGraph graph for PDF text extraction and quote-to-form auto-fill.

Accepts a PDF as base64-encoded bytes (the way a real API client would
submit an uploaded file) and returns the extracted, orientation-normalized
text. This graph is independent of the Gemma chat graph in `graph.py`.

If a ``form_template_base64`` (a blank fillable PDF form) is also given,
the graph continues past extraction: it asks Gemma to parse the extracted
text into structured quotation fields, then fills those values into the
form's matching fields, so a person doesn't have to retype them by hand.
Without a form template, the graph stops at plain text extraction.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import dataclasses
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Literal

from langgraph.graph import StateGraph
from langgraph.runtime import Runtime
from typing_extensions import TypedDict

from agent.form_filling import fill_pdf_form
from agent.pdf_extraction import extract_pdf_text
from agent.quote_extraction import (
    QuoteFields,
    QuoteItem,
    extract_quote_fields,
    quote_fields_to_form_values,
)

# Reuse the same Gemma/Ollama defaults as the chat graph (graph.py).
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:31b-cloud")
DEFAULT_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


class PdfContext(TypedDict, total=False):
    """Context parameters for the PDF extraction agent.

    Set these when creating assistants OR when invoking the graph.
    See: https://langchain-ai.github.io/langgraph/cloud/how-tos/configuration_cloud/
    """

    lang: str
    zoom: float
    enable_deskew: bool
    tesseract_cmd: str
    model: str
    base_url: str


@dataclass
class PdfState:
    """Input/output state for the PDF extraction / quote-to-form agent.

    See: https://langchain-ai.github.io/langgraph/concepts/low_level/#state
    """

    pdf_base64: str = ""
    text: str = ""
    pages: list[Dict[str, Any]] = field(default_factory=list)
    page_count: int = 0
    ocr_page_count: int = 0
    embedded_text_page_count: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    # Quote-to-form auto-fill (only runs when form_template_base64 is set).
    form_template_base64: str = ""
    extracted_fields: Dict[str, Any] = field(default_factory=dict)
    filled_form_base64: str = ""
    fill_warnings: list[str] = field(default_factory=list)


async def extract_pdf(state: PdfState, runtime: Runtime[PdfContext]) -> Dict[str, Any]:
    """Decode the base64 PDF payload and extract normalized, readable text.

    OCR is CPU-bound, so the actual extraction runs in a worker thread via
    `asyncio.to_thread` rather than blocking the event loop.
    """
    try:
        pdf_bytes = base64.b64decode(state.pdf_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        return {"error": f"Invalid base64 PDF payload: {exc}"}

    context = runtime.context or {}
    result = await asyncio.to_thread(
        extract_pdf_text,
        pdf_bytes,
        lang=context.get("lang", "eng"),
        zoom=context.get("zoom", 2.0),
        enable_deskew=context.get("enable_deskew", True),
        tesseract_cmd=context.get("tesseract_cmd"),
    )
    return dataclasses.asdict(result)


def _route_after_extract(state: PdfState) -> Literal["extract_quote_fields", "__end__"]:
    """Only run the quote-to-form steps when a form template was supplied."""
    if state.error or not state.form_template_base64:
        return "__end__"
    return "extract_quote_fields"


async def extract_quote_fields_node(
    state: PdfState, runtime: Runtime[PdfContext]
) -> Dict[str, Any]:
    """Parse the quotation's extracted text into structured fields via Gemma."""
    context = runtime.context or {}
    fields = await extract_quote_fields(
        state.text,
        model=context.get("model", DEFAULT_MODEL),
        base_url=context.get("base_url", DEFAULT_BASE_URL),
    )
    return {"extracted_fields": dataclasses.asdict(fields)}


async def fill_form_node(
    state: PdfState, runtime: Runtime[PdfContext]
) -> Dict[str, Any]:
    """Fill the supplied form template with the extracted quotation fields."""
    try:
        form_bytes = base64.b64decode(state.form_template_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        return {"fill_warnings": [f"Invalid base64 form template: {exc}"]}

    fields = QuoteFields(
        vendor_name=state.extracted_fields.get("vendor_name", ""),
        quote_no=state.extracted_fields.get("quote_no", ""),
        quote_date=state.extracted_fields.get("quote_date", ""),
        buyer_name=state.extracted_fields.get("buyer_name", ""),
        items=[QuoteItem(**item) for item in state.extracted_fields.get("items", [])],
        subtotal=state.extracted_fields.get("subtotal", ""),
        vat=state.extracted_fields.get("vat", ""),
        grand_total=state.extracted_fields.get("grand_total", ""),
    )
    values = quote_fields_to_form_values(fields)

    result = await asyncio.to_thread(fill_pdf_form, form_bytes, values)
    warnings = []
    if result.error:
        warnings.append(result.error)
    if result.unmatched_values:
        warnings.append(
            f"No matching form field for: {', '.join(result.unmatched_values)}"
        )
    return {
        "filled_form_base64": base64.b64encode(result.filled_pdf).decode("ascii"),
        "fill_warnings": warnings,
    }


# Define the graph
graph = (
    StateGraph(PdfState, context_schema=PdfContext)
    .add_node(extract_pdf)
    .add_node("extract_quote_fields", extract_quote_fields_node)
    .add_node("fill_form", fill_form_node)
    .add_edge("__start__", "extract_pdf")
    .add_conditional_edges("extract_pdf", _route_after_extract)
    .add_edge("extract_quote_fields", "fill_form")
    .compile(name="PDF Extraction Graph")
)
