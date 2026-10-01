"use client";

import type { EconomicEvent } from "@nexus/shared-types";
import { CalendarClock, ShieldAlert } from "lucide-react";
import { Fragment, useState } from "react";

import { Callout } from "@/components/common/disclaimer";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { KV } from "@/components/common/stat";
import { DataBlock, EmptyState } from "@/components/common/states";
import { ImpactBadge, ModeBadge } from "@/components/market/badges";
import { Segmented, SymbolSelect } from "@/components/market/pickers";
import { HighImpactWarning } from "@/components/panels/events-list";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { useNow } from "@/hooks/use-now";
import { qs } from "@/lib/api";
import { fmtCountdown } from "@/lib/format";
import { cn } from "@/lib/utils";

interface EventRisk {
  available: boolean;
  is_demo: boolean;
  next_high_impact_minutes: number | null;
  next_high_impact_event: string | null;
  recent_high_impact_minutes: number | null;
  in_blackout: boolean;
  detail: string;
}

const RANGES = {
  today: { back: 12, ahead: 24, label: "±24h" },
  week: { back: 24, ahead: 168, label: "Next 7 days" },
  past: { back: 168, ahead: 1, label: "Past 7 days" },
} as const;

const CURRENCIES = ["", "USD", "EUR", "GBP", "JPY", "CNY", "AUD", "CAD", "CHF"];

function dayKey(iso: string) {
  return new Date(iso).toLocaleDateString("en-GB", { weekday: "long", day: "2-digit", month: "long", timeZone: "UTC" });
}

