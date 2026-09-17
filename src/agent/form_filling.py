"""Fill a fillable PDF form (AcroForm) from a flat dict of field values.

Kept generic and independent of any particular form layout: it matches
whatever field names the target PDF's widgets actually have against the
keys given, fills what matches, and reports what didn't - it never assumes
a specific template.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf

from agent.pdf_extraction import open_pdf


@dataclass
class FormFillResult:
    """Outcome of filling one PDF form."""

    filled_pdf: bytes = b""
    filled_fields: list[str] = field(default_factory=list)
    unmatched_values: list[str] = field(default_factory=list)
    empty_widgets: list[str] = field(default_factory=list)
    error: str | None = None


def _normalize_field_name(name: str) -> str:
    """Reduce a form field name to a form that survives authoring-tool styles.

    Templates rarely match our keys byte-for-byte: tools emit "Vendor Name",
    "VendorName" or "vendor-name" for the same field, and LiveCycle/XFA forms
    qualify every name with its container path and an index, e.g.
    "form1[0].page1[0].vendor_name[0]".
    """
    leaf = name.rsplit(".", 1)[-1]
    leaf = re.sub(r"\[\d+\]", "", leaf)
    return re.sub(r"[\W_]+", "", leaf.casefold())


def fill_pdf_form(form_bytes: bytes, values: dict[str, str]) -> FormFillResult:
    """Fill a fillable PDF's text widgets from a flat field-name -> value dict.

    Names are compared via ``_normalize_field_name``, and every widget whose
    name matches is filled - a field shown in several places (e.g. a quote
    number repeated in each page header) is filled everywhere.

    Never raises: a malformed form is reported via ``FormFillResult.error``.
    Keys in ``values`` with no matching widget, and widgets with no matching
    key, are both reported so callers can see incomplete mappings rather
    than silently losing data.
    """
    doc = open_pdf(form_bytes)
    if doc is None:
        return FormFillResult(error="Could not open form template: not a valid PDF")

    keys_by_normalized = {_normalize_field_name(k): k for k, v in values.items() if v}
    matched_keys: set[str] = set()
    filled: list[str] = []
    empty_widgets: list[str] = []

    for i in range(doc.page_count):
        page: pymupdf.Page = doc[i]
        for widget in page.widgets() or []:  # type: ignore[no-untyped-call]
            name = widget.field_name
            key = keys_by_normalized.get(_normalize_field_name(name))
            if key is None:
                empty_widgets.append(name)
                continue
            widget.field_value = values[key]
            widget.update()
            filled.append(name)
            matched_keys.add(key)

    # PyMuPDF's widget API only accepts the 4 base-14 Latin fonts (Cour,
    # TiRo, Helv, ZaDb) for a field's own appearance stream - any value
    # containing other scripts (Thai, CJK, Cyrillic, ...) would render
    # blank if left to that appearance alone. Setting NeedAppearances tells
    # standards-compliant viewers (Acrobat, Chrome, Edge, Foxit) to
    # regenerate each field's appearance at open time using their own font
    # substitution, which does render non-Latin scripts correctly.
    doc.need_appearances(True)  # type: ignore[no-untyped-call]

    return FormFillResult(
        filled_pdf=doc.tobytes(deflate=True, garbage=4),  # type: ignore[no-untyped-call]
        filled_fields=filled,
        unmatched_values=sorted(set(keys_by_normalized.values()) - matched_keys),
        empty_widgets=empty_widgets,
    )
