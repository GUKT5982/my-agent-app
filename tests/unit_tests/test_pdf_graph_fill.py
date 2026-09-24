"""Graph-level tests for the quote-to-form path, with the model stubbed out.

No Ollama needed: extract_quote_fields is replaced by a fake, so these run
the real extract_pdf -> fill_form wiring. The PDFs are built in memory
because demo_*.pdf are gitignored and need a Windows font to regenerate.
"""

import base64
import importlib
from typing import Any

import pytest

fitz = pytest.importorskip(
    "pymupdf", reason="pymupdf not installed; run: pip install -e '.[pdf]'"
)

from agent.quote_extraction import QuoteFields  # noqa: E402

# `from agent import pdf_graph` gives the compiled graph, not the module:
# agent/__init__.py re-exports the graph under that name.
pdf_graph = importlib.import_module("agent.pdf_graph")

pytestmark = pytest.mark.anyio


def _quote_pdf() -> str:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Quotation QT-1 from Acme Co.")
    return base64.b64encode(doc.tobytes()).decode("ascii")


def _form_pdf() -> str:
    doc = fitz.open()
    page = doc.new_page()
    for i, name in enumerate(["vendor_name", "quote_no"]):
        widget = fitz.Widget()
        widget.field_name = name
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.rect = fitz.Rect(50, 50 + i * 30, 300, 70 + i * 30)
        page.add_widget(widget)
    return base64.b64encode(doc.tobytes()).decode("ascii")


async def _run_with_fields(
    monkeypatch: pytest.MonkeyPatch, fields: QuoteFields
) -> dict[str, Any]:
    async def fake_extract(text: str, **kwargs: Any) -> QuoteFields:
        return fields

    monkeypatch.setattr(pdf_graph, "extract_quote_fields", fake_extract)
    return await pdf_graph.graph.ainvoke(
        {"pdf_base64": _quote_pdf(), "form_template_base64": _form_pdf()},
        context={"save_to_db": False},
    )


async def test_failed_extraction_returns_no_form_and_says_why(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = await _run_with_fields(
        monkeypatch, QuoteFields(error="Model did not return a valid JSON object")
    )

    # Keys no node wrote are left out of the output, not returned empty.
    assert not out.get("filled_form_base64")
    assert len(out["fill_warnings"]) == 1
    assert "quote extraction failed" in out["fill_warnings"][0]
    assert "Model did not return a valid JSON object" in out["fill_warnings"][0]


async def test_successful_extraction_still_fills_the_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = await _run_with_fields(
        monkeypatch, QuoteFields(vendor_name="Acme Co.", quote_no="QT-1")
    )

    doc = fitz.open(stream=base64.b64decode(out["filled_form_base64"]), filetype="pdf")
    values = {w.field_name: w.field_value for w in doc[0].widgets()}
    assert values == {"vendor_name": "Acme Co.", "quote_no": "QT-1"}
