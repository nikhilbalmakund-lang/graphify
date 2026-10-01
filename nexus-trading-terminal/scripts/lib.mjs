// Shared helpers for the cross-platform npm scripts (macOS, Linux, Windows).
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const SERVICES = path.join(ROOT, "services");
export const VENV = path.join(SERVICES, ".venv");
export const IS_WIN = process.platform === "win32";

/** Python interpreter: the project venv when present, else the system one. */
export function pythonBin() {
  const venvPython = IS_WIN ? path.join(VENV, "Scripts", "python.exe") : path.join(VENV, "bin", "python");
  if (existsSync(venvPython)) return venvPython;
  if (process.env.PYTHON) return process.env.PYTHON;
  return IS_WIN ? "python" : "python3";
}

/** Environment for every Python process: both package roots on PYTHONPATH. */
export function pythonEnv(extra = {}) {
  const roots = [SERVICES, path.join(SERVICES, "api")];
  const existing = process.env.PYTHONPATH ? [process.env.PYTHONPATH] : [];
  return {
    ...process.env,
    PYTHONPATH: [...roots, ...existing].join(path.delimiter),
    PYTHONUNBUFFERED: "1",
    ...extra,
  };
}
