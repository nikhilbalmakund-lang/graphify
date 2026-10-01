#!/usr/bin/env node
// Start the API for end-to-end tests with a fresh, isolated database and no
// developer keys: forces DEMO mode and never touches .env or .secrets.env.
import { spawn } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import path from "node:path";

import { ROOT, SERVICES, pythonBin, pythonEnv } from "./lib.mjs";

const dir = path.join(ROOT, "data", "e2e");
rmSync(dir, { recursive: true, force: true });
mkdirSync(dir, { recursive: true });

const env = pythonEnv({
  NEXUS_ENV_FILE: path.join(dir, "none.env"),
  NEXUS_SECRETS_FILE: path.join(dir, "secrets.env"),
  DATABASE_URL: `sqlite:///${path.join(dir, "e2e.db")}`,
  LOG_JSON: "false",
  CORS_ORIGINS: "http://127.0.0.1:3100,http://localhost:3100",
  BUILD_MEMORY_ON_STARTUP: "false",
  SIGNAL_SCAN_INTERVAL_SECONDS: "3600",
  RATE_LIMIT_BACKTEST_PER_MINUTE: "100",
  RATE_LIMIT_AI_PER_MINUTE: "100",
});
for (const k of ["ANTHROPIC_API_KEY", "GEMINI_API_KEY", "MARKET_DATA_API_KEY", "NEWS_API_KEY", "ECONOMIC_CALENDAR_API_KEY", "BROKER_API_KEY", "BROKER_API_SECRET"]) delete env[k];

const child = spawn(pythonBin(), ["-m", "app.cli", "serve"], { cwd: SERVICES, env, stdio: "inherit" });
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => child.kill(sig));
child.on("exit", (code) => process.exit(code ?? 1));
