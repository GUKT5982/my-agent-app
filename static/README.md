# เครื่องมือหน้าเว็บ

หน้าเว็บไฟล์เดียวสำหรับงานที่ terminal ทำได้ไม่ดี — ทุกหน้าเปิดจากดิสก์ได้ตรงๆ (ดับเบิลคลิก)
ไม่ต้องมี server ไม่ต้อง build ไม่มี dependency และไม่ส่งข้อมูลออกนอกเครื่อง

| หน้า | ใช้ทำอะไร | ป้อนด้วย |
|---|---|---|
| [pdf-tester/](pdf-tester/) | ยิง PDF เข้า API แล้วดูผลที่ถอดได้ / ฟอร์มที่กรอกแล้ว | กรอกในหน้าเว็บ |
| [validation-dashboard/](validation-dashboard/) | อ่านผล validate คอร์ปัส PDF เป็นรายการงานเรียงตามผลกระทบ | `scripts/validate_pdf_extraction.py` |
| [field-mapper/](field-mapper/) | จับคู่ชื่อฟิลด์ของฟอร์มจริงกับค่าที่แกะได้ แล้ว export mapping | `scripts/inspect_form_fields.py` |
| [quote-review/](quote-review/) | ตรวจผลการแกะทีละฟิลด์ → คะแนนความแม่นยำ + ชุดเฉลย | `scripts/export_quote_records.py` |

ประวัติผลรันเทสต์อยู่คนละที่: [`docs/test-reports/index.html`](../docs/test-reports/index.html)
สร้างด้วย `scripts/record_test_run.py` (หน้านั้นฝังข้อมูลไว้ในตัว ไม่ต้องลากไฟล์)

วัดความแม่นยำของรอบถัดไปเทียบกับชุดเฉลยที่ตรวจไว้: `scripts/score_extraction.py`

แต่ละโฟลเดอร์มี README ของตัวเองอธิบายรายละเอียด
