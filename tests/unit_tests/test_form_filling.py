"""Unit tests for agent.form_filling, using a synthetic in-memory AcroForm."""

import json
from pathlib import Path

import pytest

fitz = pytest.importorskip(
    "pymupdf", reason="pymupdf not installed; run: pip install -e '.[pdf]'"
)

from agent.form_filling import fill_pdf_form, load_field_map  # noqa: E402


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


def test_fill_matches_names_across_authoring_styles() -> None:
    form_bytes = _make_form(
        ["Vendor Name", "QUOTE-NO", "form1[0].page1[0].buyer_name[0]"]
    )
    result = fill_pdf_form(
        form_bytes,
        {"vendor_name": "Acme Co.", "quote_no": "QT-1", "buyer_name": "Agent Tech"},
    )

    assert result.error is None
    assert result.unmatched_values == []
    assert result.empty_widgets == []

    doc = fitz.open(stream=result.filled_pdf, filetype="pdf")
    values = {w.field_name: w.field_value for w in doc[0].widgets()}
    assert values == {
        "Vendor Name": "Acme Co.",
        "QUOTE-NO": "QT-1",
        "form1[0].page1[0].buyer_name[0]": "Agent Tech",
    }


def test_fill_does_not_match_different_item_rows() -> None:
    form_bytes = _make_form(["item_1_qty", "item_11_qty"])
    result = fill_pdf_form(form_bytes, {"item_1_qty": "10"})

    assert result.filled_fields == ["item_1_qty"]
    assert result.empty_widgets == ["item_11_qty"]


def test_fill_every_widget_sharing_a_field_name() -> None:
    form_bytes = _make_form(["quote_no", "quote_no"])
    result = fill_pdf_form(form_bytes, {"quote_no": "QT-1"})

    assert result.filled_fields == ["quote_no", "quote_no"]
    assert result.empty_widgets == []
    assert result.unmatched_values == []


def test_fill_corrupted_form_bytes() -> None:
    result = fill_pdf_form(b"not a real pdf", {"vendor_name": "Acme"})
    assert result.error is not None
    assert result.filled_pdf == b""


def test_fill_rejects_non_pdf_template() -> None:
    # PyMuPDF's repair mode opens an HTML file as a PDF with fabricated pages;
    # without a header check that garbage came back as the "filled form".
    html = b"<html><body>" + b"<p>hello world</p>" * 500 + b"</body></html>"
    result = fill_pdf_form(html, {})
    assert result.error is not None
    assert result.filled_pdf == b""


def test_field_map_fills_names_that_normalizing_cannot_reconcile() -> None:
    # The shape a real vendor form uses: nothing here normalizes to our keys.
    form_bytes = _make_form(["Description 1", "qty1", "price1", "amt1"])
    result = fill_pdf_form(
        form_bytes,
        {
            "item_1_desc": "Widget",
            "item_1_qty": "3",
            "item_1_price": "100.00",
            "item_1_amount": "300.00",
        },
        field_map={
            "Description 1": "item_1_desc",
            "qty1": "item_1_qty",
            "price1": "item_1_price",
            "amt1": "item_1_amount",
        },
    )

    assert result.error is None
    assert sorted(result.filled_fields) == ["Description 1", "amt1", "price1", "qty1"]
    assert result.unmatched_values == []

    doc = fitz.open(stream=result.filled_pdf, filetype="pdf")
    values = {w.field_name: w.field_value for w in doc[0].widgets()}
    assert values["qty1"] == "3"
    assert values["Description 1"] == "Widget"


def test_field_map_leaves_name_matching_as_the_fallback() -> None:
    form_bytes = _make_form(["qty1", "vendor_name"])
    result = fill_pdf_form(
        form_bytes,
        {"item_1_qty": "3", "vendor_name": "Acme Co."},
        field_map={"qty1": "item_1_qty"},
    )

    assert sorted(result.filled_fields) == ["qty1", "vendor_name"]
    assert result.unmatched_values == []


def test_field_map_matches_a_widget_by_its_normalized_name() -> None:
    # The mapping was written against "qty1"; the template qualifies the name.
    form_bytes = _make_form(["form1[0].page1[0].qty1[0]"])
    result = fill_pdf_form(
        form_bytes, {"item_1_qty": "3"}, field_map={"qty1": "item_1_qty"}
    )

    assert result.filled_fields == ["form1[0].page1[0].qty1[0]"]


def test_field_map_to_a_value_that_is_absent_leaves_the_widget_empty() -> None:
    # A 8-row form mapped for every row, filled from a 1-item quote.
    form_bytes = _make_form(["qty1", "qty5"])
    result = fill_pdf_form(
        form_bytes,
        {"item_1_qty": "3"},
        field_map={"qty1": "item_1_qty", "qty5": "item_5_qty"},
    )

    assert result.filled_fields == ["qty1"]
    assert result.empty_widgets == ["qty5"]


def test_load_field_map_reads_the_mapper_file(tmp_path: Path) -> None:
    path = tmp_path / "form_mapping.json"
    path.write_text(
        json.dumps({"version": 1, "fields": {"qty1": "item_1_qty", "amt1": ""}}),
        encoding="utf-8",
    )

    field_map, error = load_field_map(path)

    assert error is None
    # An empty value means "leave this widget alone", so it is not a mapping.
    assert field_map == {"qty1": "item_1_qty"}


def test_load_field_map_reports_a_missing_file(tmp_path: Path) -> None:
    field_map, error = load_field_map(tmp_path / "nope.json")

    assert field_map == {}
    assert error is not None and "Could not read" in error


def test_load_field_map_reports_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")

    field_map, error = load_field_map(path)

    assert field_map == {}
    assert error is not None and "not valid JSON" in error


def test_load_field_map_reports_a_file_without_fields(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"version": 1}), encoding="utf-8")

    field_map, error = load_field_map(path)

    assert field_map == {}
    assert error is not None and "no 'fields' object" in error
