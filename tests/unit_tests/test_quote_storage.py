"""Unit tests for agent.quote_storage, using a throwaway SQLite file per test."""

from pathlib import Path

from agent.quote_extraction import QuoteFields, QuoteItem
from agent.quote_storage import get_quote_record, list_quote_records, save_quote_record


def _fields(**overrides: object) -> QuoteFields:
    base = dict(
        vendor_name="Acme Co.",
        quote_no="QT-1",
        quote_date="2026-09-16",
        buyer_name="Someone",
        items=[QuoteItem(description="Widget", qty="2", unit_price="10", amount="20")],
        subtotal="20",
        vat="1.4",
        grand_total="21.4",
    )
    base.update(overrides)
    return QuoteFields(**base)  # type: ignore[arg-type]


def test_save_and_get_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "quotes.db"
    record_id = save_quote_record(_fields(), db_path=db_path)

    record = get_quote_record(record_id, db_path=db_path)
    assert record is not None
    assert record["vendor_name"] == "Acme Co."
    assert record["quote_no"] == "QT-1"
    assert record["items"] == [
        {"description": "Widget", "qty": "2", "unit_price": "10", "amount": "20"}
    ]
    assert record["extraction_error"] is None
    assert record["fill_warnings"] == []
    assert record["filled_form_path"] is None


def test_save_writes_filled_form_to_disk(tmp_path: Path) -> None:
    db_path = tmp_path / "quotes.db"
    forms_dir = tmp_path / "forms"
    record_id = save_quote_record(
        _fields(),
        fill_warnings=["No matching form field for: notes"],
        filled_form_bytes=b"%PDF-fake-bytes",
        db_path=db_path,
        forms_dir=forms_dir,
    )

    record = get_quote_record(record_id, db_path=db_path)
    assert record is not None
    assert record["fill_warnings"] == ["No matching form field for: notes"]
    assert record["filled_form_path"] == str(forms_dir / f"{record_id}.pdf")
    assert Path(record["filled_form_path"]).read_bytes() == b"%PDF-fake-bytes"


def test_failed_extraction_is_still_recorded(tmp_path: Path) -> None:
    db_path = tmp_path / "quotes.db"
    record_id = save_quote_record(
        _fields(error="Model did not return valid JSON: ..."), db_path=db_path
    )

    record = get_quote_record(record_id, db_path=db_path)
    assert record is not None
    assert record["extraction_error"] == "Model did not return valid JSON: ..."


def test_get_missing_record_returns_none(tmp_path: Path) -> None:
    db_path = tmp_path / "quotes.db"
    assert get_quote_record(999, db_path=db_path) is None


def test_list_returns_newest_first(tmp_path: Path) -> None:
    db_path = tmp_path / "quotes.db"
    first_id = save_quote_record(_fields(quote_no="QT-1"), db_path=db_path)
    second_id = save_quote_record(_fields(quote_no="QT-2"), db_path=db_path)

    records = list_quote_records(db_path=db_path)
    assert [r["id"] for r in records] == [second_id, first_id]
    assert [r["quote_no"] for r in records] == ["QT-2", "QT-1"]


def test_list_respects_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "quotes.db"
    for i in range(5):
        save_quote_record(_fields(quote_no=f"QT-{i}"), db_path=db_path)

    assert len(list_quote_records(limit=2, db_path=db_path)) == 2
