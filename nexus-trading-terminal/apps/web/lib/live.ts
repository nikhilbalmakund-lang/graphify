"use client";

import type { LiveMessage, Quote } from "@nexus/shared-types";

export type LiveStatus = "idle" | "connecting" | "open" | "closed";

export interface LiveSnapshot {
  status: LiveStatus;
  quotes: Record<string, Quote>;
  lastMessageAt: number | null;
  mode: string | null;
}

type Handler = (data: unknown) => void;

function wsUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_WS_URL;
  if (fromEnv) return fromEnv;
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const port = process.env.NEXT_PUBLIC_API_PORT ?? "8000";
  return `${proto}://${window.location.hostname}:${port}/ws`;
}

/** Single shared WebSocket connection with automatic reconnect (exponential backoff). */
class LiveClient {
  private ws: WebSocket | null = null;
  private retry = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private listeners = new Set<() => void>();
  private handlers = new Map<string, Set<Handler>>();
  private refs = 0;
  snapshot: LiveSnapshot = { status: "idle", quotes: {}, lastMessageAt: null, mode: null };

  subscribe = (fn: () => void): (() => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };

  getSnapshot = (): LiveSnapshot => this.snapshot;

  private set(patch: Partial<LiveSnapshot>) {
    this.snapshot = { ...this.snapshot, ...patch };
    this.listeners.forEach((l) => l());
  }

  on(topic: string, handler: Handler): () => void {
    if (!this.handlers.has(topic)) this.handlers.set(topic, new Set());
    this.handlers.get(topic)!.add(handler);
    return () => this.handlers.get(topic)?.delete(handler);
  }

  /** Quotes from REST polling (used while the socket is down). */
  setQuotes(quotes: Quote[]) {
    const next = { ...this.snapshot.quotes };
    for (const q of quotes) next[q.symbol] = q;
    this.set({ quotes: next });
  }

  acquire() {
    this.refs += 1;
    if (this.refs === 1) this.connect();
  }

  release() {
    this.refs = Math.max(0, this.refs - 1);
    if (this.refs === 0) {
      if (this.timer) clearTimeout(this.timer);
      this.ws?.close();
      this.ws = null;
    }
  }

  private connect() {
    if (typeof window === "undefined") return;
    this.set({ status: "connecting" });
    let ws: WebSocket;
    try {
      ws = new WebSocket(wsUrl());
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;
    ws.onopen = () => {
      this.retry = 0;
      this.set({ status: "open" });
    };
    ws.onmessage = (ev) => {
      let msg: LiveMessage;
      try {
        msg = JSON.parse(ev.data as string) as LiveMessage;
      } catch {
        return;
      }
      const patch: Partial<LiveSnapshot> = { lastMessageAt: Date.now() };
      if (msg.topic === "quotes" && Array.isArray(msg.data)) {
        const next = { ...this.snapshot.quotes };
        for (const q of msg.data as Quote[]) next[q.symbol] = q;
        patch.quotes = next;
      }
      if (msg.topic === "system" && msg.data && typeof msg.data === "object" && "mode" in msg.data) {
        patch.mode = String((msg.data as { mode: string }).mode);
      }
      this.set(patch);
      this.handlers.get(msg.topic)?.forEach((h) => h(msg.data));
    };
    ws.onclose = () => {
      if (this.ws === ws) {
        this.ws = null;
        this.set({ status: "closed" });
        if (this.refs > 0) this.scheduleReconnect();
      }
    };
    ws.onerror = () => ws.close();
  }

  private scheduleReconnect() {
    if (this.timer) clearTimeout(this.timer);
    const delay = Math.min(15000, 1000 * 2 ** this.retry);
    this.retry += 1;
    this.timer = setTimeout(() => this.connect(), delay);
  }
}

export const live: LiveClient = typeof window !== "undefined" ? new LiveClient() : (null as unknown as LiveClient);
