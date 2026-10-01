"use client";

import { Menu, OctagonAlert, PanelRight, Search } from "lucide-react";
import Link from "next/link";

import { ConnDot, ModeBadge } from "@/components/market/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tip } from "@/components/ui/tooltip";
import { useLive } from "@/hooks/use-live";
import { brand } from "@/lib/brand";
import { cn } from "@/lib/utils";

import { UtcClock } from "./clock";
import { NotificationsMenu } from "./notifications-menu";
import { componentStatus, useRiskStatus, useSystemStatus } from "./use-system";

function StatusPill({ label, status, detail }: { label: string; status: string; detail?: string }) {
  return (
    <Tip content={detail ? `${label}: ${status.replace(/_/g, " ")} - ${detail}` : `${label}: ${status.replace(/_/g, " ")}`}>
      <Link href="/status" className="flex items-center gap-1.5 rounded-sm px-1.5 py-1 text-[0.7rem] text-muted hover:bg-elevated hover:text-fg">
        <ConnDot status={status} />
        <span>{label}</span>
        <span className={cn("font-semibold", status === "CONNECTED" || status === "OK" ? "text-up" : status === "DEMO" ? "text-demo" : status === "NOT_CONFIGURED" ? "text-faint" : status === "CONFIGURED_UNVERIFIED" ? "text-info" : "text-down")}>
          {status === "NOT_CONFIGURED" ? "OFF" : status === "CONFIGURED_UNVERIFIED" ? "SET" : status}
        </span>
      </Link>
    </Tip>
  );
}

export function TopBar({ onOpenPalette, onOpenMenu, onToggleRight, rightOpen }: { onOpenPalette: () => void; onOpenMenu: () => void; onToggleRight: () => void; rightOpen: boolean }) {
  const { data: status, error } = useSystemStatus();
  const { data: risk } = useRiskStatus();
  const snap = useLive();
  const backendDown = Boolean(error) && !status;
  const detail = (n: string) => status?.components.find((c) => c.name === n)?.detail;
  const killed = risk?.kill_switch;

  return (
    <header className="flex h-11 shrink-0 items-center gap-2 border-b border-line bg-panel px-2 sm:px-3">
      <Button variant="ghost" size="icon" className="lg:hidden" onClick={onOpenMenu} aria-label="Open navigation menu">
        <Menu />
      </Button>
      <Link href="/" className="flex shrink-0 items-center gap-2 rounded-sm pr-2" aria-label={`${brand.name} - dashboard`}>
        <span className="grid size-6 place-items-center rounded-sm border border-accent/50 bg-accent/10 font-mono text-[0.7rem] font-bold text-accent">N</span>
        <span className="hidden flex-col leading-none sm:flex">
          <span className="text-[0.8rem] font-bold tracking-[0.18em] text-fg-strong">{brand.short}</span>
          <span className="text-[0.55rem] uppercase tracking-[0.14em] text-faint">Trading Intelligence</span>
        </span>
      </Link>

      <button
        type="button"
        onClick={onOpenPalette}
        className="ml-1 flex h-7 min-w-0 flex-1 items-center gap-2 rounded-sm border border-line bg-panel-2 px-2 text-left text-xs text-faint transition-colors hover:border-line-strong sm:max-w-72"
        aria-label="Search and commands"
      >
        <Search className="size-3.5 shrink-0" />
        <span className="truncate">Search assets, signals, commands…</span>
        <kbd className="ml-auto hidden rounded-xs border border-line px-1 font-mono text-[0.6rem] sm:inline">/</kbd>
      </button>

      <div className="ml-auto hidden items-center gap-0.5 xl:flex">
        {backendDown ? (
          <StatusPill label="Backend" status="DISCONNECTED" detail="The NEXUS API is not reachable" />
        ) : (
          <>
            <StatusPill label="Data" status={componentStatus(status, "Market Data")} detail={detail("Market Data")} />
            <StatusPill label="Claude" status={componentStatus(status, "Claude")} detail={detail("Claude")} />
            <StatusPill label="Gemini" status={componentStatus(status, "Gemini")} detail={detail("Gemini")} />
            <Tip content={`Live updates (WebSocket): ${snap.status}${snap.status !== "open" ? " - falling back to polling" : ""}`}>
              <span className="flex items-center gap-1.5 px-1.5 text-[0.7rem] text-muted">
                <ConnDot status={snap.status} /> Stream
              </span>
            </Tip>
          </>
        )}
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-1.5 xl:ml-2">
        {status ? <ModeBadge mode={status.mode} /> : null}
        <ModeBadge mode="PAPER" title="Trading mode: PAPER. Orders are simulated; live execution is disabled." />
        {status?.live_trading.allowed ? (
          <Badge tone="solidDown">LIVE TRADING ARMED</Badge>
        ) : null}
        {killed ? (
          <Tip content="Emergency kill switch is active: no new paper orders. Release it on the Paper Trading page.">
            <Link href="/paper-trading" className="flex items-center gap-1 rounded-xs bg-down px-1.5 py-0.5 text-[0.62rem] font-bold uppercase tracking-wider text-white">
              <OctagonAlert className="size-3" /> Kill switch
            </Link>
          </Tip>
        ) : risk && risk.state !== "NORMAL" ? (
          <Tip content={risk.messages.join(" · ") || `Risk engine ${risk.state}`}>
            <Link href="/portfolio">
              <Badge tone={risk.state === "HALTED" ? "solidDown" : "warn"}>Risk {risk.state}</Badge>
            </Link>
          </Tip>
        ) : null}
        <UtcClock className="hidden px-1 text-[0.7rem] md:block" />
        <NotificationsMenu />
        <Button variant="ghost" size="icon" className="hidden xl:inline-flex" onClick={onToggleRight} aria-pressed={rightOpen} aria-label="Toggle intelligence panel">
          <PanelRight />
        </Button>
      </div>
    </header>
  );
}

export function DemoBanner() {
  const { data } = useSystemStatus();
  if (!data || data.mode !== "DEMO") return null;
  return (
    <div role="status" className="flex h-6 shrink-0 items-center justify-center gap-2 border-b border-demo/30 bg-demo/10 px-3 text-center text-[0.68rem] text-demo">
      <span className="font-bold tracking-wider">DEMO MODE</span>
      <span className="hidden text-demo/80 sm:inline">Simulated prices, news and calendar - not real market data.</span>
      <Link href="/settings" className="underline underline-offset-2 hover:text-fg">
        Connect providers
      </Link>
    </div>
  );
}
