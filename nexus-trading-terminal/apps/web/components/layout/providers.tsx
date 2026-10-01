"use client";

import type { NotificationItem, Quote } from "@nexus/shared-types";
import { useEffect } from "react";
import { toast, Toaster } from "sonner";
import { SWRConfig, useSWRConfig } from "swr";

import { TooltipProvider } from "@/components/ui/tooltip";
import { useApi } from "@/hooks/use-api";
import { useLive, useLiveTopic } from "@/hooks/use-live";
import { live } from "@/lib/live";

import { useSettings } from "./use-system";

/** Keeps quotes flowing: WebSocket first, REST polling while the socket is down. */
function LiveBridge() {
  const { mutate } = useSWRConfig();
  const snap = useLive();
  const { data: settings } = useSettings();

  useEffect(() => {
    live.acquire();
    return () => live.release();
  }, []);

  const polling = snap.status !== "open";
  const { data: polled } = useApi<Quote[]>("/api/market/quotes", polling ? 4000 : 0);
  useEffect(() => {
    if (polled) live.setQuotes(polled);
  }, [polled]);

  const revalidate = (prefix: string) => mutate((key) => typeof key === "string" && key.startsWith(prefix));

  useLiveTopic("notifications", (raw) => {
    const n = raw as Omit<NotificationItem, "read">;
    void revalidate("/api/notifications");
    const fn = n.severity === "ERROR" ? toast.error : n.severity === "WARNING" ? toast.warning : toast.info;
    fn(n.title, { description: n.is_demo ? `${n.body} · DEMO DATA` : n.body });
    const browserOn = Boolean(settings?.settings?.notifications?.browser_enabled);
    if (browserOn && typeof Notification !== "undefined" && Notification.permission === "granted" && document.hidden) {
      try {
        new Notification(n.title, { body: n.body, tag: `nexus-${n.id}` });
      } catch {
        /* some browsers only allow notifications from a service worker */
      }
    }
  });
  useLiveTopic("signals", () => {
    void revalidate("/api/signals");
    void revalidate("/api/scanner");
  });
  useLiveTopic("paper", () => {
    void revalidate("/api/paper-trading");
    void revalidate("/api/portfolio");
    void revalidate("/api/risk");
    void revalidate("/api/journal");
  });
  useLiveTopic("system", (raw) => {
    const d = raw as { event?: string; active?: boolean };
    if (d?.event === "KILL_SWITCH") {
      void revalidate("/api/risk");
      void revalidate("/api/paper-trading");
      toast.warning(d.active ? "Emergency kill switch ACTIVATED - all paper trading halted" : "Kill switch released");
    }
  });
  useLiveTopic("backtests", () => void revalidate("/api/backtests"));
  return null;
}

/** Mirrors Settings > Appearance onto <html> data attributes (accent, density, motion). */
function AppearanceSync() {
  const { data } = useSettings();
  const a = data?.settings?.appearance as { accent?: string; density?: string; reduce_motion?: boolean } | undefined;
  useEffect(() => {
    if (!a) return;
    const el = document.documentElement;
    el.dataset.accent = a.accent ?? "cyan";
    el.dataset.density = a.density ?? "compact";
    el.dataset.reduceMotion = String(Boolean(a.reduce_motion));
  }, [a]);
  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig value={{ revalidateOnFocus: false, dedupingInterval: 2000 }}>
      <TooltipProvider delayDuration={250}>
        {children}
        <LiveBridge />
        <AppearanceSync />
        <Toaster
          theme="dark"
          position="bottom-right"
          closeButton
          toastOptions={{
            classNames: {
              toast: "!bg-elevated !border !border-line-strong !text-fg !rounded-md !text-xs",
              description: "!text-muted",
            },
          }}
        />
      </TooltipProvider>
    </SWRConfig>
  );
}
