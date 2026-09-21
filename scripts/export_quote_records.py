"""Export saved quote-to-form results from SQLite to JSON for review.

Manual/on-demand tool - NOT part of `make test` or CI. `data/quotes.db` has
every extraction the graph has run, but nothing reads it back: this dumps it
in the shape `static/quote-review/` expects, so the results can be judged
field by field and turned into a golden set.

Usage:
    python scripts/export_quote_records.py
    python scripts/export_quote_records.py --limit 500 --output data/quote_records.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running this script directly without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent.quote_storage import DEFAULT_DB_PATH, list_quote_records  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=Path(DEFAULT_DB_PATH))
    parser.add_argument(
        "--limit", type=int, default=500, help="how many records, newest first"
    )
    parser.add_argument("--output", type=Path, default=Path("data/quote_records.json"))
    args = parser.parse_args()

    if not args.db_path.is_file():
        print(f"Database not found: {args.db_path}", file=sys.stderr)
        print(
            "Run a quote-to-form extraction first, or pass --db-path.", file=sys.stderr
        )
        sys.exit(1)

    records = list_quote_records(limit=args.limit, db_path=args.db_path)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(args.db_path),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    failed = sum(1 for r in records if r.get("extraction_error"))
    with_form = sum(1 for r in records if r.get("filled_form_path"))
    print(f"Exported {len(records)} record(s) from {args.db_path}")
    print(f"  extraction errors: {failed}")
    print(f"  with a filled form on disk: {with_form}")
    print(f"\nWrote {args.output}")
    print("Open static/quote-review/index.html and drop that file in to review them.")


if __name__ == "__main__":
    main()
