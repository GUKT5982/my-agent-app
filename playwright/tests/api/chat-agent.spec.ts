import { test, expect } from "@playwright/test";

// The "agent" graph calls Ollama's cloud model (OLLAMA_MODEL). On some
// networks outbound TLS to ollama.com is blocked, in which case the run
// still returns HTTP 200 but with a top-level "__error__" key instead of a
// real reply (see bruno/06 - Chat Agent docs). This test accepts either
// outcome and reports which one happened rather than hard-failing on a
// network condition outside the app's control.
test("POST /runs/wait on the agent graph replies or surfaces the known cloud-model error shape", async ({
  request,
}) => {
  const res = await request.post("/runs/wait", {
    data: {
      assistant_id: "agent",
      input: { changeme: "Say hello in one word" },
    },
  });
  expect(res.status()).toBe(200);

  const body = await res.json();
  if (body.__error__) {
    expect(body.__error__).toHaveProperty("error");
    expect(body.__error__).toHaveProperty("message");
    console.log(
      `[chat-agent] cloud model unreachable, got expected __error__ shape: ${JSON.stringify(body.__error__)}`,
    );
  } else {
    expect(body).toHaveProperty("changeme");
  }
});
