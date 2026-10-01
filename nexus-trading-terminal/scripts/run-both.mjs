// Run the API and the web app side by side with prefixed output (used by dev/start).
import { spawn, spawnSync } from "node:child_process";

import { IS_WIN, ROOT } from "./lib.mjs";

/** @param {{name: string, cmd: string, args: string[], color: string, env?: Record<string,string>}[]} procs */
export function runAll(procs) {
  const children = [];
  let exiting = false;
  // Kill each child's whole process tree (npm -> sh -> next, node -> python).
  const killTree = (child) => {
    if (child.exitCode !== null) return;
    if (IS_WIN) {
      spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    } else {
      try {
        process.kill(-child.pid, "SIGTERM");
      } catch {
        child.kill("SIGTERM");
      }
    }
  };
  const stopAll = (code) => {
    if (exiting) return;
    exiting = true;
    for (const c of children) killTree(c);
    setTimeout(() => process.exit(code), 800);
  };
  for (const p of procs) {
    const child = spawn(p.cmd, p.args, { cwd: ROOT, env: { ...process.env, FORCE_COLOR: "1", ...p.env }, shell: IS_WIN, detached: !IS_WIN, stdio: ["inherit", "pipe", "pipe"] });
    const prefix = `\x1b[${p.color}m[${p.name}]\x1b[0m `;
    const pipe = (stream, out) => {
      let buf = "";
      stream.on("data", (d) => {
        buf += d.toString();
        const lines = buf.split(/\r?\n/);
        buf = lines.pop() ?? "";
        for (const l of lines) out.write(prefix + l + "\n");
      });
    };
    pipe(child.stdout, process.stdout);
    pipe(child.stderr, process.stderr);
    child.on("exit", (code) => {
      if (!exiting) {
        console.error(`${prefix}exited with code ${code ?? "signal"}; stopping.`);
        stopAll(code ?? 1);
      }
    });
    children.push(child);
  }
  for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => stopAll(0));
}
