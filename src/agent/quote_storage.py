"""SQLite persistence for quote-to-form extraction results.

This is separate from LangGraph's own thread/checkpoint storage, which
(in `langgraph dev`'s default in-memory runtime) lives only in process
memory and is gone on restart. This module is business data: what got
extracted from which quotation, and where the filled-in form ended up -
meant to survive server restarts and be queryable outside of a graph run.

Each call to `save_quote_record` appends one row and, if a filled form was
produced, writes it to `forms_dir` under `<row_id>.pdf`.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from agent.quote_extraction import QuoteFields

DEFAULT_DB_PATH = os.environ.get("QUOTE_DB_PATH", "data/quotes.db")
DEFAULT_FORMS_DIR = os.environ.get("FILLED_FORMS_DIR", "data/filled_forms")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS quote_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    vendor_name TEXT NOT NULL DEFAULT '',
    quote_no TEXT NOT NULL DEFAULT '',
    quote_date TEXT NOT NULL DEFAULT '',
    buyer_name TEXT NOT NULL DEFAULT '',
    subtotal TEXT NOT NULL DEFAULT '',
    vat TEXT NOT NULL DEFAULT '',
    grand_total TEXT NOT NULL DEFAULT '',
    items_json TEXT NOT NULL DEFAULT '[]',
    extraction_error TEXT,
    fill_warnings_json TEXT NOT NULL DEFAULT '[]',
    filled_form_path TEXT
);
"""


def init_db(db_path: str | os.PathLike[str] = DEFAULT_DB_PATH) -> None:
    """Create the quote_records table (and its parent directory) if needed."""
    parent = Path(db_path).parent
    if str(parent):
        parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(_SCHEMA)


def save_quote_record(
    fields: QuoteFields,
    *,
    fill_warnings: Iterable[str] | None = None,
    filled_form_bytes: bytes | None = None,
    db_path: str | os.PathLike[str] = DEFAULT_DB_PATH,
    forms_dir: str | os.PathLike[str] = DEFAULT_FORMS_DIR,
) -> int:
    """Persist one quote-to-form result and return its new row id.

    Safe to call even when extraction failed (``fields.error`` set) or no
    form template was supplied (``filled_form_bytes`` is ``None``) - a row
    is still written so failed attempts stay visible in the history too.
    """
    init_db(db_path)
    created_at = _utc_now_iso()

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO quote_records
                (created_at, vendor_name, quote_no, quote_date, buyer_name,
                 subtotal, vat, grand_total, items_json, extraction_error,
                 fill_warnings_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                fields.vendor_name,
                fields.quote_no,
                fields.quote_date,
                fields.buyer_name,
                fields.subtotal,
                fields.vat,
                fields.grand_total,
                json.dumps(
                    [dataclasses.asdict(item) for item in fields.items],
                    ensure_ascii=False,
                ),
                fields.error,
                json.dumps(list(fill_warnings or []), ensure_ascii=False),
            ),
        )
        row_id = cur.lastrowid
        assert row_id is not None  # AUTOINCREMENT always assigns one

        if filled_form_bytes:
            forms_dir_path = Path(forms_dir)
            forms_dir_path.mkdir(parents=True, exist_ok=True)
            filled_form_path = forms_dir_path / f"{row_id}.pdf"
            filled_form_path.write_bytes(filled_form_bytes)
            conn.execute(
                "UPDATE quote_records SET filled_form_path = ? WHERE id = ?",
                (str(filled_form_path), row_id),
            )
        conn.commit()
    return row_id


def get_quote_record(
    record_id: int, db_path: str | os.PathLike[str] = DEFAULT_DB_PATH
) -> dict[str, Any] | None:
    """Fetch one saved record by id, or None if it doesn't exist."""
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM quote_records WHERE id = ?", (record_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_quote_records(
    *, limit: int = 50, db_path: str | os.PathLike[str] = DEFAULT_DB_PATH
) -> list[dict[str, Any]]:
    """Fetch the most recently created records, newest first."""
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM quote_records ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["items"] = json.loads(data.pop("items_json"))
    data["fill_warnings"] = json.loads(data.pop("fill_warnings_json"))
    return data


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
