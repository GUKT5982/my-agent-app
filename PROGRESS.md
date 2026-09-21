---
title: PDF Extraction & Quote-to-Form — Progress
project: my-agent-app
status: in-progress
created: 2026-09-11
updated: 2026-09-21
tags:
  - project/pdf-extractor
  - langgraph
  - status/in-progress
---

# ความคืบหน้าโปรเจกต์

> [!info] อัปเดตล่าสุด
> 2026-09-21 — ดูรายละเอียดการติดตั้ง/setup ทั้งหมดที่ [SETUP.txt](SETUP.txt)

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

> [!success] Git / Pull Request
> - งานทั้งหมดทำบน branch `feature/pdf-extraction-and-quote-to-form` (ไม่แตะ `master` โดยตรง)
> - 2026-09-21: **[PR #1](https://github.com/GUKT5982/my-agent-app/pull/1) merge เข้า `master` แล้ว** ด้วย merge commit `dfca519` — commit ทั้ง 14 ตัวยังอยู่ครบพร้อมวันที่เดิม branch เดิมยังไม่ได้ลบ

> [!tip] ทำไม contribution graph ถึงไม่ขึ้น (และวิธีแก้)
> 2026-09-21: กราฟบนโปรไฟล์ GitHub ไม่ขึ้นสีตามวันที่ทำงาน ทั้งที่ commit ครบ — **GitHub นับเฉพาะ commit ที่อยู่บน default branch (`master`) เท่านั้น** commit บน branch อื่นไม่นับจนกว่าจะ merge และการเปิด PR ค้างไว้เฉยๆ ก็ไม่นับ
> - เช็คว่า GitHub นับให้เท่าไหร่จริงๆ:
>   ```bash
>   gh api graphql -f query='{ viewer { contributionsCollection(from: "2026-09-01T00:00:00Z", to: "2026-09-21T23:59:59Z") { totalCommitContributions } } }'
>   ```
>   ก่อน merge ตอบ `3` หลัง merge ตอบ `17` (ขึ้นครบทั้ง 8 / 11 / 16 / 17 / 21 ก.ย.)
> - เช็คว่า email ผูกกับบัญชีหรือยัง (สาเหตุยอดฮิตอีกข้อ): `gh api repos/<owner>/<repo>/commits/<sha> --jq .author.login` ถ้าได้ `null` แปลว่าไม่ผูก
> - **ตอน merge ห้ามใช้ squash** ถ้าอยากให้กราฟกระจายตามวันจริง เพราะ squash ยุบเหลือ commit เดียวลงวันที่ merge ใช้ merge commit หรือ rebase แทน

---

## 📝 เหลือทำต่อ

> [!todo] งานหลักที่ยังไม่เสร็จ
> - [ ] **ทดสอบกับข้อมูลจริง** — ตอนนี้ทดสอบด้วยไฟล์ demo ที่สร้างขึ้นเอง (`demo_quote.pdf`, `demo_form.pdf`)
>   - [ ] ฟอร์ม PDF จริงที่จะใช้งานจริง (ต้องรู้ชื่อฟิลด์ AcroForm จริง เพื่อปรับ mapping)
>   - [ ] ใบเสนอราคาจริงจากผู้ขายจริง (โครงสร้าง/ภาษาอาจต่างจาก demo — Gemma extraction เป็น general-purpose แต่ควรทดสอบยืนยัน)
> - [ ] **รัน validate กับไฟล์ทั้งหมดใน `test_pdfs`** (1,077 ไฟล์, ~868MB) — ตอนนี้สุ่มทดสอบแค่บางไฟล์ ยังไม่ได้รันชุดเต็มด้วย `scripts/validate_pdf_extraction.py` (คาดว่าใช้เวลานาน เพราะ OCR ช้า)
>   - ผลที่ได้เอาไปเปิดใน `static/validation-dashboard/` ได้เลย จะบอกเองว่าควรไล่แก้อะไรก่อน และประมาณเวลาที่เหลือให้
> - [x] ~~Review และ merge PR #1~~ — merge แล้ว 2026-09-21

> [!warning] ปัญหา environment: port 2024 ใช้ไม่ได้ถาวร
> เจอ ghost process ค้างใน TCP table ของเครื่องที่ฆ่าไม่ตาย ตอนนี้ใช้ port 2777 แทนชั่วคราว (`langgraph dev --port 2777`)
> - [ ] ลอง restart เครื่อง (Windows) ดูว่า TCP table เคลียร์หรือไม่
> - [ ] ถ้ายังไม่หาย ให้ใช้ port อื่นที่ไม่เคยใช้มาก่อนทุกครั้งที่ restart server (อย่าใช้ port ซ้ำ)
>
> 2026-09-17 (เครื่อง KCG): เจออาการเดียวกันแต่รู้สาเหตุแล้ว — server ตัวเก่ายังไม่ตาย และ Windows ยอมให้ server ตัวใหม่ bind พอร์ต 2024 ซ้ำได้ request เลยยังวิ่งไปตัวเก่า server ที่ "restart แล้ว" จึงยังรันโค้ดเดิม
> - เช็คก่อนเทสต์ทุกครั้ง: `netstat -ano | findstr :2024` ต้องมีบรรทัด `LISTENING` แค่บรรทัดเดียว
> - ถ้ามีเกิน ให้ฆ่าทั้ง tree จาก process แม่ (`taskkill /PID <pid> /T /F`) ฆ่าแค่ตัวลูกไม่พอ
> - `langgraph dev` บนเครื่องนี้ไม่ reload เองเมื่อแก้ไฟล์ใน `src/` ต้อง restart ทุกครั้งหลังแก้โค้ด

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

## ไฟล์ที่เกี่ยวข้อง

- [SETUP.txt](SETUP.txt) — ขั้นตอนติดตั้งทั้งหมด (Ollama, Tesseract, dependencies)
- `src/agent/pdf_extraction.py` — core extraction logic
- `src/agent/pdf_graph.py` — LangGraph graph definition
- `src/agent/quote_extraction.py` — Gemma-based structured field parsing
- `src/agent/form_filling.py` — AcroForm filling logic
- `scripts/generate_form_demo.py` — สร้างไฟล์ตัวอย่างสำหรับทดสอบ
- `scripts/validate_pdf_extraction.py` — batch validation กับ corpus จริง
