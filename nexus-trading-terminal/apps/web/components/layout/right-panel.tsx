"use client";

import type { EconomicEvent, Signal } from "@nexus/shared-types";
import { CalendarClock, ShieldCheck, Zap } from "lucide-react";
import Link from "next/link";

import { ConnBadge, DirectionBadge, ImpactBadge, ModeBadge } from "@/components/market/badges";
import { Progress } from "@/components/ui/progress";
import { useApi } from "@/hooks/use-api";
import { useNow } from "@/hooks/use-now";
import { fmtCountdown, fmtFrac, fmtMoney, fmtTime } from "@/lib/format";
import { cn } from "@/lib/utils";

import { componentStatus, useRiskStatus, useSystemStatus } from "./use-system";

function Section({ title, icon, href, children }: { title: string; icon: React.ReactNode; href?: string; children: React.ReactNode }) {
  return (
    <section className="border-b border-line px-3 py-3">
      <div className="mb-2 flex items-center gap-1.5">
        <span className="text-accent [&_svg]:size-3">{icon}</span>
        <h2 className="flex-1 text-[0.66rem] font-semibold uppercase tracking-[0.1em] text-fg">{title}</h2>
        {href ? (
          <Link href={href} className="text-[0.66rem] text-muted hover:text-accent">
            View all
          </Link>
        ) : null}
      </div>
      {children}
    </section>
  );
}

export function RightPanel() {
  const { data: risk } = useRiskStatus();
  const { data: status } = useSystemStatus();
  const { data: signals } = useApi<Signal[]>("/api/signals?active=true&limit=6", 30_000);
  const { data: events } = useApi<EconomicEvent[]>("/api/calendar?hours_back=0&hours_ahead=72&impact=HIGH", 60_000);
  const now = useNow();
  const minutesUntil = (iso: string) => (now ? (new Date(iso).getTime() - now) / 60000 : null);

  return (
    <aside aria-label="Intelligence panel" className="hidden w-72 shrink-0 overflow-y-auto border-l border-line bg-panel/50 xl:block">
      <Section title="Risk engine" icon={<ShieldCheck />} href="/portfolio">
        {risk ? (
          <div className="flex flex-col gap-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-muted">State</span>
              <span className={cn("font-semibold", risk.state === "NORMAL" ? "text-up" : risk.state === "HALTED" ? "text-down" : "text-warn")}>
                {risk.kill_switch ? "KILL SWITCH" : risk.state}
              </span>
            </div>
            <div>
              <div className="mb-1 flex justify-between">
                <span className="text-muted">Daily loss used</span>
                <span className="num">{fmtFrac(risk.daily_loss_used, 0)}</span>
              </div>
              <Progress value={risk.daily_loss_used * 100} tone={risk.daily_loss_used > 0.8 ? "down" : risk.daily_loss_used > 0.5 ? "warn" : "accent"} label="Daily loss limit used" />
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Drawdown</span>
              <span className="num">{fmtFrac(risk.drawdown, 2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Open risk</span>
              <span className="num">
                {fmtMoney(risk.open_risk_usd, 0)} · {risk.open_positions} pos
              </span>
            </div>
            <p className="text-[0.62rem] text-faint">Paper account · SIMULATED</p>
          </div>
        ) : (
          <p className="text-xs text-faint">Loading…</p>
        )}
      </Section>

      <Section title="Active signals" icon={<Zap />} href="/signals">
        {signals?.length ? (
          <ul className="flex flex-col gap-1">
            {signals.map((s) => (
              <li key={s.id}>
                <Link href={`/signals/${s.id}`} className="flex items-center gap-2 rounded-sm px-1.5 py-1 hover:bg-elevated">
                  <span className="w-14 text-xs font-semibold text-fg">{s.symbol}</span>
                  <DirectionBadge direction={s.direction} />
                  <span className="text-[0.66rem] text-faint">{s.timeframe}</span>
                  <span className="num ml-auto text-xs text-accent">{s.score.toFixed(0)}</span>
                  <span className="text-[0.6rem] text-faint">/100</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-faint">{signals ? "No active signals. NO_TRADE is a valid outcome." : "Loading…"}</p>
        )}
      </Section>

      <Section title="High-impact events" icon={<CalendarClock />} href="/calendar">
        {events?.length ? (
          <ul className="flex flex-col gap-2">
            {events.slice(0, 4).map((e) => {
              const mins = minutesUntil(e.time);
              return (
                <li key={e.id} className="text-xs">
                  <div className="flex items-center gap-1.5">
                    <ImpactBadge impact={e.impact} />
                    <span className="font-semibold text-fg">{e.currency}</span>
                    <span className="num ml-auto text-warn">{mins === null ? fmtTime(e.time) : mins > 0 ? `in ${fmtCountdown(mins)}` : "now"}</span>
                  </div>
                  <p className="mt-0.5 truncate text-muted">{e.event}</p>
                </li>
              );
            })}
            {events.some((e) => e.is_demo) ? <ModeBadge mode="DEMO" title="Synthetic calendar - not real economic events" /> : null}
          </ul>
        ) : (
          <p className="text-xs text-faint">{events ? "No high-impact events in the next 72h." : "Loading…"}</p>
        )}
      </Section>

      <Section title="Connections" icon={<ShieldCheck />} href="/status">
        <div className="flex flex-col gap-1.5 text-xs">
          {["Market Data", "Claude", "Gemini", "News", "Economic Calendar", "Paper Broker"].map((n) => (
            <div key={n} className="flex items-center justify-between">
              <span className="text-muted">{n}</span>
              <ConnBadge status={componentStatus(status, n)} />
            </div>
          ))}
        </div>
      </Section>
    </aside>
  );
}
