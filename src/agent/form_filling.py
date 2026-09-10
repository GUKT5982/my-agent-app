"""Fill a fillable PDF form (AcroForm) from a flat dict of field values.

Kept generic and independent of any particular form layout: it matches
whatever field names the target PDF's widgets actually have against the
keys given, fills what matches, and reports what didn't - it never assumes
a specific template.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pymupdf


@dataclass
class FormFillResult:
    """Outcome of filling one PDF form."""

    filled_pdf: bytes = b""
    filled_fields: list[str] = field(default_factory=list)
    unmatched_values: list[str] = field(default_factory=list)
    empty_widgets: list[str] = field(default_factory=list)
    error: str | None = None


def fill_pdf_form(form_bytes: bytes, values: dict[str, str]) -> FormFillResult:
    """Fill a fillable PDF's text widgets from a flat field-name -> value dict.

    Never raises: a malformed form is reported via ``FormFillResult.error``.
    Keys in ``values`` with no matching widget, and widgets with no matching
    key, are both reported so callers can see incomplete mappings rather
    than silently losing data.
    """
    try:
        doc = pymupdf.open(stream=form_bytes, filetype="pdf")  # type: ignore[no-untyped-call]
    except Exception as exc:  # noqa: BLE001 - malformed form must not crash the pipeline
        return FormFillResult(error=f"Could not open form template: {exc}")

    remaining_keys = {k for k, v in values.items() if v}
    filled: list[str] = []
    empty_widgets: list[str] = []

    for i in range(doc.page_count):
        page: pymupdf.Page = doc[i]
        for widget in page.widgets() or []:  # type: ignore[no-untyped-call]
            name = widget.field_name
            if name in remaining_keys:
                widget.field_value = values[name]
                widget.update()
                filled.append(name)
                remaining_keys.discard(name)
            else:
                empty_widgets.append(name)

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
        unmatched_values=sorted(remaining_keys),
        empty_widgets=empty_widgets,
    )
