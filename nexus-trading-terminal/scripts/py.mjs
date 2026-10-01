#!/usr/bin/env node
// Run the project's Python with the correct PYTHONPATH and working directory.
//   node scripts/py.mjs -m pytest -q
//   node scripts/py.mjs -m app.cli serve
import { spawn } from "node:child_process";

import { SERVICES, pythonBin, pythonEnv } from "./lib.mjs";

const child = spawn(pythonBin(), process.argv.slice(2), { cwd: SERVICES, env: pythonEnv(), stdio: "inherit" });
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => child.kill(sig));
child.on("error", (err) => {
  console.error(`[nexus] could not start Python (${pythonBin()}): ${err.message}`);
  console.error("[nexus] run `npm run setup` first, or install Python 3.11+.");
  process.exit(1);
});
child.on("exit", (code, signal) => process.exit(signal ? 1 : (code ?? 1)));
