---
title: PDF Extraction & Quote-to-Form — Progress
project: my-agent-app
status: in-progress
created: 2026-09-11
updated: 2026-09-28
tags:
  - project/pdf-extractor
  - langgraph
  - status/in-progress
---

# ความคืบหน้าโปรเจกต์

> [!info] อัปเดตล่าสุด
> 2026-09-28 — ดูรายละเอียดการติดตั้ง/setup ทั้งหมดที่ [SETUP.txt](SETUP.txt)

---

## ✅ เสร็จแล้ว

> [!success] Phase 1 — PDF Text Extraction (`pdf_extractor` graph)
> - ถอดข้อความจาก PDF อัตโนมัติ รองรับทั้งไฟล์ที่มี text layer อยู่แล้ว (ดึงตรงๆ เร็ว) และไฟล์สแกน/ภาพ (fallback ไป OCR)
> - ตรวจจับ + แก้หน้าที่กลับหัว/หมุน 90/180/270° อัตโนมัติก่อน OCR (ใช้ Tesseract OSD)
> - ยืนยันแล้วผ่าน API จริงใน LangGraph Studio (ไม่ใช่แค่ unit test) ทั้งเคสข้อความปกติและเคสกลับหัว
> - ไฟล์หลัก: `src/agent/pdf_extraction.py`, `src/agent/pdf_graph.py`

> [!success] Phase 2 — Quote-to-Form Auto-fill
> - ต่อยอด pipeline เดิม: `extract_pdf` → `extract_quote_fields` (ใช้ Gemma แกะข้อมูลเป็น JSON) → `fill_form` (ใช้ PyMuPDF กรอกลง AcroForm)
> - ยืนยันสำเร็จผ่าน API จริง: แกะข้อมูลได้ครบทุกฟิลด์ (19/19) กรอกฟอร์มถูกต้อง ไม่มี field ตกหล่น
> - ไฟล์หลัก: `src/agent/quote_extraction.py`, `src/agent/form_filling.py`, `scripts/generate_form_demo.py`

> [!success] Testing / Infra
> - pytest 31 ผ่าน / 3 skip (skip มีเหตุผลกำกับ: Ollama ไม่ได้รัน 2, ไม่มีคอร์ปัส `test_pdfs` 1) / 0 fail, `ruff check` + `mypy --strict` สะอาด
> - Playwright suite (`playwright/`): API 7 + UI 5 เทสต์ ครอบ Bruno collection และหน้า `static/pdf-tester/`
> - 2026-09-17: แก้บั๊กไฟล์ที่ไม่ใช่ PDF (เช่น HTML) ถูกรายงานว่าถอดสำเร็จ — PyMuPDF สร้างหน้าปลอมแล้วโดน OCR ทีละหน้า ตอนนี้บังคับเช็ค `%PDF-` header ทั้งไฟล์ใบเสนอราคาและ form template (เดิม template ที่ไม่ใช่ PDF ได้ "ฟอร์มที่กรอกแล้ว" เป็นหน้าขยะกลับมาและถูกบันทึกลงดิสก์ โดยไม่มีคำเตือน)
> - 2026-09-17: เทสต์ OCR 3 ตัวเคยถูก skip เงียบๆ เพราะ pytest ไม่ได้โหลด `TESSERACT_CMD` จาก `.env` — แก้แล้ว รันจริงและผ่าน
> - สร้างเครื่องมือ **Payload Scanner** (web artifact) ช่วยแปลง PDF → base64 JSON payload สำหรับทดสอบใน Studio โดยไม่ต้องยุ่งกับ PowerShell/clipboard
> - แก้ปัญหาไฟล์ demo ใหญ่เกินไป (~980KB → ~60KB ด้วย font subsetting) ที่เคยทำให้ copy-paste พัง

