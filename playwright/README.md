# Playwright tests

Two projects, both driven by one `playwright.config.ts`:

- **api** — mirrors the manual checks in [`../bruno`](../bruno) using
  Playwright's `request` fixture (no browser — plain HTTP against the
  LangGraph server).
- **ui** — drives a real Chromium browser against two static pages for the
  `pdf_extractor` graph:
  [`../static/pdf-tester/index.html`](../static/pdf-tester/index.html) (pick
  a quote PDF, optionally a form template, run the extraction) and
  [`../static/pdf-tester/form-result.html`](../static/pdf-tester/form-result.html)
  (a separate page showing the extracted fields as an auto-filled
  "quotation intake form", handed over via `localStorage` after a
  quote-to-form run). The config auto-starts a static file server for both.

## Prerequisites

Start the LangGraph dev server first (from the repo root) — this is not
auto-started by the config, since it's a long-running dev process:

```powershell
langgraph dev --no-browser --port 2024
```

## Run

```powershell
cd playwright
npm install
npx playwright install chromium   # first time only
npx playwright test
```

Run just one project: `npx playwright test --project=api` or `--project=ui`.

Point at a different LangGraph server with `LANGGRAPH_BASE_URL` (defaults to
`http://localhost:2024`); point the ui project's static server at a
different port with `PDF_TESTER_PORT` (defaults to `5544`):

```powershell
$env:LANGGRAPH_BASE_URL = "http://localhost:2777"
npx playwright test
```

View the HTML report after a run: `npx playwright show-report`.

## Coverage

- `tests/api/server.spec.ts` — health check, server info, assistant listing
  (Bruno 01-03)
- `tests/api/pdf-extractor.spec.ts` — `pdf_extractor` graph: valid
  embedded-text PDF, invalid/empty payload, and the full create-thread → run
  → read-state flow (Bruno 04, 05, 07-09)
- `tests/api/chat-agent.spec.ts` — `agent` graph; accepts either a real reply
  or the known `__error__` shape returned when the Ollama cloud model is
  unreachable (Bruno 06)
- `tests/ui/pdf-tester.spec.ts` — the manual test pages end-to-end: extracts
  text from `demo_quote.pdf` on the index page, shows an inline error for an
  unreadable file, runs the full quote-to-form auto-fill flow with
  `demo_form.pdf` and follows the "View auto-filled form" link to
  `form-result.html` (only tolerates the one known
  Ollama-cloud-unreachable error shape there — any other error fails the
  test), checks `form-result.html`'s empty state when opened with no prior
  run, and a mocked-API test that verifies the intake-form fields
  (vendor/quote no/date/buyer/line items/totals) on `form-result.html` are
  actually populated correctly from `extracted_fields`, independent of
  whether the real model is reachable

## Bug this suite found (now fixed)

Uploading a non-PDF file through the UI came back as a *successful*
extraction instead of an error. The open step only rejected a 0-page
PyMuPDF result when the input bytes were also empty, and PyMuPDF's repair
mode does not reject non-PDF input at all: handed an HTML file it returned
a document with fabricated pages (23 of them for a 10KB page), each then
rasterized and OCR'd as if it were a real scan. The form-template side had
the same hole: a non-PDF template came back, without any error or warning,
as a "filled form" of fabricated pages that also got saved to disk.

Both now go through `open_pdf` in `src/agent/pdf_extraction.py`, which
requires the `%PDF-` header (searched in the first 1KB, so PDFs with
leading junk still open) before handing bytes to PyMuPDF. Covered by
`test_extract_non_pdf_file_is_rejected`,
`test_extract_tolerates_junk_before_pdf_header` and
`test_fill_rejects_non_pdf_template`.
