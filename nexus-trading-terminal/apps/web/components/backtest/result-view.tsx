"use client";

import type { BacktestDetail, MetricsBundle } from "@nexus/shared-types";
import { AlertTriangle, BarChart3, CalendarRange, LineChart, ListOrdered, TrendingDown } from "lucide-react";
import { useState } from "react";

import { CountBars, DrawdownChart, EquityChart } from "@/components/charts/recharts-kit";
import { Callout } from "@/components/common/disclaimer";
import { ExportButton } from "@/components/common/export-button";
import { KV } from "@/components/common/stat";
import { DirectionBadge, ModeBadge, RegimeBadge } from "@/components/market/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { fmtDateTime, fmtMoney, fmtNum, fmtPrice, fmtR, titleCase } from "@/lib/format";
import { decimate, rDistribution } from "@/lib/series";
import { cn } from "@/lib/utils";

import { MetricsGrid } from "./metrics-grid";
import { MonthlyReturns } from "./monthly-returns";

function curves(equity: [string, number][] | undefined, drawdown: [string, number][] | undefined) {
  const eq = decimate(
    (equity ?? []).map(([ts, v]) => ({ ts, equity: v })),
    700,
    (p) => p.equity,
  );
  const dd = decimate(
    (drawdown ?? []).map(([ts, v]) => ({ ts, dd: v })),
    700,
    (p) => -Math.abs(p.dd),
  );
  return { eq, dd };
}

/** Drawdown series from an equity curve (used for walk-forward OOS, which stores equity only). */
function ddFromEquity(equity: [string, number][]): [string, number][] {
  let peak = -Infinity;
  return equity.map(([ts, v]) => {
    peak = Math.max(peak, v);
    return [ts, peak > 0 ? (peak - v) / peak : 0];
  });
}

