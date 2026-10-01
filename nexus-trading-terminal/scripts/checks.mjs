import { existsSync } from "node:fs";
import path from "node:path";

import { ROOT, VENV } from "./lib.mjs";

/** Fail fast with a helpful message when `npm run setup` has not been run. */
export function requireSetup() {
  const missing = [];
  if (!existsSync(VENV)) missing.push("Python virtualenv (services/.venv)");
  if (!existsSync(path.join(ROOT, "node_modules"))) missing.push("node_modules");
  if (missing.length) {
    console.error(`[nexus] Missing: ${missing.join(", ")}.\n[nexus] Run \`npm run setup\` first (one time).`);
    process.exit(1);
  }
  if (!existsSync(path.join(ROOT, ".env"))) {
    console.warn("[nexus] No .env file found - running with defaults (DEMO mode). Copy .env.example to .env to configure providers.");
  }
}
