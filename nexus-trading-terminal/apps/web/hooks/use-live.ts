"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";

import { live, type LiveSnapshot } from "@/lib/live";

const SERVER_SNAPSHOT: LiveSnapshot = { status: "idle", quotes: {}, lastMessageAt: null, mode: null };

export function useLive(): LiveSnapshot {
  return useSyncExternalStore(
    (fn) => (live ? live.subscribe(fn) : () => undefined),
    () => (live ? live.getSnapshot() : SERVER_SNAPSHOT),
    () => SERVER_SNAPSHOT,
  );
}

export function useLiveQuote(symbol: string | null | undefined) {
  const snap = useLive();
  return symbol ? snap.quotes[symbol] : undefined;
}

/** Run a handler for every message on a topic (handler may change between renders). */
export function useLiveTopic(topic: string, handler: (data: unknown) => void) {
  const ref = useRef(handler);
  useEffect(() => {
    ref.current = handler;
  });
  useEffect(() => {
    if (!live) return;
    return live.on(topic, (d) => ref.current(d));
  }, [topic]);
}
