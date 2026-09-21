"""Score a quote-extraction run against the golden set built in the review page.

Manual/on-demand tool - NOT part of `make test` or CI. `static/quote-review/`
turns human judgements into a golden set: for each quotation, the value every
field should have. This replays that against a fresh export of
`data/quotes.db` and reports what still matches, so a prompt or model change
can be measured instead of eyeballed.

Quotations are matched between the two files by `quote_no` (records reviewed
without one fall back to their row id, which only matches the same run).

Usage:
    python scripts/export_quote_records.py --output data/quote_records.json
    python scripts/score_extraction.py --golden quote_review_verdicts.json \
        --records data/quote_records.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# The item columns are judged as a whole column ("were the quantities right?"),
# so scoring joins that column the same way the review page displays it.
ITEM_COLUMNS = {
    "items_desc": "description",
    "items_qty": "qty",
    "items_price": "unit_price",
    "items_amount": "amount",
}


def normalize(value: str) -> str:
    """Compare values the way a person reading them would.

    Whitespace and letter case never carry meaning here, and "1,200.00" and
    "1200" are the same amount written two ways, so numbers are compared as
    numbers. Everything else is compared as text.
    """
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    plain = text.replace(",", "")
    if re.fullmatch(r"-?\d+(\.\d+)?", plain):
        return str(float(plain))
    return text.casefold()


def value_of(record: dict[str, Any], field: str) -> str:
    """The value a record holds for a judged field name."""
    column = ITEM_COLUMNS.get(field)
    if column is None:
        return str(record.get(field, "") or "")
    values = [str(item.get(column, "") or "") for item in record.get("items", [])]
    return " · ".join(v for v in values if v)


def key_of(record: dict[str, Any]) -> str:
    """The key a record is matched on between runs."""
    quote_no = str(record.get("quote_no", "") or "")
    return quote_no if quote_no else f"id:{record.get('id')}"


def score(golden: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare every golden field against the matching record in this run."""
    by_key: dict[str, dict[str, Any]] = {}
    for record in records:
        by_key[key_of(record)] = record

    per_field: dict[str, dict[str, int]] = {}
    mismatches: list[dict[str, str]] = []
    missing_records: list[str] = []
    unusable: list[str] = []

    for key, entry in golden.items():
        record = by_key.get(key)
        if record is None:
            missing_records.append(key)
            continue

        for field, judged in (entry.get("fields") or {}).items():
            expected = str(judged.get("expected", "") or "")
            if judged.get("verdict") == "bad" and not expected:
                # Marked wrong but nobody typed what it should have been.
                unusable.append(f"{key}.{field}")
                continue

            stats = per_field.setdefault(field, {"match": 0, "differ": 0})
            actual = value_of(record, field)
            if normalize(actual) == normalize(expected):
                stats["match"] += 1
            else:
                stats["differ"] += 1
                mismatches.append(
                    {
                        "quote": key,
                        "field": field,
                        "expected": expected,
                        "actual": actual,
                    }
                )

    total_match = sum(s["match"] for s in per_field.values())
    total_checked = total_match + sum(s["differ"] for s in per_field.values())

    return {
        "checked_fields": total_checked,
        "matching_fields": total_match,
        "accuracy": round(100 * total_match / total_checked, 1)
        if total_checked
        else None,
        "quotes_scored": len(golden) - len(missing_records),
        "per_field": per_field,
        "mismatches": mismatches,
        "missing_records": missing_records,
        "unusable_judgements": unusable,
    }


def print_report(result: dict[str, Any]) -> None:
    print("\n=== Extraction score ===")
    if result["accuracy"] is None:
        print("Nothing could be scored - no golden field matched a record in this run.")
    else:
        print(
            f"Overall: {result['accuracy']}% "
            f"({result['matching_fields']}/{result['checked_fields']} fields) "
            f"across {result['quotes_scored']} quotation(s)"
        )

    if result["per_field"]:
        print("\nPer field (worst first):")
        rows = sorted(
            result["per_field"].items(),
            key=lambda kv: kv[1]["match"] / max(1, kv[1]["match"] + kv[1]["differ"]),
        )
        for field, stats in rows:
            checked = stats["match"] + stats["differ"]
            pct = 100 * stats["match"] / checked if checked else 0
            print(f"  {field:<16} {pct:5.1f}%  ({stats['match']}/{checked})")

    if result["mismatches"]:
        print(f"\nDifferences ({len(result['mismatches'])}):")
        for m in result["mismatches"][:20]:
            print(f"  {m['quote']} · {m['field']}")
            print(f"      expected: {m['expected']!r}")
            print(f"      actual:   {m['actual']!r}")
        if len(result["mismatches"]) > 20:
            print(f"  ...and {len(result['mismatches']) - 20} more")

    if result["missing_records"]:
        print(
            f"\nNot in this run ({len(result['missing_records'])}): "
            + ", ".join(result["missing_records"][:10])
        )
    if result["unusable_judgements"]:
        print(
            f"\nMarked wrong with no correct value typed, so not scored "
            f"({len(result['unusable_judgements'])}): "
            + ", ".join(result["unusable_judgements"][:10])
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--golden",
        type=Path,
        default=Path("quote_review_verdicts.json"),
        help="the file downloaded from static/quote-review/",
    )
    parser.add_argument(
        "--records",
        type=Path,
        default=Path("data/quote_records.json"),
        help="a fresh export from scripts/export_quote_records.py",
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="also write the result as JSON"
    )
    args = parser.parse_args()

    for path in (args.golden, args.records):
        if not path.is_file():
            print(f"File not found: {path}", file=sys.stderr)
            sys.exit(1)

    golden_file = json.loads(args.golden.read_text(encoding="utf-8"))
    golden = golden_file.get("golden")
    if not isinstance(golden, dict) or not golden:
        print(
            f"{args.golden} has no golden set. Re-download it from "
            "static/quote-review/ after judging some fields.",
            file=sys.stderr,
        )
        sys.exit(1)

    records_file = json.loads(args.records.read_text(encoding="utf-8"))
    records = records_file.get("records")
    if not isinstance(records, list):
        print(
            f"{args.records} is not an export from export_quote_records.py",
            file=sys.stderr,
        )
        sys.exit(1)

    result = score(golden, records)
    print_report(result)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
