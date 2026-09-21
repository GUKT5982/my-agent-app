import { test, expect } from "@playwright/test";
import path from "node:path";

const quotePdf = path.join(__dirname, "..", "..", "..", "demo_quote.pdf");
const formPdf = path.join(__dirname, "..", "..", "..", "demo_form.pdf");

test.describe("PDF tester page (static/pdf-tester/index.html)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("extracts text from a quote PDF with no form template", async ({ page }) => {
    await page.locator("#quoteFile").setInputFiles(quotePdf);
    await page.locator("#runBtn").click();

    await expect(page.locator("#status")).toHaveAttribute("data-state", "ok", {
      timeout: 15_000,
    });
    await expect(page.locator("#errorBox")).toBeHidden();

    await expect(page.locator("#pageCount")).toHaveText("1");
    await expect(page.locator("#embeddedPageCount")).toHaveText("1");
    await expect(page.locator("#ocrPageCount")).toHaveText("0");

    // The demo quote is a Thai-language quotation; assert on the plain-ASCII
    // grand total so the check doesn't depend on Unicode normalization.
    await expect(page.locator("#extractedText")).toContainText("87,954.00");

    // No form template was supplied, so the quote-to-form section stays hidden.
    await expect(page.locator("#fieldsSection")).toBeHidden();
  });

  test("shows an inline error for an unreadable file", async ({ page }) => {
    await page.locator("#quoteFile").setInputFiles(
      path.join(__dirname, "..", "..", "fixtures", "not-a-pdf.txt"),
    );
    await page.locator("#runBtn").click();

    await expect(page.locator("#status")).toHaveAttribute("data-state", "error", {
      timeout: 15_000,
    });
    await expect(page.locator("#extractedText")).toContainText("not a valid PDF");
  });

  test("runs the quote-to-form flow and links to a separate result page", async ({ page }) => {
    await page.locator("#quoteFile").setInputFiles(quotePdf);
    await page.locator("#formFile").setInputFiles(formPdf);
    await page.locator("#runBtn").click();

    // Extraction itself always succeeds for this fixture; the quote-to-form
    // step depends on reaching the Ollama cloud model, which may or may not
    // be reachable on this network - assert on what's guaranteed either way.
    await expect(page.locator("#status")).toHaveAttribute("data-state", /ok|error/, {
      timeout: 30_000,
    });
    await expect(page.locator("#fieldsSection")).toBeVisible();
    await expect(page.locator("#viewFormLink")).toBeVisible();

    await page.locator("#viewFormLink").click();
    await expect(page).toHaveURL(/form-result\.html$/);
    await expect(page.locator("#resultView")).toBeVisible();
    await expect(page.locator("#emptyState")).toBeHidden();

    const fieldsJson = await page.locator("#fieldsJson").textContent();
    expect(fieldsJson).toBeTruthy();
    const fields = JSON.parse(fieldsJson ?? "{}");

    if (fields.error) {
      // Only tolerate the model being unreachable, which is an environment
      // condition rather than an app defect - either the local Ollama isn't
      // running ("All connection attempts failed") or it is, but outbound
      // TLS to ollama.com is blocked (see bruno/06 and chat-agent.spec.ts).
      // Anything else - a bad JSON reply, a field-mapping bug - is a real
      // regression and must fail here, not be silently swallowed.
      expect(fields.error, `unexpected quote-field extraction error: ${fields.error}`).toMatch(
        /ollama\.com|tls: handshake failure|ResponseError|all connection attempts failed|connect(ion)? (refused|failed)/i,
      );
      console.log(`[ui] quote-field model call blocked by network, as expected: ${fields.error}`);
      await expect(page.locator("#fieldsErrorNote")).toBeVisible();
      await expect(page.locator("#ff_vendor")).toHaveValue("");
    } else {
      expect(fields.grand_total).toContain("87,954");
      await expect(page.locator("#ff_grand_total")).toHaveValue(fields.grand_total);
      await expect(page.locator("#downloadFilledForm")).toBeVisible();
    }
  });

  test("shows the empty state when opened with no prior result", async ({ page }) => {
    await page.goto("/form-result.html");
    await expect(page.locator("#emptyState")).toBeVisible();
    await expect(page.locator("#resultView")).toBeHidden();
  });

  test("populates the intake-form fields from a successful extraction (mocked API)", async ({
    page,
  }) => {
    // The real quote-to-form flow depends on reaching the Ollama cloud
    // model, which this network blocks (see the test above), so the
    // "values actually land in the right on-page fields" behavior would
    // otherwise never run here. Mocking /runs/wait with a canned success
    // response makes this deterministic and independent of the model.
    await page.route("**/runs/wait", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          error: null,
          page_count: 1,
          embedded_text_page_count: 1,
          ocr_page_count: 0,
          warnings: [],
          text: "--- page 1 ---\nmocked",
          record_id: 42,
          extracted_fields: {
            vendor_name: "Acme Co.",
            quote_no: "QT-2026-0142",
            quote_date: "08/09/2026",
            buyer_name: "Agent Technology Co.",
            items: [
              { description: "Office Chair", qty: "10", unit_price: "2,500.00", amount: "25,000.00" },
              { description: "Office Desk", qty: "10", unit_price: "4,200.00", amount: "42,000.00" },
            ],
            subtotal: "82,200.00",
            vat: "5,754.00",
            grand_total: "87,954.00",
            error: null,
          },
          fill_warnings: [],
          filled_form_base64: "",
        }),
      });
    });

    await page.locator("#quoteFile").setInputFiles(quotePdf);
    await page.locator("#formFile").setInputFiles(formPdf);
    await page.locator("#runBtn").click();
    await expect(page.locator("#status")).toHaveAttribute("data-state", "ok", { timeout: 10_000 });

    await page.locator("#viewFormLink").click();
    await expect(page).toHaveURL(/form-result\.html$/);

    await expect(page.locator("#fieldsErrorNote")).toBeHidden();
    await expect(page.locator("#ff_vendor")).toHaveValue("Acme Co.");
    await expect(page.locator("#ff_quote_no")).toHaveValue("QT-2026-0142");
    await expect(page.locator("#ff_quote_date")).toHaveValue("08/09/2026");
    await expect(page.locator("#ff_buyer")).toHaveValue("Agent Technology Co.");
    await expect(page.locator("#ff_subtotal")).toHaveValue("82,200.00");
    await expect(page.locator("#ff_vat")).toHaveValue("5,754.00");
    await expect(page.locator("#ff_grand_total")).toHaveValue("87,954.00");

    // The intake form always renders at least 3 line-item rows (matching
    // the paper form's layout), padding with blank rows past the data.
    const itemRows = page.locator("#itemsBody tr");
    await expect(itemRows).toHaveCount(3);
    await expect(itemRows.nth(0).locator("input").nth(0)).toHaveValue("Office Chair");
    await expect(itemRows.nth(0).locator("input").nth(3)).toHaveValue("25,000.00");
    await expect(itemRows.nth(1).locator("input").nth(0)).toHaveValue("Office Desk");
    await expect(itemRows.nth(2).locator("input").nth(0)).toHaveValue("");
  });
});
