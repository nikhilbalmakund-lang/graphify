"use client";

import type { EconomicEvent, NewsItem, OverviewCard, PaperOverview, RiskStatus, ScannerRow, Signal } from "@nexus/shared-types";
import { CalendarClock, Gauge, LayoutGrid, Newspaper, Radar, ShieldCheck, Target, Zap } from "lucide-react";
import Link from "next/link";

import { BriefingPanel } from "@/components/ai/briefing-panel";
import { RiskNotice } from "@/components/common/disclaimer";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { Stat } from "@/components/common/stat";
import { DataBlock, EmptyState } from "@/components/common/states";
import { DirectionBadge, ModeBadge } from "@/components/market/badges";
import { MarketCard } from "@/components/market/market-card";
import { Signed } from "@/components/market/price";
import { EventsList, HighImpactWarning } from "@/components/panels/events-list";
import { NewsList } from "@/components/panels/news-list";
import { RiskSummary } from "@/components/panels/risk-summary";
import { SignalCard } from "@/components/signals/signal-card";
import { SignalTable } from "@/components/signals/signal-table";
import { usePaperTrade } from "@/components/signals/use-paper-trade";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useMediaQuery } from "@/hooks/use-media-query";
import { fmtMoney } from "@/lib/format";

function ViewAll({ href, label = "View all" }: { href: string; label?: string }) {
  return (
    <Link href={href} className="text-[0.68rem] text-muted hover:text-accent">
      {label} →
    </Link>
  );
}

