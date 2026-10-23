"use strict";

const { defineConfig } = require("@playwright/test");

const baseURL = process.env.E2E_BASE_URL || "http://127.0.0.1:8000";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined;

module.exports = defineConfig({
  testDir: "./tests/e2e",
  timeout: 60000,
  expect: { timeout: 10000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL,
    headless: true,
    viewport: { width: 1440, height: 900 },
    launchOptions: {
      executablePath,
      args: ["--no-sandbox", "--disable-dev-shm-usage"],
    },
  },
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "node server/server.js",
        url: baseURL + "/api/health",
        reuseExistingServer: true,
        timeout: 30000,
        env: { PORT: "8000", HOST: "127.0.0.1" },
      },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
