"""Dump a fillable PDF's AcroForm field names, and what the filler would do with them.

Manual/on-demand tool - NOT part of `make test` or CI. Before a real customer
form can be auto-filled we have to know the field names its widgets actually
carry, and which of them `fill_pdf_form` already matches on its own. This
prints that, and writes a JSON dump that `static/field-mapper/` turns into a
mapping file for the names it cannot match by itself.

Usage:
    python scripts/inspect_form_fields.py demo_form.pdf
    python scripts/inspect_form_fields.py real_form.pdf --output form_fields.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Allow running this script directly without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent.form_filling import _normalize_field_name  # noqa: E402
from agent.pdf_extraction import open_pdf  # noqa: E402
from agent.quote_extraction import (  # noqa: E402
    QuoteFields,
    QuoteItem,
    quote_fields_to_form_values,
)


def _value_keys() -> dict[str, list[str]]:
    """The field-name keys `quote_fields_to_form_values` can produce.

    Item rows are per-row, so they are reported as templates (`item_{n}_qty`)
    that the mapper expands to however many rows the form actually has.
    """
    one_row = quote_fields_to_form_values(QuoteFields(items=[QuoteItem()]))
    single = [k for k in one_row if not k.startswith("item_")]
    item_row = [
        k.replace("item_1_", "item_{n}_") for k in one_row if k.startswith("item_")
    ]
    return {"single": single, "item_row": item_row}


def inspect_form(form_bytes: bytes) -> dict[str, Any]:
    """Describe every widget in a form, and the value key it would be filled from."""
    doc = open_pdf(form_bytes)
    if doc is None:
        raise ValueError("Could not open form template: not a valid PDF")

    keys = _value_keys()
    # A form with 30 item rows is unusual but harmless to probe for.
    probe = quote_fields_to_form_values(
        QuoteFields(items=[QuoteItem() for _ in range(30)])
    )
    auto_keys = {_normalize_field_name(k): k for k in probe}

    fields: list[dict[str, Any]] = []
    for page_index in range(doc.page_count):
        page = doc[page_index]
        for widget in page.widgets() or []:  # type: ignore[no-untyped-call]
            name = widget.field_name or ""
            normalized = _normalize_field_name(name)
            fields.append(
                {
                    "name": name,
                    "normalized": normalized,
                    # PyMuPDF names the type for us; the numeric constants
                    # are easy to get wrong and differ between versions.
                    "type": (widget.field_type_string or "unknown").lower(),
                    "page": page_index + 1,
                    "value": widget.field_value or "",
                    "auto_match": auto_keys.get(normalized),
                }
            )

    return {
        "page_count": doc.page_count,
        "value_keys": keys,
        "fields": fields,
    }


def _print_summary(report: dict[str, Any]) -> None:
    fields = report["fields"]
    matched = [f for f in fields if f["auto_match"]]
    unmatched = [f for f in fields if not f["auto_match"]]

    print("\n=== Form fields ===")
    print(f"Widgets: {len(fields)} across {report['page_count']} page(s)")
    print(f"Auto-matched by fill_pdf_form: {len(matched)}")
    print(f"Needs a mapping: {len(unmatched)}")

    if matched:
        print("\nMatched:")
        for f in matched:
            print(f"  {f['name']}  ->  {f['auto_match']}")
    if unmatched:
        print("\nUnmatched (these stay blank until mapped):")
        for f in unmatched:
            print(f"  {f['name']}  [{f['type']}, page {f['page']}]")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("form", type=Path, help="the fillable PDF to inspect")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="write the JSON dump here (default: <form>.fields.json)",
    )
    args = parser.parse_args()

    if not args.form.is_file():
        print(f"Form not found: {args.form}", file=sys.stderr)
        sys.exit(1)

    try:
        report = inspect_form(args.form.read_bytes())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    report["form"] = str(args.form)
    output = args.output or args.form.with_suffix(".fields.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    _print_summary(report)
    print(f"\nWrote field dump to {output}")
    print(
        "Open static/field-mapper/index.html and drop that file in to build a mapping."
    )


if __name__ == "__main__":
    main()
