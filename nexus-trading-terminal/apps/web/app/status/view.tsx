"use client";

import type { SystemStatus } from "@nexus/shared-types";
import { Activity, Cpu, ListTree, ScrollText, ShieldAlert } from "lucide-react";

import { Callout } from "@/components/common/disclaimer";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { KV } from "@/components/common/stat";
import { DataBlock } from "@/components/common/states";
import { ConnBadge, ConnDot, ModeBadge } from "@/components/market/badges";
import { Badge } from "@/components/ui/badge";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { useLive } from "@/hooks/use-live";
import { useNow } from "@/hooks/use-now";
import { fmtDateTime, fmtNum, timeAgo, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

interface AuditEvent {
  id: number;
  ts: string;
  event_type: string;
  severity: string;
  source: string;
  message: string;
  request_id: string | null;
  signal_id: string | null;
}

export function StatusView() {
  const { data, error, isLoading, mutate } = useApi<SystemStatus>("/api/system/status", 10_000);
  const events = useApi<AuditEvent[]>("/api/system/events?limit=100", 15_000);
  const live = useLive();
  const now = useNow();
  const skew = data && now ? (new Date(data.server_time).getTime() - now) / 1000 : null;

  return (
    <PageContainer>
      <PageHeader
        title="System Status"
        description="Every integration with its real state. Failures are shown, never hidden: CONNECTED · DEMO · NOT CONFIGURED · DISCONNECTED · ERROR."
        badges={data ? <ModeBadge mode={data.mode} /> : null}
      />
      {error && !data ? (
        <Callout tone="down" title="Backend: DISCONNECTED">
          The NEXUS API is not reachable from the web server. Start it with <code>npm run dev</code> (or <code>npm run dev:api</code>) and check port 8000.
        </Callout>
      ) : null}
      <DataBlock data={data} error={error} isLoading={isLoading} onRetry={() => mutate()} rows={10}>
        {(d) => (
          <>
            <Panel>
              <PanelHeader title="Connections" icon={<Activity />} subtitle={`${d.app_name} v${d.version} · trading mode ${d.trading_mode}`} />
              <Table>
                <THead>
                  <tr>
                    <TH>Component</TH>
                    <TH>Status</TH>
                    <TH>Provider / model</TH>
                    <TH>Detail</TH>
                    <TH align="right">Latency</TH>
                  </tr>
                </THead>
                <tbody>
                  <TR>
                    <TD className="font-medium">
                      <span className="flex items-center gap-2">
                        <ConnDot status="CONNECTED" /> Frontend
                      </span>
                    </TD>
                    <TD>
                      <ConnBadge status="CONNECTED" />
                    </TD>
                    <TD className="text-xs text-muted">Next.js</TD>
                    <TD className="text-xs text-muted">Serving this page; proxies /api to the backend</TD>
                    <TD />
                  </TR>
                  <TR>
                    <TD className="font-medium">
                      <span className="flex items-center gap-2">
                        <ConnDot status={live.status} /> Live stream
                      </span>
                    </TD>
                    <TD>
                      <ConnBadge status={live.status === "open" ? "CONNECTED" : live.status === "connecting" ? "CONFIGURED_UNVERIFIED" : "DISCONNECTED"} />
                    </TD>
                    <TD className="text-xs text-muted">WebSocket /ws</TD>
                    <TD className="text-xs text-muted">{live.status === "open" ? `Last message ${live.lastMessageAt && now ? `${Math.max(0, Math.round((now - live.lastMessageAt) / 1000))}s ago` : "—"}` : "Falling back to REST polling for quotes"}</TD>
                    <TD />
                  </TR>
                  {d.components.map((c) => (
                    <TR key={c.name}>
                      <TD className="font-medium">
                        <span className="flex items-center gap-2">
                          <ConnDot status={c.status} /> {c.name}
                        </span>
                      </TD>
                      <TD>
                        <ConnBadge status={c.status} />
                      </TD>
                      <TD className="text-xs text-muted">{c.provider ?? "—"}</TD>
                      <TD className={cn("whitespace-normal text-xs", c.status === "ERROR" || c.status === "DISCONNECTED" ? "text-down" : "text-muted")}>{c.detail}</TD>
                      <TD align="right" className="num text-muted">
                        {c.latency_ms !== null ? `${fmtNum(c.latency_ms, 0)}ms` : "—"}
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            </Panel>

            <div className="grid gap-3 xl:grid-cols-3">
              <Panel>
                <PanelHeader title="Live trading gate" icon={<ShieldAlert />} />
                <PanelBody className="flex flex-col gap-2 text-xs">
                  <Badge tone={d.live_trading.allowed ? "solidDown" : "up"} className="self-start">
                    {d.live_trading.allowed ? "LIVE EXECUTION ARMED" : "LIVE EXECUTION DISABLED"}
                  </Badge>
                  <KV k="LIVE_TRADING_ENABLED (server env)" v={d.live_trading.env_enabled ? "true" : "false"} />
                  <KV k="UI safety switch" v={d.live_trading.ui_switch_on ? "ON" : "OFF"} />
                  <KV k="Broker" v={d.live_trading.broker} />
                  <ul className="list-disc pl-4 text-muted">
                    {d.live_trading.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </PanelBody>
              </Panel>
              <Panel>
                <PanelHeader title="Versions" icon={<Cpu />} />
                <PanelBody className="flex flex-col text-xs">
                  {Object.entries(d.versions).map(([k, v]) => (
                    <KV key={k} k={titleCase(k)} v={v} />
                  ))}
                  <KV k="Server time" v={fmtDateTime(d.server_time)} />
                  <KV k="Clock skew vs browser" v={skew === null ? "—" : `${skew >= 0 ? "+" : ""}${skew.toFixed(1)}s`} />
                </PanelBody>
              </Panel>
              <Panel>
                <PanelHeader title="Setup memory" icon={<ListTree />} subtitle={`State: ${d.memory.state}`} />
                <PanelBody className="flex flex-col gap-1 text-xs">
                  {d.memory.pending?.length ? <p className="text-warn">Pending: {d.memory.pending.join(", ")}</p> : null}
                  {d.memory.errors?.length ? d.memory.errors.map((e) => <p key={e.key} className="text-down">{e.key}: {e.error}</p>) : null}
                  {(d.memory.built ?? []).slice(0, 12).map((b) => (
                    <KV key={b.key} k={b.key} v={`${b.records} new`} />
                  ))}
                </PanelBody>
              </Panel>
            </div>

            <Panel>
              <PanelHeader title="Background jobs" icon={<Activity />} />
              <Table>
                <THead>
                  <tr>
                    <TH>Job</TH>
                    <TH align="right">Interval</TH>
                    <TH align="right">Runs</TH>
                    <TH align="right">Errors</TH>
                    <TH>Last run</TH>
                    <TH>Last error</TH>
                  </tr>
                </THead>
                <tbody>
                  {Object.entries(d.background).map(([k, j]) => (
                    <TR key={k}>
                      <TD className="font-medium">{titleCase(k)}</TD>
                      <TD align="right" className="num text-muted">
                        {j.interval_s ? `${j.interval_s}s` : "once"}
                      </TD>
                      <TD align="right" className="num">
                        {j.runs}
                      </TD>
                      <TD align="right" className={cn("num", j.errors ? "text-down" : "text-muted")}>
                        {j.errors}
                      </TD>
                      <TD className="num text-muted">{j.last_run && now ? timeAgo(j.last_run, now) : "—"}</TD>
                      <TD className="max-w-96 truncate text-xs text-down">{j.last_error ?? ""}</TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            </Panel>
          </>
        )}
      </DataBlock>

      <Panel>
        <PanelHeader title="Audit log" icon={<ScrollText />} subtitle="Signals, AI calls, orders, risk events, settings changes and errors" />
        <DataBlock data={events.data} error={events.error} isLoading={events.isLoading} onRetry={() => events.mutate()}>
          {(rows) => (
            <div className="max-h-96 overflow-y-auto">
              <Table>
                <THead>
                  <tr>
                    <TH>Time (UTC)</TH>
                    <TH>Severity</TH>
                    <TH>Type</TH>
                    <TH>Source</TH>
                    <TH>Message</TH>
                  </tr>
                </THead>
                <tbody>
                  {rows.map((e) => (
                    <TR key={e.id}>
                      <TD className="num text-muted">{fmtDateTime(e.ts).replace(" UTC", "")}</TD>
                      <TD>
                        <Badge tone={e.severity === "ERROR" ? "down" : e.severity === "WARNING" ? "warn" : "neutral"}>{e.severity}</Badge>
                      </TD>
                      <TD className="text-xs">{e.event_type}</TD>
                      <TD className="text-xs text-muted">{e.source}</TD>
                      <TD className="whitespace-normal text-xs text-fg">{e.message}</TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            </div>
          )}
        </DataBlock>
      </Panel>
    </PageContainer>
  );
}
