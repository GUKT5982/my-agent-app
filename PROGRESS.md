# ความคืบหน้าโปรเจกต์

อัปเดตล่าสุด: 2026-09-11

## ✅ เสร็จแล้ว

### Phase 1 — PDF Text Extraction (`pdf_extractor` graph)
- ถอดข้อความจาก PDF อัตโนมัติ รองรับทั้งไฟล์ที่มี text layer อยู่แล้ว (ดึงตรงๆ เร็ว) และไฟล์สแกน/ภาพ (fallback ไป OCR)
- ตรวจจับ + แก้หน้าที่กลับหัว/หมุน 90/180/270° อัตโนมัติก่อน OCR (ใช้ Tesseract OSD)
- ยืนยันแล้วผ่าน API จริงใน LangGraph Studio (ไม่ใช่แค่ unit test) ทั้งเคสข้อความปกติและเคสกลับหัว
- ไฟล์หลัก: `src/agent/pdf_extraction.py`, `src/agent/pdf_graph.py`

### Phase 2 — Quote-to-Form Auto-fill
- ต่อยอด pipeline เดิม: `extract_pdf` → `extract_quote_fields` (ใช้ Gemma แกะข้อมูลเป็น JSON) → `fill_form` (ใช้ PyMuPDF กรอกลง AcroForm)
- ยืนยันสำเร็จผ่าน API จริง: แกะข้อมูลได้ครบทุกฟิลด์ (19/19) กรอกฟอร์มถูกต้อง ไม่มี field ตกหล่น
- ไฟล์หลัก: `src/agent/quote_extraction.py`, `src/agent/form_filling.py`, `scripts/generate_form_demo.py`

### Testing / Infra
- Unit tests 12/12 ผ่าน, `ruff check` + `mypy --strict` สะอาด (ยกเว้นปัญหาเดิมที่มีอยู่ก่อนหน้านี้ในโปรเจกต์ ไม่เกี่ยวกับงานนี้)
- สร้างเครื่องมือ **Payload Scanner** (web artifact) ช่วยแปลง PDF → base64 JSON payload สำหรับทดสอบใน Studio โดยไม่ต้องยุ่งกับ PowerShell/clipboard
- แก้ปัญหาไฟล์ demo ใหญ่เกินไป (~980KB → ~60KB ด้วย font subsetting) ที่เคยทำให้ copy-paste พัง

## 📝 เหลือทำต่อ

1. **ทดสอบกับข้อมูลจริง** — ตอนนี้ทดสอบด้วยไฟล์ demo ที่สร้างขึ้นเอง (`demo_quote.pdf`, `demo_form.pdf`) ยังไม่ได้ลองกับ:
   - ฟอร์ม PDF จริงที่จะใช้งานจริง (ต้องรู้ชื่อฟิลด์ AcroForm จริง เพื่อปรับ mapping)
   - ใบเสนอราคาจริงจากผู้ขายจริง (โครงสร้าง/ภาษาอาจต่างจาก demo — Gemma extraction เป็น general-purpose แต่ควรทดสอบยืนยัน)

2. **รัน validate กับไฟล์ทั้งหมดใน `test_pdfs`** (1,077 ไฟล์, ~868MB) — ตอนนี้สุ่มทดสอบแค่บางไฟล์ ยังไม่ได้รันชุดเต็มด้วย `scripts/validate_pdf_extraction.py` (คาดว่าใช้เวลานาน เพราะ OCR ช้า)

3. **ปัญหา environment: port 2024 ใช้ไม่ได้ถาวร** — เจอ ghost process ค้างใน TCP table ของเครื่องที่ฆ่าไม่ตาย ตอนนี้ใช้ port 2777 แทนชั่วคราว (`langgraph dev --port 2777`)
   - แนะนำ: ลอง restart เครื่อง (Windows) ดูว่า TCP table เคลียร์หรือไม่
   - ถ้ายังไม่หาย ให้ใช้ port อื่นที่ไม่เคยใช้มาก่อนทุกครั้งที่ restart server (อย่าใช้ port ซ้ำ)

4. **ยังไม่ได้ commit เข้า git** — งานทั้งหมด (ทั้งไฟล์ใหม่และแก้ไข) ยังอยู่ใน working tree เท่านั้น ดู `git status` เพื่อดูรายการ

5. **ปรับปรุงเพิ่มเติม (ถ้าต้องการ, ไม่เร่งด่วน)**
   - รองรับฟอร์มที่ชื่อฟิลด์ไม่ตรงกับ convention `item_N_desc/qty/price/amount` (ตอนนี้ fix ตาม pattern เดียวจาก demo)
   - เพิ่ม retry logic ถ้า Gemma ตอบ JSON ผิดรูปแบบ (ตอนนี้ fail แบบ graceful แต่ไม่ retry)
   - ปัญหาเทสต์ `@pytest.mark.langsmith` ที่ fail เพราะไม่มี LANGSMITH_API_KEY (pre-existing ก่อนงานนี้ ไม่กระทบ logic)

## คำสั่งอ้างอิงเร็วๆ

```powershell
# รัน server (ใช้ port 2777 เพราะ 2024 มีปัญหา)
cd C:\Users\Amaya\Desktop\agent\my-agent-app
langgraph dev --no-browser --port 2777

# รัน unit tests
python -m pytest tests/unit_tests/ -v

# สร้างไฟล์ demo ใหม่ (ถ้าลบไปแล้ว)
python scripts/generate_form_demo.py

# validate กับไฟล์จริงชุดเล็ก
make validate_pdf_sample
```

รายละเอียดการติดตั้ง/setup ทั้งหมดดูที่ [SETUP.txt](SETUP.txt)
