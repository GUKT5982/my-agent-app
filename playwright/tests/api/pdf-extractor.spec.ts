import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const tinyPdfBase64 = readFileSync(
  path.join(__dirname, "..", "..", "fixtures", "tiny.pdf.base64.txt"),
  "utf-8",
).trim();

test.describe("pdf_extractor graph via POST /runs/wait", () => {
  test("extracts embedded text from a valid PDF (fast path, no OCR)", async ({ request }) => {
    const res = await request.post("/runs/wait", {
      data: {
        assistant_id: "pdf_extractor",
        input: { pdf_base64: tinyPdfBase64 },
      },
    });
    expect(res.status()).toBe(200);

    const body = await res.json();
    expect(body.error).toBeNull();
    expect(body.page_count).toBe(1);
    expect(body.embedded_text_page_count).toBe(1);
    expect(body.ocr_page_count).toBe(0);
    expect(body.text).toContain("Hello Bruno API test");
    expect(body.text).toContain("Acme Co.");
  });

  test("returns a graceful error (HTTP 200) for an invalid/empty PDF payload", async ({
    request,
  }) => {
    const res = await request.post("/runs/wait", {
      data: {
        assistant_id: "pdf_extractor",
        input: { pdf_base64: "" },
      },
    });
    expect(res.status()).toBe(200);

    const body = await res.json();
    expect(body.page_count).toBe(0);
    expect(body.text).toBe("");
    expect(body.error).toBeTruthy();
    expect(body.error).toContain("not a valid PDF");
  });
});

test.describe("pdf_extractor graph via a persistent thread", () => {
  test("create thread -> run -> read back persisted state", async ({ request }) => {
    const createRes = await request.post("/threads", { data: {} });
    expect(createRes.status()).toBe(200);
    const { thread_id: threadId } = await createRes.json();
    expect(threadId).toBeTruthy();

    const runRes = await request.post(`/threads/${threadId}/runs/wait`, {
      data: {
        assistant_id: "pdf_extractor",
        input: { pdf_base64: "" },
      },
    });
    expect(runRes.status()).toBe(200);
    const runBody = await runRes.json();
    expect(runBody.error).toBeTruthy();

    const stateRes = await request.get(`/threads/${threadId}/state`);
    expect(stateRes.status()).toBe(200);
    const stateBody = await stateRes.json();

    expect(stateBody.values.error).toBe(runBody.error);
    expect(stateBody.values.page_count).toBe(0);
  });
});
