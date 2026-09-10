"""Generate two demo PDFs for the quote-to-form auto-fill feature.

Manual/on-demand tool, not part of the test suite. Produces:
  - demo_quote.pdf   a realistic Thai price quotation (source document)
  - demo_form.pdf    a blank fillable PDF form (AcroForm) with matching
                      field names, meant to be filled from the quotation

Run: python scripts/generate_form_demo.py [output_dir]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

# Base-14 fonts (helv, etc.) have no Thai glyphs, so Thai text needs a real
# embedded font. Tahoma ships with Windows and covers Thai script.
THAI_FONT_PATH = r"C:\Windows\Fonts\tahoma.ttf"
THAI_FONT_NAME = "thai"

QUOTE_LINES = [
    ("บริษัท สยามอุปกรณ์สำนักงาน จำกัด", 14, True),
    ("123/45 ถ.สุขุมวิท แขวงคลองตัน เขตคลองเตย กรุงเทพฯ 10110", 10, False),
    ("โทร. 02-123-4567  อีเมล khun.somchai@siamoffice.co.th", 10, False),
    ("", 8, False),
    ("ใบเสนอราคา / QUOTATION", 16, True),
    ("", 8, False),
    ("เลขที่ใบเสนอราคา: QT-2026-0142", 11, False),
    ("วันที่: 08/09/2026", 11, False),
    ("เสนอต่อ: บริษัท เอเจนท์ เทคโนโลยี จำกัด", 11, False),
    ("ยืนราคาถึง: 08/10/2026", 11, False),
    ("", 10, False),
]

ITEMS = [
    ("เก้าอี้สำนักงาน (Office Chair) รุ่น ERGO-100", "10", "2,500.00", "25,000.00"),
    ("โต๊ะทำงาน (Office Desk) ขนาด 120x60 ซม.", "10", "4,200.00", "42,000.00"),
    ("ตู้เอกสาร (Filing Cabinet) 4 ลิ้นชัก", "4", "3,800.00", "15,200.00"),
]

TOTALS = [
    ("รวมเป็นเงิน (Subtotal)", "82,200.00"),
    ("ภาษีมูลค่าเพิ่ม 7% (VAT)", "5,754.00"),
    ("จำนวนเงินรวมทั้งสิ้น (Grand Total)", "87,954.00"),
]

FORM_FIELDS = [
    # (field_name, label, y_position)
    ("vendor_name", "ชื่อผู้ขาย / Vendor", 120),
    ("quote_no", "เลขที่ใบเสนอราคา / Quote No.", 150),
    ("quote_date", "วันที่ / Date", 180),
    ("buyer_name", "ผู้ซื้อ / Buyer", 210),
]

ITEM_FIELD_ROWS = [
    ("item_1_desc", "item_1_qty", "item_1_price", "item_1_amount", 270),
    ("item_2_desc", "item_2_qty", "item_2_price", "item_2_amount", 300),
    ("item_3_desc", "item_3_qty", "item_3_price", "item_3_amount", 330),
]

TOTAL_FIELDS = [
    ("subtotal", "รวมเป็นเงิน / Subtotal", 400),
    ("vat", "ภาษีมูลค่าเพิ่ม 7% / VAT", 425),
    ("grand_total", "ยอดรวมทั้งสิ้น / Grand Total", 450),
]


def build_quote_pdf() -> bytes:
    """Build a plain, embedded-text price quotation PDF."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4

    y = 60
    for text, size, bold in QUOTE_LINES:
        if text:
            page.insert_text(
                (56, y),
                text,
                fontsize=size,
                fontname=THAI_FONT_NAME,
                fontfile=THAI_FONT_PATH,
            )
        y += size + 8

    # Item table header
    col_x = [56, 330, 400, 470]
    headers = ["รายการ", "จำนวน", "ราคา/หน่วย", "จำนวนเงิน"]
    for x, h in zip(col_x, headers):
        page.insert_text(
            (x, y), h, fontsize=10, fontname=THAI_FONT_NAME, fontfile=THAI_FONT_PATH
        )
    y += 6
    page.draw_line((56, y), (539, y))
    y += 16

    for desc, qty, price, amount in ITEMS:
        page.insert_text(
            (col_x[0], y),
            desc,
            fontsize=9,
            fontname=THAI_FONT_NAME,
            fontfile=THAI_FONT_PATH,
        )
        page.insert_text(
            (col_x[1], y),
            qty,
            fontsize=9,
            fontname=THAI_FONT_NAME,
            fontfile=THAI_FONT_PATH,
        )
        page.insert_text(
            (col_x[2], y),
            price,
            fontsize=9,
            fontname=THAI_FONT_NAME,
            fontfile=THAI_FONT_PATH,
        )
        page.insert_text(
            (col_x[3], y),
            amount,
            fontsize=9,
            fontname=THAI_FONT_NAME,
            fontfile=THAI_FONT_PATH,
        )
        y += 20

    y += 6
    page.draw_line((56, y), (539, y))
    y += 20

    for label, value in TOTALS:
        page.insert_text(
            (330, y),
            label,
            fontsize=10,
            fontname=THAI_FONT_NAME,
            fontfile=THAI_FONT_PATH,
        )
        page.insert_text(
            (470, y),
            value,
            fontsize=10,
            fontname=THAI_FONT_NAME,
            fontfile=THAI_FONT_PATH,
        )
        y += 18

    doc.subset_fonts()
    return doc.tobytes(deflate=True, garbage=4)


