"use client";

import { useSyncExternalStore } from "react";

/** Matches a CSS media query; false during SSR and the first client render. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (fn) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", fn);
      return () => mql.removeEventListener("change", fn);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}
