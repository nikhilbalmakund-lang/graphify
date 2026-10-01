#!/usr/bin/env node
// One-command development: FastAPI (auto-reload) on :8000 + Next.js dev server on :3000.
import { requireSetup } from "./checks.mjs";
import { IS_WIN } from "./lib.mjs";
import { runAll } from "./run-both.mjs";

requireSetup();
console.log("[nexus] Starting API on http://127.0.0.1:8000 and web on http://localhost:3000 (Ctrl+C to stop)");
runAll([
  { name: "api", cmd: "node", args: ["scripts/py.mjs", "-m", "app.cli", "serve", "--reload"], color: "36" },
  { name: "web", cmd: IS_WIN ? "npm.cmd" : "npm", args: ["run", "dev", "-w", "@nexus/web"], color: "35" },
]);
