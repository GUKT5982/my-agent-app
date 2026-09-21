import { test, expect } from "@playwright/test";

test.describe("LangGraph server basics", () => {
  test("GET /ok reports the server is up", async ({ request }) => {
    const res = await request.get("/ok");
    expect(res.status()).toBe(200);
    expect(await res.json()).toEqual({ ok: true });
  });

  test("GET /info returns server/runtime metadata", async ({ request }) => {
    const res = await request.get("/info");
    expect(res.status()).toBe(200);

    const body = await res.json();
    expect(body).toHaveProperty("version");
    expect(body).toHaveProperty("flags");
    expect(body).toHaveProperty("host");
  });

  test("POST /assistants/search lists the registered graphs", async ({ request }) => {
    const res = await request.post("/assistants/search", {
      data: { limit: 10, offset: 0 },
    });
    expect(res.status()).toBe(200);

    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);

    const graphIds = body.map((assistant: { graph_id: string }) => assistant.graph_id);
    expect(graphIds).toEqual(expect.arrayContaining(["agent", "pdf_extractor"]));
  });
});
