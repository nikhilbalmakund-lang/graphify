#!/usr/bin/env node
// Production-style local run: API (no reload) + `next start` on the built web app.
import { existsSync } from "node:fs";
import path from "node:path";

import { requireSetup } from "./checks.mjs";
import { IS_WIN, ROOT } from "./lib.mjs";
import { runAll } from "./run-both.mjs";

requireSetup();
if (!existsSync(path.join(ROOT, "apps", "web", ".next", "BUILD_ID"))) {
  console.error("[nexus] No production build found. Run `npm run build` first.");
  process.exit(1);
}
console.log("[nexus] Starting API on http://127.0.0.1:8000 and web on http://localhost:3000");
runAll([
  { name: "api", cmd: "node", args: ["scripts/py.mjs", "-m", "app.cli", "serve"], color: "36" },
  { name: "web", cmd: IS_WIN ? "npm.cmd" : "npm", args: ["run", "start", "-w", "@nexus/web"], color: "35" },
]);
