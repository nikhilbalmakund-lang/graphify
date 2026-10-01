import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

// End-to-end tests run against the real stack in DEMO MODE: the FastAPI
// backend (fresh SQLite database) and a production build of the web app.
// Run `npm run build` first; the web server reuses that build.
const root = path.resolve(__dirname, "../..");

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } }, testIgnore: /mobile\.spec\.ts/ },
    { name: "mobile", use: { ...devices["Pixel 7"] }, testMatch: /mobile\.spec\.ts/ },
  ],
  webServer: [
    {
      command: "node scripts/py.mjs -m app.cli serve",
      cwd: root,
      url: "http://127.0.0.1:8000/health",
      timeout: 180_000,
      reuseExistingServer: false,
      env: {
        DATABASE_URL: "sqlite:///" + path.join(root, "data", "e2e.db"),
        LOG_JSON: "false",
        CORS_ORIGINS: "http://127.0.0.1:3100,http://localhost:3100",
        BUILD_MEMORY_ON_STARTUP: "false",
        SIGNAL_SCAN_INTERVAL_SECONDS: "3600",
      },
    },
    {
      command: "npx next start --port 3100 --hostname 127.0.0.1",
      cwd: __dirname,
      url: "http://127.0.0.1:3100",
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
});