> [!success] Phase 3 — เครื่องมือช่วยพัฒนา (2026-09-21)
> หน้าเว็บไฟล์เดียวทั้งหมด เปิดจากดิสก์ได้เลย ไม่ต้องมี server/build ดูสรุปที่ [static/README.md](static/README.md)
> - **Validation Dashboard** (`static/validation-dashboard/`) — อ่านผล `validate_pdf_extraction.py` แล้วแยกไฟล์เป็น 4 กลุ่ม จุดสำคัญคือกลุ่ม **น่าสงสัย** (ไม่มี error แต่แทบไม่ได้ข้อความ) ซึ่ง JSON ดิบมองไม่เห็นเพราะ `error` เป็น `null` เหมือนไฟล์ที่ผ่านจริง + จัดกลุ่ม error ตามจำนวนไฟล์ที่โดน + ประมาณเวลารันคอร์ปัสเต็ม
> - **Field Mapper** (`scripts/inspect_form_fields.py` + `static/field-mapper/`) — dump ชื่อฟิลด์ AcroForm จริงพร้อมบอกว่าโค้ดจับคู่ได้เองกี่ฟิลด์ แล้วจับคู่ที่เหลือผ่านหน้าเว็บ export เป็น `form_mapping.json`
> - **Quote Review & Scoreboard** (`scripts/export_quote_records.py` + `static/quote-review/`) — ตรวจผลการแกะทีละฟิลด์ ได้คะแนนรายฟิลด์ (เรียงจากแย่สุด = ลำดับที่ควรแก้ prompt) และชุดเฉลย รายการที่แกะไม่ได้เพราะ infra ถูกแยกไม่นับคะแนน
> - **`scripts/score_extraction.py`** — เทียบผลรอบใหม่กับชุดเฉลยอัตโนมัติ จับคู่ด้วย `quote_no` เทียบตัวเลขเป็นตัวเลข (`1,200.00` = `1200`)
> - **`scripts/record_test_run.py`** — เก็บผลรันเทสต์เป็น JSON แล้วสร้าง [docs/test-reports/index.html](docs/test-reports/index.html) ใหม่ เห็นแนวโน้มข้ามรอบแทนที่จะเป็น snapshot รายวัน
> - เด็คนำเสนอ (Artifact) + [สคริปต์อัดวิดีโอ demo](docs/demo-script.md)
> - `make test_report` / `make export_quotes`

> [!success] รองรับฟอร์มที่ตั้งชื่อฟิลด์คนละ convention (2026-09-21)
> - `fill_pdf_form(..., field_map=...)` + context `form_mapping_path` — ไฟล์ mapping ถูกใช้ก่อน (เทียบชื่อตรง แล้วเทียบชื่อที่ normalize) ที่เหลือ fallback ไปจับคู่ตามชื่อแบบเดิม ไม่ใส่ = พฤติกรรมเดิมทุกประการ ไฟล์หาย/พัง = เตือนใน `fill_warnings` แล้วกรอกแบบเดิม
> - ฟอร์มทดสอบ 41 ช่องที่ชื่อ `qty1` / `Description 1` / `NET TOTAL`: จับได้เอง 1 ช่อง → หลังจับคู่ 39 ช่อง → กรอกจริงได้ 19 ฟิลด์ (เท่าจำนวนข้อมูลที่ใบเสนอราคามี) ช่องลงชื่อไม่ถูกแตะ
> - เทสต์ใหม่ 8 ตัวใน `tests/unit_tests/test_form_filling.py` รวมทั้งชุด **40 ผ่าน / 3 skip**

> [!success] 2026-09-28 — Ollama ใช้ได้แล้ว รันเทสต์ที่เคยติดได้ครบ + เจอบั๊กใหญ่ 1 ตัว
> Gemma cloud (`gemma4:31b-cloud`) เรียกได้แล้ว network ไม่บล็อกอีก เทสต์ที่เคย skip รันจริงผ่านหมด
> - **pytest 45 ผ่าน / 0 skip / 0 fail** (เดิม 40 ผ่าน 3 skip) + **Playwright 13 ผ่าน** (API 8 + UI 5 บน Chromium จริง) — `ruff` + `mypy --strict` สะอาด
> - chat agent (`agent` graph) ตอบจริงแล้ว ไม่ใช่ `__error__` อีก — เทสต์ที่เขียนเผื่อไว้สองทางตอนนี้เข้าทางที่ถูก
> - quote-to-form ผ่าน HTTP `/runs/wait` จริง: 2.7 วิ, 19/19 ฟิลด์, `fill_warnings` ว่าง, บันทึกลง `data/quotes.db` + เขียนไฟล์ฟอร์มลงดิสก์ครบ
> - ทดสอบ generalization ด้วยใบเสนอราคาที่หน้าตาต่างจาก demo: **ภาษาอังกฤษ label คนละแบบ (Invoice No / Bill To / Total Due), วันที่ MM/DD/YYYY, ไม่มี VAT → ถูกทุกฟิลด์** และไม่เดาข้อมูลที่ไม่มีในเอกสาร (ปล่อยว่างถูกต้อง)

