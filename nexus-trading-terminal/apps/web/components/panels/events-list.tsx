"use client";

import type { EconomicEvent } from "@nexus/shared-types";

import { ImpactBadge } from "@/components/market/badges";
import { useNow } from "@/hooks/use-now";
import { fmtCountdown, fmtTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export function EventsList({ events, limit = 6 }: { events: EconomicEvent[]; limit?: number }) {
  const now = useNow();
  return (
    <ul className="flex flex-col divide-y divide-line/60">
      {events.slice(0, limit).map((e) => {
        const mins = now ? (new Date(e.time).getTime() - now) / 60000 : e.minutes_until;
        const soon = e.impact === "HIGH" && mins > 0 && mins <= 120;
        return (
          <li key={e.id} className={cn("flex items-center gap-2.5 py-1.5 text-xs", soon && "bg-down/5")}>
            <span className="num w-20 shrink-0 text-muted">{fmtTime(e.time, true)}</span>
            <span className="w-9 shrink-0 font-semibold text-fg">{e.currency}</span>
            <span className="min-w-0 flex-1 truncate text-fg">{e.event}</span>
            <ImpactBadge impact={e.impact} />
            <span className={cn("num w-16 shrink-0 text-right", soon ? "font-semibold text-down" : "text-muted")}>{mins > 0 ? fmtCountdown(mins) : "passed"}</span>
          </li>
        );
      })}
    </ul>
  );
}

/** "HIGH IMPACT EVENT IN: 1h 20m" banner from the spec. */
export function HighImpactWarning({ events }: { events: EconomicEvent[] }) {
  const now = useNow();
  if (!now) return null;
  const next = events
    .filter((e) => e.impact === "HIGH")
    .map((e) => ({ e, mins: (new Date(e.time).getTime() - now) / 60000 }))
    .filter((x) => x.mins > 0)
    .sort((a, b) => a.mins - b.mins)[0];
  if (!next || next.mins > 24 * 60) return null;
  return (
    <div role="status" className={cn("flex items-center gap-2 rounded-sm border px-3 py-2 text-xs", next.mins <= 120 ? "border-down/40 bg-down/10 text-down" : "border-warn/35 bg-warn/5 text-warn")}>
      <span className="font-bold uppercase tracking-wider">High impact event in:</span>
      <span className="num text-sm font-bold">{fmtCountdown(next.mins)}</span>
      <span className="truncate text-fg">
        {next.e.currency} · {next.e.event}
      </span>
      {next.e.is_demo ? <span className="ml-auto shrink-0 text-[0.62rem] font-semibold text-demo">DEMO</span> : null}
    </div>
  );
}
