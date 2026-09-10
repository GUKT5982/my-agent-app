"""Unit tests for agent.form_filling, using a synthetic in-memory AcroForm."""

import pytest

fitz = pytest.importorskip(
    "pymupdf", reason="pymupdf not installed; run: pip install -e '.[pdf]'"
)

from agent.form_filling import fill_pdf_form  # noqa: E402


def _make_form(field_names: list[str]) -> bytes:
    """Build a minimal fillable PDF with one text widget per given name."""
    doc = fitz.open()
    page = doc.new_page()
    for i, name in enumerate(field_names):
        widget = fitz.Widget()
        widget.field_name = name
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.rect = fitz.Rect(50, 50 + i * 30, 300, 70 + i * 30)
        page.add_widget(widget)
    return doc.tobytes()  # type: ignore[no-any-return]


def test_fill_matches_fields_by_name() -> None:
    form_bytes = _make_form(["vendor_name", "quote_no"])
    result = fill_pdf_form(form_bytes, {"vendor_name": "Acme Co.", "quote_no": "QT-1"})

    assert result.error is None
    assert sorted(result.filled_fields) == ["quote_no", "vendor_name"]
    assert result.unmatched_values == []
    assert result.empty_widgets == []

    doc = fitz.open(stream=result.filled_pdf, filetype="pdf")
    values = {w.field_name: w.field_value for w in doc[0].widgets()}
    assert values == {"vendor_name": "Acme Co.", "quote_no": "QT-1"}


def test_fill_reports_unmatched_values_and_empty_widgets() -> None:
    form_bytes = _make_form(["vendor_name"])
    result = fill_pdf_form(
        form_bytes, {"vendor_name": "", "quote_no": "QT-1", "buyer_name": "Someone"}
    )

    assert result.error is None
    assert result.filled_fields == []
    assert sorted(result.unmatched_values) == ["buyer_name", "quote_no"]
    assert result.empty_widgets == ["vendor_name"]


def test_fill_corrupted_form_bytes() -> None:
    result = fill_pdf_form(b"not a real pdf", {"vendor_name": "Acme"})
    assert result.error is not None
    assert result.filled_pdf == b""
