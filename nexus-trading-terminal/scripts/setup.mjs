#!/usr/bin/env node
// One-time setup: Python venv + backend deps, npm deps, .env, database migrations.
import { execFileSync, spawnSync } from "node:child_process";
import { copyFileSync, existsSync } from "node:fs";
import path from "node:path";

import { IS_WIN, ROOT, SERVICES, VENV, pythonBin, pythonEnv } from "./lib.mjs";

const step = (msg) => console.log(`\n\x1b[36m[nexus]\x1b[0m ${msg}`);
const run = (cmd, args, opts = {}) => {
  const r = spawnSync(cmd, args, { stdio: "inherit", shell: IS_WIN && cmd.startsWith("npm"), ...opts });
  if (r.status !== 0) {
    console.error(`\n[nexus] Command failed: ${cmd} ${args.join(" ")}`);
    process.exit(r.status ?? 1);
  }
};

const [major, minor] = process.versions.node.split(".").map(Number);
if (major < 20 || (major === 20 && minor < 9)) {
  console.error(`[nexus] Node.js >= 20.9 is required (found ${process.versions.node}).`);
  process.exit(1);
}

step("Checking Python (3.11+ required)");
const systemPython = process.env.PYTHON ?? (IS_WIN ? "python" : "python3");
let version = "";
try {
  version = execFileSync(existsSync(VENV) ? pythonBin() : systemPython, ["-c", "import sys; print('%d.%d' % sys.version_info[:2])"]).toString().trim();
} catch {
  console.error(`[nexus] Could not run ${systemPython}. Install Python 3.11+ or set PYTHON=/path/to/python.`);
  process.exit(1);
}
const [pyMaj, pyMin] = version.split(".").map(Number);
if (pyMaj < 3 || (pyMaj === 3 && pyMin < 11)) {
  console.error(`[nexus] Python 3.11+ is required (found ${version}).`);
  process.exit(1);
}
console.log(`Python ${version}`);

if (!existsSync(VENV)) {
  step("Creating virtualenv at services/.venv");
  run(systemPython, ["-m", "venv", VENV]);
}

step("Installing backend dependencies");
run(pythonBin(), ["-m", "pip", "install", "--upgrade", "pip"], { cwd: SERVICES });
run(pythonBin(), ["-m", "pip", "install", "-r", path.join("api", "requirements-dev.txt")], { cwd: SERVICES });

step("Installing frontend dependencies");
run(IS_WIN ? "npm.cmd" : "npm", ["install"], { cwd: ROOT });

if (!existsSync(path.join(ROOT, ".env"))) {
  step("Creating .env from .env.example (DEMO mode: no keys needed)");
  copyFileSync(path.join(ROOT, ".env.example"), path.join(ROOT, ".env"));
}

step("Applying database migrations");
run(pythonBin(), ["-m", "app.cli", "migrate"], { cwd: SERVICES, env: pythonEnv() });

console.log(`
\x1b[32m[nexus] Setup complete.\x1b[0m

  npm run demo     seed DEMO data (~1-2 min) and start everything
  npm run dev      start API (:8000) + web (:3000)
  npm test         backend + frontend unit tests

Open http://localhost:3000
`);
