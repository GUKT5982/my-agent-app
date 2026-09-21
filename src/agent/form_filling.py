"""Fill a fillable PDF form (AcroForm) from a flat dict of field values.

Kept generic and independent of any particular form layout: it matches
whatever field names the target PDF's widgets actually have against the
keys given, fills what matches, and reports what didn't - it never assumes
a specific template.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

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


def load_field_map(path: str | os.PathLike[str]) -> tuple[dict[str, str], str | None]:
    """Read a mapping file written by ``static/field-mapper/``.

    The file is ``{"fields": {"<widget name>": "<value key>"}}``. Returns the
    mapping and an error message; on any problem the mapping is empty and the
    message says why, so a bad file degrades to plain name matching instead of
    failing the whole fill.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        return {}, f"Could not read form mapping {path}: {exc}"
    except json.JSONDecodeError as exc:
        return {}, f"Form mapping {path} is not valid JSON: {exc}"

    fields = raw.get("fields") if isinstance(raw, dict) else None
    if not isinstance(fields, dict):
        return {}, f"Form mapping {path} has no 'fields' object"

    return {str(k): str(v) for k, v in fields.items() if v}, None


def fill_pdf_form(
    form_bytes: bytes,
    values: dict[str, str],
    *,
    field_map: dict[str, str] | None = None,
) -> FormFillResult:
    """Fill a fillable PDF's text widgets from a flat field-name -> value dict.

    Names are compared via ``_normalize_field_name``, and every widget whose
    name matches is filled - a field shown in several places (e.g. a quote
    number repeated in each page header) is filled everywhere.

    ``field_map`` maps a widget's own name to the key in ``values`` it should
    take, for the forms whose names no amount of normalizing will reconcile
    ("qty1" vs "item_1_qty"). It is consulted first - by exact widget name,
    then by normalized name - and name matching remains the fallback for
    every widget it doesn't mention.

    Never raises: a malformed form is reported via ``FormFillResult.error``.
    Keys in ``values`` with no matching widget, and widgets with no matching
    key, are both reported so callers can see incomplete mappings rather
    than silently losing data.
    """
    doc = open_pdf(form_bytes)
    if doc is None:
        return FormFillResult(error="Could not open form template: not a valid PDF")

    keys_by_normalized = {_normalize_field_name(k): k for k, v in values.items() if v}
    mapped_by_normalized = {
        _normalize_field_name(widget): key for widget, key in (field_map or {}).items()
    }
    matched_keys: set[str] = set()
    filled: list[str] = []
    empty_widgets: list[str] = []

    for i in range(doc.page_count):
        page: pymupdf.Page = doc[i]
        for widget in page.widgets() or []:  # type: ignore[no-untyped-call]
            name = widget.field_name
            key = None
            if field_map:
                key = field_map.get(name) or mapped_by_normalized.get(
                    _normalize_field_name(name)
                )
            if key is None:
                key = keys_by_normalized.get(_normalize_field_name(name))
            if key is None or not values.get(key):
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