/** Compact scanner list for phones (the desktop layout links to the full scanner instead). */
function MobileScanner() {
  const { data, error, isLoading, mutate } = useApi<{ rows: ScannerRow[] }>("/api/scanner?timeframe=15m", 60_000);
  return (
    <Panel>
      <PanelHeader title="Market scanner" icon={<Radar />} subtitle="15m · ranked by signal score" actions={<ViewAll href="/scanner" />} />
      <DataBlock data={data} error={error} isLoading={isLoading} onRetry={() => mutate()} rows={5}>
        {(d) => (
          <ul className="divide-y divide-line/60">
            {d.rows.slice(0, 6).map((r) => (
              <li key={r.symbol}>
                <Link href={`/signals/${r.signal_id}`} className="flex items-center gap-2 px-3 py-2 text-xs">
                  <span className="w-16 font-semibold text-fg">{r.symbol}</span>
                  <DirectionBadge direction={r.direction} />
                  <span className="truncate text-muted">{r.regime.replace(/_/g, " ").toLowerCase()}</span>
                  <span className="num ml-auto text-accent">{r.score.toFixed(0)}</span>
                  <span className="text-[0.6rem] text-faint">/100</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </DataBlock>
    </Panel>
  );
}

export function DashboardView() {
  const isMobile = useMediaQuery("(max-width: 1023px)");
  const overview = useApi<{ mode: string; is_demo: boolean; cards: OverviewCard[] }>("/api/market/overview?timeframe=1H", 30_000);
  const signals = useApi<Signal[]>("/api/signals?active=true&limit=50", 20_000);
  const events = useApi<EconomicEvent[]>("/api/calendar?hours_back=0&hours_ahead=72", 60_000);
  const news = useApi<NewsItem[]>("/api/news?limit=8", 60_000);
  const risk = useApi<RiskStatus>("/api/risk/status", 10_000);
  const paper = useApi<PaperOverview>("/api/paper-trading", 15_000);
  const { execute } = usePaperTrade();

  const active = (signals.data ?? []).filter((s) => s.direction !== "NO_TRADE");
  const top = [...active].sort((a, b) => b.score - a.score).slice(0, 3);
  const highEvents = (events.data ?? []).filter((e) => e.impact === "HIGH");

  return (
    <PageContainer>
      <PageHeader
        title="Dashboard"
        description="Market overview, qualifying setups, risk and context in one view. Every value is labelled with its data source."
        badges={overview.data ? <ModeBadge mode={overview.data.is_demo ? "DEMO" : "LIVE"} /> : null}
        actions={
          <>
            <Button asChild size="sm" variant="outline">
              <Link href="/scanner">
                <Radar /> Scanner
              </Link>
            </Button>
            <Button asChild size="sm" variant="primary">
              <Link href="/signals">
                <Zap /> Signals
              </Link>
            </Button>
          </>
        }
      />

      {events.data ? <HighImpactWarning events={events.data} /> : null}

      <section aria-labelledby="overview-h">
        <div className="mb-2 flex items-center gap-2">
          <LayoutGrid className="size-3.5 text-accent" />
          <h2 id="overview-h" className="text-[0.72rem] font-semibold uppercase tracking-[0.09em] text-fg">
            Market overview
          </h2>
          <span className="hidden text-[0.66rem] text-faint sm:inline">1H trend, volatility and regime</span>
          <span className="ml-auto">
            <ViewAll href="/markets" label="All markets" />
          </span>
        </div>
        {overview.error && !overview.data ? (
          <DataBlock data={undefined} error={overview.error} isLoading={false} onRetry={() => overview.mutate()}>
            {() => null}
          </DataBlock>
        ) : (
          <div className="-mx-3 flex snap-x gap-2 overflow-x-auto px-3 pb-1 sm:mx-0 sm:grid sm:grid-cols-3 sm:overflow-visible sm:px-0 sm:pb-0 lg:grid-cols-4 2xl:grid-cols-5">
            {overview.data
              ? overview.data.cards.map((c) => (
                  <div key={c.symbol} className="w-[46%] shrink-0 snap-start sm:w-auto">
                    <MarketCard card={c} />
                  </div>
                ))
              : Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} className="h-[138px] w-[46%] shrink-0 sm:w-auto" />)}
          </div>
        )}
      </section>

      <div className="grid gap-3 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <BriefingPanel />
        </div>
        <Panel>
          <PanelHeader title="Risk status" icon={<ShieldCheck />} subtitle="Deterministic risk engine · paper account" actions={<ViewAll href="/portfolio" />} />
          <PanelBody>
            <DataBlock data={risk.data} error={risk.error} isLoading={risk.isLoading} onRetry={() => risk.mutate()}>
              {(r) => <RiskSummary risk={r} />}
            </DataBlock>
          </PanelBody>
        </Panel>
      </div>

      <section aria-labelledby="top-h">
        <div className="mb-2 flex items-center gap-2">
          <Target className="size-3.5 text-accent" />
          <h2 id="top-h" className="text-[0.72rem] font-semibold uppercase tracking-[0.09em] text-fg">
            Top opportunities
          </h2>
          <span className="hidden text-[0.66rem] text-faint sm:inline">Highest-scoring signals that passed every filter and the risk engine - not guaranteed outcomes</span>
          <span className="ml-auto">
            <ViewAll href="/signals" />
          </span>
        </div>
        {signals.data && !top.length ? (
          <Panel>
            <EmptyState icon={<Zap />} title="No qualifying setups right now" description="NO_TRADE is a valid and common outcome. The engine only issues signals when score, filters, historical evidence and risk checks all pass." />
          </Panel>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {signals.data ? top.map((s) => <SignalCard key={s.id} signal={s} compact onPaper={execute} />) : Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-80" />)}
          </div>
        )}
      </section>

      {isMobile ? <MobileScanner /> : null}

      <Panel>
        <PanelHeader title="Active signals" icon={<Zap />} subtitle={signals.data ? `${active.length} active` : undefined} actions={<ViewAll href="/signals" />} />
        <DataBlock data={signals.data} error={signals.error} isLoading={signals.isLoading} onRetry={() => signals.mutate()} isEmpty={() => !active.length} empty={<EmptyState title="No active signals" description="Signals appear here when a new bar produces a qualifying setup." />}>
          {() => <SignalTable signals={active} />}
        </DataBlock>
      </Panel>

      <div className="grid gap-3 lg:grid-cols-3">
        <Panel>
          <PanelHeader title="Economic events" icon={<CalendarClock />} subtitle="Next 72 hours" actions={<ViewAll href="/calendar" />} />
          <PanelBody>
            <DataBlock data={events.data} error={events.error} isLoading={events.isLoading} onRetry={() => events.mutate()} isEmpty={(d) => !d.length} empty={<EmptyState title="No scheduled events" />}>
              {(d) => (
                <>
                  <EventsList events={highEvents.length ? highEvents : d} limit={7} />
                  {d.some((e) => e.is_demo) ? <p className="mt-2 text-[0.62rem] text-demo">DEMO calendar - synthetic events, not real releases.</p> : null}
                </>
              )}
            </DataBlock>
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="News" icon={<Newspaper />} subtitle="Latest relevant headlines" actions={<ViewAll href="/news" />} />
          <PanelBody className="py-1">
            <DataBlock data={news.data} error={news.error} isLoading={news.isLoading} onRetry={() => news.mutate()} isEmpty={(d) => !d.length} empty={<EmptyState title="No news" />}>
              {(d) => <NewsList items={d} limit={6} />}
            </DataBlock>
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Paper portfolio" icon={<Gauge />} subtitle="SIMULATED - no real money" actions={<ViewAll href="/paper-trading" />} />
          <PanelBody>
            <DataBlock data={paper.data} error={paper.error} isLoading={paper.isLoading} onRetry={() => paper.mutate()}>
              {(p) => (
                <div className="flex flex-col gap-3">
                  <div className="grid grid-cols-2 gap-3">
                    <Stat label="Equity" value={fmtMoney(p.account.equity)} size="lg" />
                    <Stat label="Balance" value={fmtMoney(p.account.balance)} />
                    <Stat label="Open P&L" value={<Signed value={p.account.unrealized_pnl}>{fmtMoney(p.account.unrealized_pnl, 2, true)}</Signed>} />
                    <Stat label="Day P&L" value={<Signed value={p.risk.daily_pnl}>{fmtMoney(p.risk.daily_pnl, 2, true)}</Signed>} />
                  </div>
                  <div className="flex flex-col gap-1">
                    {p.positions.slice(0, 4).map((pos) => (
                      <div key={pos.id} className="flex items-center gap-2 text-xs">
                        <span className="w-16 font-semibold text-fg">{pos.symbol}</span>
                        <span className={pos.direction > 0 ? "text-up" : "text-down"}>{pos.direction > 0 ? "LONG" : "SHORT"}</span>
                        <span className="num text-muted">{pos.lots} lots</span>
                        <Signed value={pos.unrealized_pnl} className="ml-auto">
                          {fmtMoney(pos.unrealized_pnl, 2, true)}
                        </Signed>
                      </div>
                    ))}
                    {!p.positions.length ? <p className="text-xs text-faint">No open paper positions.</p> : null}
                  </div>
                  <ModeBadge mode="PAPER" className="self-start" />
                </div>
              )}
            </DataBlock>
          </PanelBody>
        </Panel>
      </div>
      <RiskNotice className="pb-2" />
    </PageContainer>
  );
}