function BundleSections({ bundle, equity, drawdown, title }: { bundle: MetricsBundle; equity: [string, number][]; drawdown: [string, number][]; title: string }) {
  const { eq, dd } = curves(equity, drawdown);
  return (
    <>
      <Panel>
        <PanelHeader title={`${title} · metrics`} icon={<BarChart3 />} />
        <PanelBody>
          <MetricsGrid m={bundle.metrics} />
        </PanelBody>
      </Panel>
      <div className="grid gap-3 xl:grid-cols-2">
        <Panel>
          <PanelHeader title="Equity curve" icon={<LineChart />} />
          <PanelBody>{eq.length ? <EquityChart data={eq} /> : <p className="text-xs text-faint">No equity data.</p>}</PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Drawdown" icon={<TrendingDown />} subtitle="Peak-to-trough decline of equity" />
          <PanelBody>{dd.length ? <DrawdownChart data={dd} height={220} /> : <p className="text-xs text-faint">No drawdown data.</p>}</PanelBody>
        </Panel>
      </div>
      <div className="grid gap-3 xl:grid-cols-2">
        <Panel>
          <PanelHeader title="Monthly returns" icon={<CalendarRange />} subtitle="% of equity at month start" />
          <PanelBody>
            <MonthlyReturns data={bundle.monthly_returns} />
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Trade distribution" subtitle="R-multiple of each closed trade" />
          <PanelBody>
            <CountBars data={rDistribution(bundle.r_distribution)} />
          </PanelBody>
        </Panel>
      </div>
      <div className="grid gap-3 xl:grid-cols-2">
        <Panel>
          <PanelHeader title="Losing periods" icon={<AlertTriangle />} subtitle="Every drawdown episode, largest first - never hidden" />
          {bundle.losing_periods.length ? (
            <Table>
              <THead>
                <tr>
                  <TH>Start</TH>
                  <TH>Trough</TH>
                  <TH>Recovered</TH>
                  <TH align="right">Depth</TH>
                  <TH align="right">Bars</TH>
                </tr>
              </THead>
              <tbody>
                {bundle.losing_periods.map((p, i) => (
                  <TR key={i}>
                    <TD className="num text-muted">{fmtDateTime(p.start)}</TD>
                    <TD className="num text-muted">{fmtDateTime(p.trough)}</TD>
                    <TD className={p.recovered ? "num text-muted" : "text-xs font-semibold text-down"}>{p.recovered ? fmtDateTime(p.end) : "Not recovered"}</TD>
                    <TD align="right" className="num text-down">
                      −{fmtNum(p.depth_pct, 2)}%
                    </TD>
                    <TD align="right" className="num">
                      {p.duration_bars}
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          ) : (
            <PanelBody>
              <p className="text-xs text-faint">No drawdown episodes.</p>
            </PanelBody>
          )}
        </Panel>
        <Panel>
          <PanelHeader title="Performance by market regime" subtitle="Regime at entry" />
          <Table>
            <THead>
              <tr>
                <TH>Regime</TH>
                <TH align="right">Trades</TH>
                <TH align="right">Win rate</TH>
                <TH align="right">Avg R</TH>
                <TH align="right">PF</TH>
                <TH align="right">Net</TH>
              </tr>
            </THead>
            <tbody>
              {bundle.by_regime.map((r) => (
                <TR key={r.regime}>
                  <TD>
                    <RegimeBadge regime={r.regime} />
                  </TD>
                  <TD align="right" className="num">
                    {r.trades}
                    {r.trades < 10 ? <span className="ml-1 text-[0.6rem] text-warn">small</span> : null}
                  </TD>
                  <TD align="right" className="num">
                    {r.win_rate === null ? "—" : `${fmtNum(r.win_rate * 100, 0)}%`}
                  </TD>
                  <TD align="right" className={cn("num", (r.average_r ?? 0) >= 0 ? "text-up" : "text-down")}>
                    {fmtR(r.average_r)}
                  </TD>
                  <TD align="right" className="num">
                    {fmtNum(r.profit_factor, 2)}
                  </TD>
                  <TD align="right" className={cn("num", r.net_profit >= 0 ? "text-up" : "text-down")}>
                    {fmtMoney(r.net_profit, 0, true)}
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </Panel>
      </div>
    </>
  );
}

export function BacktestResultView({ bt }: { bt: BacktestDetail }) {
  const [showAll, setShowAll] = useState(false);
  const r = bt.result;
  const isWf = bt.kind === "WALK_FORWARD";
  const trades = showAll ? bt.trades : bt.trades.slice(0, 100);
  return (
    <div className="flex flex-col gap-3">
      <Panel>
        <PanelBody className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-base font-bold text-fg-strong">
              {bt.strategy} <span className="text-xs font-normal text-muted">v{bt.strategy_version}</span>
            </span>
            <Badge tone="purple">{isWf ? "WALK-FORWARD" : "BACKTEST"}</Badge>
            <ModeBadge mode="BACKTEST" />
            {bt.is_demo ? <ModeBadge mode="DEMO" /> : <Badge tone="info">{bt.data_label}</Badge>}
            <span className="num text-xs text-muted">
              {bt.symbol} · {bt.timeframe}
            </span>
            <div className="ml-auto flex gap-1.5">
              {bt.trades.length ? <ExportButton path={`/api/backtests/${bt.id}/trades.csv`} filename={`nexus-backtest-${bt.id}.csv`} size="xs" variant="outline" label="Trades CSV" /> : null}
            </div>
          </div>
          <div className="grid gap-x-6 text-xs sm:grid-cols-2 xl:grid-cols-4">
            <KV k="Data" v={bt.data_label} mono={false} />
            <KV k="Provider" v={bt.provider} />
            <KV k="Trading period" v={r?.trade_start ? `${fmtDateTime(r.trade_start)} → ${fmtDateTime(r.trade_end)}` : "—"} />
            <KV k="Bars" v={r?.bars ?? "—"} />
            <KV k="Engine" v={`v${bt.engine_version}`} />
            <KV k="Run time" v={bt.duration_ms !== null ? `${fmtNum(bt.duration_ms / 1000, 1)}s` : "—"} />
            <KV k="Created" v={fmtDateTime(bt.created_at)} />
            <KV k="Params" v={Object.keys(bt.params).length ? JSON.stringify(bt.params) : "defaults"} />
          </div>
          {bt.warnings.map((w, i) => (
            <Callout key={i} tone="warn">
              {w}
            </Callout>
          ))}
          {bt.error ? <Callout tone="down">{bt.error}</Callout> : null}
        </PanelBody>
      </Panel>

      {!isWf && r?.metrics ? <BundleSections bundle={r.metrics} equity={r.equity_curve ?? []} drawdown={r.drawdown_curve ?? []} title="Backtest" /> : null}

      {isWf && r ? (
        <>
          {r.overfitting ? (
            <Callout tone={r.overfitting.suspicious ? "down" : "accent"} title={r.overfitting.suspicious ? "Overfitting warning" : "Overfitting checks"}>
              <p>{r.overfitting.summary}</p>
              {r.overfitting.flags.length ? (
                <ul className="mt-1 list-disc pl-4">
                  {r.overfitting.flags.map((f) => (
                    <li key={f.code}>
                      <span className={f.severity === "HIGH" ? "text-down" : "text-warn"}>{f.code}</span> · {f.detail}
                    </li>
                  ))}
                </ul>
              ) : null}
            </Callout>
          ) : null}
          <Panel>
            <PanelHeader title="Walk-forward windows" icon={<CalendarRange />} subtitle="Parameters chosen on TRAIN, checked on VALIDATION, reported on unseen TEST data" />
            <Table>
              <THead>
                <tr>
                  <TH>#</TH>
                  <TH>Train</TH>
                  <TH>Validation</TH>
                  <TH>Test (out of sample)</TH>
                  <TH>Chosen params</TH>
                  <TH align="right">Train exp.</TH>
                  <TH align="right">Val exp.</TH>
                  <TH align="right">Test exp.</TH>
                  <TH align="right">Test trades</TH>
                  <TH align="right">Test net</TH>
                </tr>
              </THead>
              <tbody>
                {(r.windows ?? []).map((w) => (
                  <TR key={w.window}>
                    <TD className="num">{w.window}</TD>
                    <TD className="num text-[0.7rem] text-muted">
                      {fmtDateTime(w.train.start).slice(0, 11)} → {fmtDateTime(w.train.end).slice(0, 11)}
                    </TD>
                    <TD className="num text-[0.7rem] text-muted">
                      {fmtDateTime(w.validation.start).slice(0, 11)} → {fmtDateTime(w.validation.end).slice(0, 11)}
                    </TD>
                    <TD className="num text-[0.7rem] text-fg">
                      {fmtDateTime(w.test.start).slice(0, 11)} → {fmtDateTime(w.test.end).slice(0, 11)}
                    </TD>
                    <TD className="max-w-56 truncate text-[0.7rem] text-muted">{JSON.stringify(w.chosen_params)}</TD>
                    <TD align="right" className="num">
                      {fmtR(w.train.metrics.expectancy_r)}
                    </TD>
                    <TD align="right" className="num">
                      {fmtR(w.validation.metrics.expectancy_r)}
                    </TD>
                    <TD align="right" className={cn("num font-semibold", (w.test.metrics.expectancy_r ?? 0) >= 0 ? "text-up" : "text-down")}>
                      {fmtR(w.test.metrics.expectancy_r)}
                    </TD>
                    <TD align="right" className="num">
                      {w.test.metrics.total_trades}
                    </TD>
                    <TD align="right" className={cn("num", w.test.metrics.net_profit >= 0 ? "text-up" : "text-down")}>
                      {fmtMoney(w.test.metrics.net_profit, 0, true)}
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          </Panel>
          {r.oos_metrics ? <BundleSections bundle={r.oos_metrics} equity={r.oos_equity_curve ?? []} drawdown={ddFromEquity(r.oos_equity_curve ?? [])} title="Out-of-sample (stitched TEST windows)" /> : null}
        </>
      ) : null}

      <Panel>
        <PanelHeader title={isWf ? "Out-of-sample trades" : "Trade list"} icon={<ListOrdered />} subtitle={`${bt.trades.length} trades · fills at next bar open incl. spread, slippage and fees`} />
        {bt.trades.length ? (
          <>
            <Table>
              <THead>
                <tr>
                  <TH>#</TH>
                  <TH>Dir</TH>
                  <TH>Entry</TH>
                  <TH>Exit</TH>
                  <TH align="right">Entry px</TH>
                  <TH align="right">Exit px</TH>
                  <TH align="right">Lots</TH>
                  <TH align="right">P&L</TH>
                  <TH align="right">R</TH>
                  <TH align="right">Fees</TH>
                  <TH>Exit reason</TH>
                  <TH>Regime</TH>
                  <TH align="right">Bars</TH>
                </tr>
              </THead>
              <tbody>
                {trades.map((t) => (
                  <TR key={t.trade_no}>
                    <TD className="num text-muted">{t.trade_no}</TD>
                    <TD>
                      <DirectionBadge direction={t.direction} />
                    </TD>
                    <TD className="num text-muted">{fmtDateTime(t.entry_time)}</TD>
                    <TD className="num text-muted">{fmtDateTime(t.exit_time)}</TD>
                    <TD align="right" className="num">
                      {fmtPrice(t.entry_price, bt.symbol)}
                    </TD>
                    <TD align="right" className="num">
                      {fmtPrice(t.exit_price, bt.symbol)}
                    </TD>
                    <TD align="right" className="num">
                      {fmtNum(t.lots, 2)}
                    </TD>
                    <TD align="right" className={cn("num", t.pnl >= 0 ? "text-up" : "text-down")}>
                      {fmtMoney(t.pnl, 2, true)}
                    </TD>
                    <TD align="right" className={cn("num", (t.pnl_r ?? 0) >= 0 ? "text-up" : "text-down")}>
                      {fmtR(t.pnl_r)}
                    </TD>
                    <TD align="right" className="num text-muted">
                      {fmtMoney(t.fees, 2)}
                    </TD>
                    <TD className="text-xs">{titleCase(t.exit_reason)}</TD>
                    <TD>
                      <RegimeBadge regime={t.regime} />
                    </TD>
                    <TD align="right" className="num">
                      {t.bars_held}
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
            {bt.trades.length > 100 ? (
              <div className="border-t border-line p-2 text-center">
                <Button size="xs" variant="ghost" onClick={() => setShowAll((v) => !v)}>
                  {showAll ? "Show first 100" : `Show all ${bt.trades.length} trades`}
                </Button>
              </div>
            ) : null}
          </>
        ) : (
          <PanelBody>
            <p className="text-xs text-faint">No trades were taken. A strategy that does not trade in this period is a valid result.</p>
          </PanelBody>
        )}
      </Panel>
    </div>
  );
}