> [!warning] บั๊กที่เจอและแก้แล้ว (2026-09-28): heuristic นับช่องว่างเป็นตัวหาร ทำให้ทิ้ง text layer ที่ดีไปใช้ OCR
> `_page_has_usable_text` หาร `alnum / len(stripped)` ซึ่ง **ตัวหารรวมช่องว่าง** เอกสารที่จัดคอลัมน์ด้วยช่องว่าง (ใบเสนอราคา/ตาราง/ฟอร์มราชการ แทบทุกใบ) จะมีช่องว่างเกินครึ่งหน้า อัตราเลยตกใต้ 0.5 → ถูกส่งไป OCR ทั้งที่ข้อความฝังสมบูรณ์ **และไม่มี warning เลย**
> - วัดกับคอร์ปัสจริงทั้ง 1,077 ไฟล์ (13,584 หน้า): **230 หน้าใน 63 ไฟล์โดนผลกระทบ** คิดเป็น 59% ของหน้าที่ระบบตัดสินใจ OCR ทั้งที่มีข้อความอยู่
> - ตัวอย่างความเสียหายจริง (`P6HR4OCK...pdf` ใบตอบประมูลรัฐ Alabama ทั้ง 5 หน้า): หน้า 1 จาก **3,897 ตัวอักษรเหลือ 1,417 — หายไป 64%** และ OCR อ่านเลขผิด (`22197` → `2219757`)
> - เอกสารไทยเสียหายหนักกว่า เพราะ OCR ใช้ `lang="eng"` ทับข้อความไทย ได้อักษรละตินที่อ่านไม่ออกแต่ดู "เหมือนจะถูก" (`ห้างหุ้นส่วนจำกัด ไทยเจริญวัสดุ` → `Weyuaruariia lnaatyian`) แล้วส่งต่อให้ Gemma แกะ
> - แก้โดยไม่นับช่องว่างในตัวหาร (ช่องว่างคือ layout ไม่ใช่เนื้อหา) **ผลหลังแก้: 230 หน้าใช้ text layer ถูกต้อง, 0 regression, กู้ข้อความจริงกลับมา 1,015,022 ตัวอักษร, ลดภาระ OCR 12%**
> - เพิ่มเทสต์กันถอยหลัง 2 ตัว: ตารางที่ padding ด้วยช่องว่างต้องใช้ text layer / text layer ที่เป็นสัญลักษณ์ขยะต้องยัง fallback ไป OCR
> - หมายเหตุ: ไฟล์ demo รอดบั๊กนี้มาตลอดเพราะวิธีสร้างไฟล์ (แยก `insert_text` ต่อ cell → ช่องว่างแค่ 11%) ต้องมีเอกสารจริงเท่านั้นจึงเจอ

> [!warning] บั๊กที่เจอและแก้แล้ว (2026-09-28): scoreboard match ใบเสนอราคาไม่เจอแบบเงียบๆ
> `score_extraction.py` จับคู่ใบเสนอราคาด้วย `quote_no` ดิบ แต่ PDF บางไฟล์รายงาน hyphen ที่วาดจริงเป็น U+00AD (soft hyphen มองไม่เห็น) และ Gemma บางรอบแปลงเป็น `-` บางรอบปล่อยผ่าน
> - ผลคือ **ใบเดียวกันคนละรอบได้ key ต่างกัน → หลุดไปอยู่ `missing_records` ไม่ถูกคิดคะแนน** โดยไม่มีอะไรเตือน ซึ่งขัดกับเหตุผลที่สร้างสคริปต์นี้มา
> - แก้โดยรวบ hyphen/dash ทุกแบบ (U+00AD, U+2010-2014) เป็น `-` และลบ zero-width ก่อนเทียบ ทั้งฝั่ง golden และฝั่ง record — ยืนยันแล้วว่าใบที่เคยหลุดกลับมาคิดคะแนนได้ 100%

