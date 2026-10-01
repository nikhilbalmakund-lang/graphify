"use client";

import { useCallback, useSyncExternalStore } from "react";

// localStorage-backed state for per-browser UI conveniences (panel toggles,
// chart preferences). Never used for secrets or trading state.
const listeners = new Set<() => void>();

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  const onStorage = () => fn();
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(fn);
    window.removeEventListener("storage", onStorage);
  };
}

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function useLocalStorage<T>(key: string, initial: T): [T, (v: T | ((prev: T) => T)) => void] {
  const raw = useSyncExternalStore(
    subscribe,
    () => read(key),
    () => null,
  );
  let value = initial;
  if (raw !== null) {
    try {
      value = JSON.parse(raw) as T;
    } catch {
      value = initial;
    }
  }
  const set = useCallback(
    (v: T | ((prev: T) => T)) => {
      let prev = initial;
      const cur = read(key);
      if (cur !== null) {
        try {
          prev = JSON.parse(cur) as T;
        } catch {
          prev = initial;
        }
      }
      const next = typeof v === "function" ? (v as (p: T) => T)(prev) : v;
      try {
        window.localStorage.setItem(key, JSON.stringify(next));
      } catch {
        /* storage may be full or disabled */
      }
      listeners.forEach((l) => l());
    },
    // `initial` is a fallback literal; callers pass stable values.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [key],
  );
  return [value, set];
}