def _add_text_field(page: pymupdf.Page, name: str, rect: pymupdf.Rect) -> None:
    widget = pymupdf.Widget()
    widget.field_name = name
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT  # type: ignore[attr-defined]
    widget.rect = rect
    widget.border_color = (0.6, 0.6, 0.6)
    widget.text_fontsize = 9
    page.add_widget(widget)


def build_form_pdf() -> bytes:
    """Build a blank fillable PDF form (AcroForm) matching the quote fields."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    page.insert_text(
        (56, 50),
        "ใบบันทึกรับใบเสนอราคา / QUOTATION INTAKE FORM",
        fontsize=14,
        fontname=THAI_FONT_NAME,
        fontfile=THAI_FONT_PATH,
    )
    page.draw_line((56, 60), (539, 60))

    for field_name, label, y in FORM_FIELDS:
        page.insert_text(
            (56, y), label, fontsize=9, fontname=THAI_FONT_NAME, fontfile=THAI_FONT_PATH
        )
        _add_text_field(page, field_name, pymupdf.Rect(260, y - 12, 500, y + 4))

    page.insert_text(
        (56, 245),
        "รายการสินค้า / Line items",
        fontsize=10,
        fontname=THAI_FONT_NAME,
        fontfile=THAI_FONT_PATH,
    )
    col_x = [56, 300, 380, 460]
    headers = ["รายการ", "จำนวน", "ราคา/หน่วย", "จำนวนเงิน"]
    for x, h in zip(col_x, headers):
        page.insert_text(
            (x, 260), h, fontsize=8, fontname=THAI_FONT_NAME, fontfile=THAI_FONT_PATH
        )

    col_widths = [235, 70, 70, 79]
    for desc_f, qty_f, price_f, amount_f, y in ITEM_FIELD_ROWS:
        x = col_x[0]
        for field_name, width in zip((desc_f, qty_f, price_f, amount_f), col_widths):
            _add_text_field(
                page, field_name, pymupdf.Rect(x, y - 12, x + width - 4, y + 4)
            )
            x += width

    page.draw_line((56, 370), (539, 370))
    for field_name, label, y in TOTAL_FIELDS:
        page.insert_text(
            (300, y),
            label,
            fontsize=9,
            fontname=THAI_FONT_NAME,
            fontfile=THAI_FONT_PATH,
        )
        _add_text_field(page, field_name, pymupdf.Rect(460, y - 12, 539, y + 4))

    page.insert_text(
        (56, 500),
        "ผู้บันทึก / Prepared by: ____________________",
        fontsize=9,
        fontname=THAI_FONT_NAME,
        fontfile=THAI_FONT_PATH,
    )
    page.insert_text(
        (56, 525),
        "ผู้อนุมัติ / Approved by: ____________________",
        fontsize=9,
        fontname=THAI_FONT_NAME,
        fontfile=THAI_FONT_PATH,
    )

    doc.subset_fonts()
    return doc.tobytes(deflate=True, garbage=4)


def main() -> None:
    out_dir = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    quote_path = out_dir / "demo_quote.pdf"
    form_path = out_dir / "demo_form.pdf"

    quote_path.write_bytes(build_quote_pdf())
    form_path.write_bytes(build_form_pdf())

    print(f"Wrote {quote_path} ({quote_path.stat().st_size} bytes)")
    print(f"Wrote {form_path} ({form_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