> [!success] Git / Pull Request
> - Commit ทั้งหมดอยู่ใน branch `feature/pdf-extraction-and-quote-to-form` (ไม่แตะ `master` โดยตรง)
> - Push ขึ้น GitHub แล้ว และเปิด PR ไว้ให้: **[PR #1](https://github.com/GUKT5982/my-agent-app/pull/1)**
> - รอ review/merge จากผู้ใช้

---

## 📝 เหลือทำต่อ

> [!todo] งานหลักที่ยังไม่เสร็จ
> - [ ] **ทดสอบกับข้อมูลจริง** — ยังต้องใช้ไฟล์ของจริงจากงานจริง
>   - [ ] ฟอร์ม PDF จริงที่จะใช้งานจริง (ต้องรู้ชื่อฟิลด์ AcroForm จริง เพื่อปรับ mapping)
>   - [ ] ใบเสนอราคาจริงจากผู้ขายจริง — 2026-09-28 ทดสอบ generalization ด้วยใบที่หน้าตาต่างจาก demo แล้ว (label คนละแบบ, วันที่คนละ format, ไม่มี VAT, มีบรรทัดส่วนลดที่ schema ไม่มีช่อง, qty มีหน่วยติดมา) ผลดี แต่ยังเป็นไฟล์ที่เราสร้างเองอยู่
> - [ ] **รัน validate เต็มคอร์ปัส `test_pdfs` แบบมี OCR** (1,077 ไฟล์, ~868MB) ด้วย `scripts/validate_pdf_extraction.py` — ยังไม่ได้รัน เพราะ OCR ช้า
>   - 2026-09-28: วิเคราะห์ชั้น text layer ของทั้ง 1,077 ไฟล์ (13,584 หน้า) ไปแล้วแบบไม่ต้อง OCR — ใช้หาบั๊ก heuristic ข้างบนได้ ถ้าจะทำซ้ำ ดูสคริปต์วัดใน commit นี้
>   - ผลที่ได้เอาไปเปิดใน `static/validation-dashboard/` ได้เลย จะบอกเองว่าควรไล่แก้อะไรก่อน และประมาณเวลาที่เหลือให้
> - [ ] **Review และ merge PR #1**
> - [ ] พิจารณาเตือนเมื่อ OCR ทับหน้าที่มี text layer เยอะ แล้วได้ข้อความสั้นกว่าเดิมมาก — ตอนนี้ถ้า OCR ผิดภาษา จะได้ข้อความขยะที่ดู "เหมือนจะถูก" โดยไม่มีสัญญาณอะไรเลย (บั๊ก heuristic แก้ต้นเหตุหลักไปแล้ว แต่ safety net นี้ยังไม่มี)
> - [ ] พิจารณาให้ context ตั้ง `lang` ของ OCR ตามภาษาเอกสารได้ง่ายขึ้น / ใช้ `tha+eng` เป็นค่าเริ่มต้นสำหรับงานเอกสารไทย

> [!note] port 2024 — 2026-09-28 ใช้ได้ปกติแล้ว (แต่ยังต้องเช็คก่อนเทสต์)
> เครื่องนี้ (Amaya) ตอนนี้ port 2024 ว่างสะอาด ghost entry หายไปแล้ว (น่าจะเพราะ restart เครื่อง) `langgraph dev --no-browser --port 2024` ขึ้นปกติ มี `LISTENING` แค่บรรทัดเดียว **ไม่ต้องใช้ port 2777 แล้ว**
> - ยังควรเช็คก่อนเทสต์ทุกครั้ง: `netstat -ano | findstr :2024` ต้องมีบรรทัด `LISTENING` แค่บรรทัดเดียว
> - ถ้ามีเกิน ให้ฆ่าทั้ง tree จาก process แม่ (`taskkill /PID <pid> /T /F`) ฆ่าแค่ตัวลูกไม่พอ
> - `langgraph dev` ไม่ reload เองเมื่อแก้ไฟล์ใน `src/` ต้อง restart ทุกครั้งหลังแก้โค้ด
>
> 2026-09-17 (เครื่อง KCG): server ตัวเก่ายังไม่ตาย และ Windows ยอมให้ตัวใหม่ bind พอร์ตซ้ำได้ request เลยยังวิ่งไปตัวเก่า server ที่ "restart แล้ว" จึงยังรันโค้ดเดิม

> [!warning] ถ้า `langgraph dev` ขึ้นไม่ได้และฟ้อง `.langgraph_retry_counter.pckl` — ลบโฟลเดอร์ `.langgraph_api/`
> 2026-09-28: เจอ startup ตายด้วย `FileNotFoundError: '.langgraph_api\.langgraph_retry_counter.pckl'` → `Application startup failed. Exiting.` พร้อมกับ watchfiles ยัง reload ต่อ ทำให้ดูเหมือน server รันอยู่แต่ตอบอะไรไม่ได้ (คนละเรื่องกับปัญหา port ด้านบน แต่มีอาการคล้ายกันจนสับสนได้)
> - สาเหตุคือบั๊กใน `langgraph_runtime_inmem/database.py`: cache เก่าโหลดไม่ได้ → โค้ดกู้คืนสั่ง `os.remove()` ทั้งไฟล์ ops และไฟล์ retry counter แต่ไม่เช็คว่ามีอยู่จริง ตัวที่ไม่มีจึงทำให้ทั้ง startup ตาย
> - แก้ง่ายๆ: ลบ `.langgraph_api/` แล้วสตาร์ตใหม่ (เป็นแค่ cache ไม่มีข้อมูลธุรกิจ — ข้อมูลจริงอยู่ใน `data/quotes.db`) และ `.langgraph_api/` อยู่ใน `.gitignore` แล้ว
> - บน console ภาษาไทย/Windows ให้สตาร์ตด้วย `PYTHONIOENCODING=utf-8` ด้วย ไม่งั้น log จะพ่น `UnicodeEncodeError` (cp1252) รัวๆ กลบ error จริง

> [!warning] `uv sync` ใช้ไม่ได้บนเครื่อง KCG
> 2026-09-21: `uv sync` ล้มตอนสร้าง `jsonschema-rs` (dev dependency ที่มาจาก `langgraph-cli[inmem]`) เพราะต้องคอมไพล์ Rust แล้ว linker บนเครื่องนี้ error
> - ทางออกชั่วคราว: ลงเฉพาะที่ต้องใช้แบบไม่ผ่าน lock
>   ```powershell
>   uv pip install --python .venv\Scripts\python.exe langgraph python-dotenv langchain-ollama pymupdf pytesseract pillow opencv-python-headless ruff
>   uv pip install --python .venv\Scripts\python.exe -e . --no-deps
>   ```
> - หลังทำแล้ว `make test` / `make lint` ใช้ได้ แต่ `langgraph dev` ยังต้องใช้ `langgraph-cli` ซึ่งยังลงไม่ได้บนเครื่องนี้
> - [ ] หาทางแก้ถาวร (ลง Visual Studio Build Tools ให้ครบ หรือหา wheel สำเร็จรูปของ `jsonschema-rs`)

> [!note] ปรับปรุงเพิ่มเติม (ไม่เร่งด่วน)
> - [x] ชื่อฟิลด์ที่ต่างกันแค่รูปแบบ match ได้แล้ว (`Vendor Name` / `VENDOR-NAME` / `form1[0].page1[0].vendor_name[0]`) และฟิลด์ที่โผล่หลายที่ถูกกรอกครบทุกจุด
>   - [x] รองรับ convention ที่ต่างกันจริงๆ แล้ว (เช่น `qty1`, `Description 1`) ผ่านไฟล์ mapping จาก `static/field-mapper/` — แต่ยังทดสอบกับฟอร์มที่สร้างขึ้นจำลองเท่านั้น ยังไม่เคยเจอฟอร์มจริง
> - [x] Retry เมื่อ Gemma ตอบ JSON ผิดรูปแบบ (สูงสุด 3 ครั้ง ส่ง error กลับให้โมเดลเห็น เพราะ temperature=0 ส่ง prompt เดิมจะได้คำตอบเดิม) — ไม่ retry ถ้าเรียกโมเดลไม่ได้เลย และแก้ crash กรณีตอบ JSON ที่ไม่ใช่ object
> - [x] เทสต์ `@pytest.mark.langsmith` — ปิด LangSmith tracking เมื่อไม่มี API key เทสต์เลยรันจริงแทนที่จะ fail 401 ก่อนเริ่ม

---

## คำสั่งอ้างอิงเร็วๆ

```powershell
# รัน server (port 2024 ใช้ได้แล้ว ตั้ง UTF-8 กัน log พ่น error ภาษาไทย)
cd C:\Users\Amaya\Desktop\agent\my-agent-app
$env:PYTHONIOENCODING = "utf-8"
langgraph dev --no-browser --port 2024

# รันเทสต์ทั้งหมด (unit + integration)
python -m pytest tests/ -v

# รัน Playwright (ต้องมี server รันอยู่ก่อน)
cd playwright; npx playwright test

# สร้างไฟล์ demo ใหม่ (ถ้าลบไปแล้ว)
python scripts/generate_form_demo.py

# validate กับไฟล์จริงชุดเล็ก
make validate_pdf_sample
```

## ไฟล์ที่เกี่ยวข้อง

- [SETUP.txt](SETUP.txt) — ขั้นตอนติดตั้งทั้งหมด (Ollama, Tesseract, dependencies)
- `src/agent/pdf_extraction.py` — core extraction logic
- `src/agent/pdf_graph.py` — LangGraph graph definition
- `src/agent/quote_extraction.py` — Gemma-based structured field parsing
- `src/agent/form_filling.py` — AcroForm filling logic
- `scripts/generate_form_demo.py` — สร้างไฟล์ตัวอย่างสำหรับทดสอบ
- `scripts/validate_pdf_extraction.py` — batch validation กับ corpus จริง