export function CalendarView() {
  const [range, setRange] = useState<keyof typeof RANGES>("week");
  const [impact, setImpact] = useState<"" | "HIGH" | "MEDIUM" | "LOW">("");
  const [currency, setCurrency] = useState("");
  const [symbol, setSymbol] = useState("XAUUSD");
  const r = RANGES[range];
  const { data, error, isLoading, mutate } = useApi<EconomicEvent[]>(`/api/calendar${qs({ hours_back: r.back, hours_ahead: r.ahead, impact, currency })}`, 60_000);
  const risk = useApi<EventRisk>(`/api/calendar/risk/${symbol}`, 60_000);
  const now = useNow();
  const isDemo = data?.some((e) => e.is_demo);

  const groups = new Map<string, EconomicEvent[]>();
  for (const e of data ?? []) {
    const k = dayKey(e.time);
    groups.set(k, [...(groups.get(k) ?? []), e]);
  }

  return (
    <PageContainer>
      <PageHeader
        title="Economic Calendar"
        description="Scheduled macro releases with impact, previous, forecast and actual values. High-impact events feed the signal engine's news-risk filter."
        badges={data ? <ModeBadge mode={isDemo ? "DEMO" : "LIVE"} title={isDemo ? "Synthetic calendar: not real economic events. Configure an economic calendar provider in Settings." : undefined} /> : null}
        actions={
          <>
            <Segmented label="Range" value={range} onChange={setRange} options={Object.entries(RANGES).map(([k, v]) => ({ value: k as keyof typeof RANGES, label: v.label }))} />
            <Segmented
              label="Impact"
              value={impact}
              onChange={setImpact}
              options={[
                { value: "", label: "All" },
                { value: "HIGH", label: "High" },
                { value: "MEDIUM", label: "Medium" },
                { value: "LOW", label: "Low" },
              ]}
            />
            <Select aria-label="Currency" value={currency} onChange={(e) => setCurrency(e.target.value)} className="h-7 w-24 text-xs">
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c || "All ccy"}
                </option>
              ))}
            </Select>
          </>
        }
      />
      {isDemo ? <Callout tone="warn" title="DEMO MODE calendar">These events are synthetic and generated for demonstration. They are not real economic releases and their values are not real data.</Callout> : null}
      {data ? <HighImpactWarning events={data} /> : null}

      <div className="grid gap-3 xl:grid-cols-[1fr_300px]">
        <Panel>
          <PanelHeader title="Events" icon={<CalendarClock />} subtitle={data ? `${data.length} events · times in UTC` : undefined} />
          <DataBlock data={data} error={error} isLoading={isLoading} onRetry={() => mutate()} rows={10} isEmpty={(d) => !d.length} empty={<EmptyState title="No events in this window" />}>
            {() => (
              <Table>
                <THead>
                  <tr>
                    <TH>Time</TH>
                    <TH>Ccy</TH>
                    <TH>Event</TH>
                    <TH>Impact</TH>
                    <TH align="right">Previous</TH>
                    <TH align="right">Forecast</TH>
                    <TH align="right">Actual</TH>
                    <TH align="right">In</TH>
                  </tr>
                </THead>
                <tbody>
                  {[...groups.entries()].map(([day, evs]) => (
                    <Fragment key={day}>
                      <tr>
                        <td colSpan={8} className="bg-panel-2 px-2.5 py-1 text-[0.66rem] font-semibold uppercase tracking-wider text-muted">
                          {day}
                        </td>
                      </tr>
                      {evs.map((e) => {
                        const mins = now ? (new Date(e.time).getTime() - now) / 60000 : e.minutes_until;
                        const high = e.impact === "HIGH";
                        return (
                          <TR key={e.id} className={cn(high && "bg-down/[0.06]")}>
                            <TD className="num text-muted">{new Date(e.time).toISOString().slice(11, 16)}</TD>
                            <TD className="font-semibold">{e.currency}</TD>
                            <TD className={cn("whitespace-normal", high ? "font-medium text-fg-strong" : "text-fg")}>
                              {e.event}
                              <span className="block text-[0.62rem] text-faint">
                                {e.country} · {e.source}
                              </span>
                            </TD>
                            <TD>
                              <ImpactBadge impact={e.impact} />
                            </TD>
                            <TD align="right" className="num text-muted">
                              {e.previous ?? "—"}
                            </TD>
                            <TD align="right" className="num">
                              {e.forecast ?? "—"}
                            </TD>
                            <TD align="right" className="num font-semibold text-fg-strong">
                              {e.actual ?? "—"}
                            </TD>
                            <TD align="right" className={cn("num", mins > 0 && mins < 120 && high ? "font-semibold text-down" : "text-muted")}>
                              {mins > 0 ? fmtCountdown(mins) : "released"}
                            </TD>
                          </TR>
                        );
                      })}
                    </Fragment>
                  ))}
                </tbody>
              </Table>
            )}
          </DataBlock>
        </Panel>
        <Panel>
          <PanelHeader title="Event risk by asset" icon={<ShieldAlert />} actions={<SymbolSelect value={symbol} onChange={setSymbol} className="h-7 text-xs" />} />
          <PanelBody className="flex flex-col gap-2 text-xs">
            <DataBlock data={risk.data} error={risk.error} isLoading={risk.isLoading}>
              {(d) => (
                <>
                  <Badge tone={d.in_blackout ? "solidDown" : "up"} className="self-start">
                    {d.in_blackout ? "In news blackout" : "No blackout"}
                  </Badge>
                  <KV k="Next high-impact" v={d.next_high_impact_event ?? "None scheduled"} mono={false} />
                  <KV k="Starts in" v={d.next_high_impact_minutes !== null ? fmtCountdown(d.next_high_impact_minutes) : "—"} />
                  <KV k="Last high-impact" v={d.recent_high_impact_minutes !== null ? `${fmtCountdown(d.recent_high_impact_minutes)} ago` : "—"} />
                  <p className="text-muted">{d.detail}</p>
                  <p className="text-[0.66rem] text-faint">The signal engine blocks new signals inside the configured blackout window around high-impact events for the asset&apos;s currencies.</p>
                </>
              )}
            </DataBlock>
          </PanelBody>
        </Panel>
      </div>
    </PageContainer>
  );
}
