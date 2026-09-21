import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const langgraphBaseURL = process.env.LANGGRAPH_BASE_URL ?? "http://localhost:2024";
const uiPort = process.env.PDF_TESTER_PORT ?? "5544";
const uiBaseURL = `http://localhost:${uiPort}`;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  timeout: 30_000,
  // Serves static/pdf-tester/ (the manual test page) so the "ui" project
  // can navigate to it. The LangGraph dev server itself is NOT started
  // here - it's a separate long-running process (`langgraph dev`) the
  // suite assumes is already up, same as the "api" project.
  webServer: {
    command: `python -m http.server ${uiPort}`,
    cwd: path.join(__dirname, "..", "static", "pdf-tester"),
    url: uiBaseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 15_000,
  },
  projects: [
    {
      name: "api",
      testDir: "./tests/api",
      use: {
        baseURL: langgraphBaseURL,
        extraHTTPHeaders: { "Content-Type": "application/json" },
      },
    },
    {
      name: "ui",
      testDir: "./tests/ui",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: uiBaseURL,
      },
    },
  ],
});
