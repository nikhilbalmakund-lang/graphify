"use client";

import { useSyncExternalStore } from "react";

// One shared 1-second clock for every countdown / "x ago" label. The server
// snapshot is 0 so server and first client render agree (no hydration drift);
// callers render a placeholder while now === 0.
let current = 0;
let timer: ReturnType<typeof setInterval> | undefined;
const listeners = new Set<() => void>();

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  if (!timer) {
    current = Date.now();
    timer = setInterval(() => {
      current = Date.now();
      listeners.forEach((l) => l());
    }, 1000);
  }
  return () => {
    listeners.delete(fn);
    if (!listeners.size && timer) {
      clearInterval(timer);
      timer = undefined;
    }
  };
}

const getSnapshot = () => current;
const getServerSnapshot = () => 0;

/** Current epoch ms, ticking once per second (0 during SSR/hydration). */
export function useNow(): number {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
