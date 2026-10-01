"use client";

import type { Portfolio } from "@nexus/shared-types";
import { PieChart, ShieldCheck, Wallet } from "lucide-react";

import { DrawdownChart, EquityChart, SignedBars } from "@/components/charts/recharts-kit";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { Stat } from "@/components/common/stat";
import { DataBlock, EmptyState } from "@/components/common/states";
import { ModeBadge } from "@/components/market/badges";
import { FlashPrice, Signed } from "@/components/market/price";
import { PerformanceSection } from "@/components/panels/performance";
import { RiskSummary } from "@/components/panels/risk-summary";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { fmtFrac, fmtMoney, fmtNum, fmtPrice } from "@/lib/format";
import { decimate } from "@/lib/series";

export function PortfolioView() {
  const { data, error, isLoading, mutate } = useApi<Portfolio>("/api/portfolio", 10_000);
  return (
    <PageContainer>
      <PageHeader
        title="Portfolio"
        description="Paper account balances, P&L, drawdown, open positions and exposure. All figures are SIMULATED."
        badges={
          <>
            <ModeBadge mode="PAPER" />
            {data?.is_demo_prices ? <ModeBadge mode="DEMO" /> : null}
          </>
        }
      />
      <DataBlock data={data} error={error} isLoading={isLoading} onRetry={() => mutate()} rows={8}>
        {(p) => {
          const s = p.summary;
          const eq = decimate(p.equity_curve, 600, (x) => x.equity);
          return (
            <>
              <Panel>
                <PanelHeader title="Account" icon={<Wallet />} subtitle={p.label} />
                <PanelBody className="grid grid-cols-2 gap-4 sm:grid-cols-4 xl:grid-cols-6">
                  <Stat label="Balance" value={fmtMoney(s.balance)} size="lg" />
                  <Stat label="Equity" value={fmtMoney(s.equity)} size="lg" />
                  <Stat label="Cash" value={fmtMoney(s.cash)} />
                  <Stat label="Margin used" value={fmtMoney(s.margin_used)} sub={`free ${fmtMoney(s.free_margin, 0)}`} />
                  <Stat label="Open P&L" value={<Signed value={s.open_pnl}>{fmtMoney(s.open_pnl, 2, true)}</Signed>} />
                  <Stat label="Closed P&L" value={<Signed value={s.closed_pnl}>{fmtMoney(s.closed_pnl, 2, true)}</Signed>} />
                  <Stat label="Daily P&L" value={<Signed value={s.daily_pnl}>{fmtMoney(s.daily_pnl, 2, true)}</Signed>} />
                  <Stat label="Weekly P&L" value={<Signed value={s.weekly_pnl}>{fmtMoney(s.weekly_pnl, 2, true)}</Signed>} />
                  <Stat label="Drawdown" value={fmtFrac(s.drawdown, 2)} tone={s.drawdown > 0.05 ? "down" : undefined} sub={`peak ${fmtMoney(s.peak_equity, 0)}`} />
                  <Stat label="Starting balance" value={fmtMoney(p.account.starting_balance, 0)} />
                  <Stat label="Return" value={fmtFrac((s.equity - p.account.starting_balance) / p.account.starting_balance, 2)} tone={s.equity >= p.account.starting_balance ? "up" : "down"} />
                  <Stat label="Max leverage" value={`${p.account.max_leverage}×`} />
                </PanelBody>
              </Panel>
              <div className="grid gap-3 xl:grid-cols-3">
                <Panel className="xl:col-span-2">
                  <PanelHeader title="Equity & balance" subtitle="Recorded snapshots of the paper account" />
                  <PanelBody>
                    {eq.length > 1 ? (
                      <>
                        <EquityChart data={eq} height={230} />
                        <DrawdownChart data={eq.map((x) => ({ ts: x.ts, dd: x.drawdown }))} height={110} />
                      </>
                    ) : (
                      <EmptyState title="Not enough history yet" description="Equity snapshots are recorded periodically while the app runs." />
                    )}
                  </PanelBody>
                </Panel>
                <Panel>
                  <PanelHeader title="Risk status" icon={<ShieldCheck />} />
                  <PanelBody>
                    <RiskSummary risk={p.risk} />
                  </PanelBody>
                </Panel>
              </div>
              <div className="grid gap-3 xl:grid-cols-3">
                <Panel className="xl:col-span-2">
                  <PanelHeader title="Positions" subtitle={`${p.positions.length} open`} />
                  {p.positions.length ? (
                    <Table>
                      <THead>
                        <tr>
                          <TH>Asset</TH>
                          <TH>Side</TH>
                          <TH align="right">Lots</TH>
                          <TH align="right">Entry</TH>
                          <TH align="right">Current</TH>
                          <TH align="right">Risk</TH>
                          <TH align="right">Unrealised</TH>
                        </tr>
                      </THead>
                      <tbody>
                        {p.positions.map((x) => (
                          <TR key={x.id}>
                            <TD className="font-semibold">{x.symbol}</TD>
                            <TD className={x.direction > 0 ? "text-up" : "text-down"}>{x.direction > 0 ? "LONG" : "SHORT"}</TD>
                            <TD align="right" className="num">
                              {fmtNum(x.lots, 2)}
                            </TD>
                            <TD align="right" className="num">
                              {fmtPrice(x.entry_price, x.symbol)}
                            </TD>
                            <TD align="right">
                              <FlashPrice value={x.current_price} symbol={x.symbol} />
                            </TD>
                            <TD align="right" className="num text-muted">
                              {fmtMoney(x.risk_usd, 0)}
                            </TD>
                            <TD align="right">
                              <Signed value={x.unrealized_pnl}>{fmtMoney(x.unrealized_pnl, 2, true)}</Signed>
                            </TD>
                          </TR>
                        ))}
                      </tbody>
                    </Table>
                  ) : (
                    <EmptyState title="No open positions" />
                  )}
                </Panel>
                <Panel>
                  <PanelHeader title="Exposure" icon={<PieChart />} subtitle="Signed notional (USD) per instrument" />
                  <PanelBody>
                    {p.exposure.length ? <SignedBars data={p.exposure.map((e) => ({ label: e.symbol, value: e.notional }))} valueLabel="Notional" format={(v) => fmtMoney(v, 0)} height={200} /> : <p className="text-xs text-faint">No exposure.</p>}
                  </PanelBody>
                </Panel>
              </div>
              <PerformanceSection report={p.performance} unit="usd" title="Closed-trade performance (paper)" />
            </>
          );
        }}
      </DataBlock>
    </PageContainer>
  );
}
