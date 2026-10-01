"use client";

import { Activity, Gauge, GitCompareArrows, Layers, Waves } from "lucide-react";

import { CorrelationMatrix } from "@/components/charts/correlation-matrix";
import { Callout } from "@/components/common/disclaimer";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { Stat } from "@/components/common/stat";
import { DataBlock } from "@/components/common/states";
import { ModeBadge, RegimeBadge } from "@/components/market/badges";
import { Change } from "@/components/market/price";
import { Badge } from "@/components/ui/badge";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Progress } from "@/components/ui/progress";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { REGIME_LABEL } from "@/lib/constants";
import { fmtNum } from "@/lib/format";
import { cn } from "@/lib/utils";

interface Psychology {
  is_demo: boolean;
  disclaimer: string;
  risk_appetite: { score: number; label: string; usd_basket_change_pct: number | null; inputs: string };
  volatility: { average_percentile: number | null; elevated: string[] };
  breadth: { pct_up_24h: number; pct_positive_trend: number; instruments: number };
  momentum: { average_score: number | null; strongest: { symbol: string; score: number }[] };
  concentration: { top2_share_of_moves: number | null; herfindahl: number | null };
  correlation: { average_abs_correlation: number | null; symbols: string[]; matrix: (number | null)[][]; days: number; observations: number };
  regimes: Record<string, number>;
  assets: { symbol: string; change_pct_24h: number | null; trend_score: number | null; momentum_score: number | null; vol_percentile: number | null; regime: string }[];
}

function RiskDial({ score, label }: { score: number; label: string }) {
  const pct = ((Math.max(-1, Math.min(1, score)) + 1) / 2) * 100;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-end justify-between">
        <span className="text-xs text-down">Risk-off</span>
        <span className={cn("text-lg font-bold tracking-wide", score > 0.2 ? "text-up" : score < -0.2 ? "text-down" : "text-warn")}>{label.replace(/_/g, " ")}</span>
        <span className="text-xs text-up">Risk-on</span>
      </div>
      <div className="relative h-2.5 rounded-full bg-gradient-to-r from-down/70 via-warn/50 to-up/70">
        <span className="absolute top-1/2 h-4 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-fg-strong shadow" style={{ left: `${pct}%` }} />
      </div>
      <span className="num text-center text-xs text-muted">score {fmtNum(score, 2)} (−1 … +1)</span>
    </div>
  );
}

export function PsychologyView() {
  const { data, error, isLoading, mutate } = useApi<Psychology>("/api/psychology", 60_000);
  return (
    <PageContainer>
      <PageHeader
        title="Market Psychology"
        description="Market state inferred from measurable variables: cross-asset moves, volatility, breadth, momentum, concentration and correlation. It does not read anyone's mind."
        badges={data ? <ModeBadge mode={data.is_demo ? "DEMO" : "LIVE"} /> : null}
      />
      <DataBlock data={data} error={error} isLoading={isLoading} onRetry={() => mutate()} rows={8}>
        {(d) => (
          <>
            <Callout tone="info" title="How to read this page">
              {d.disclaimer}
            </Callout>
            <div className="grid gap-3 lg:grid-cols-3">
              <Panel>
                <PanelHeader title="Risk appetite" icon={<Gauge />} subtitle="Risk-on / risk-off proxy" />
                <PanelBody className="flex flex-col gap-3">
                  <RiskDial score={d.risk_appetite.score} label={d.risk_appetite.label} />
                  <p className="text-[0.7rem] text-muted">Inputs: {d.risk_appetite.inputs}</p>
                  {d.risk_appetite.usd_basket_change_pct !== null ? (
                    <p className="text-xs">
                      USD basket 24h: <Change pct={d.risk_appetite.usd_basket_change_pct} />
                    </p>
                  ) : null}
                </PanelBody>
              </Panel>
              <Panel>
                <PanelHeader title="Breadth & momentum" icon={<Activity />} />
                <PanelBody className="flex flex-col gap-3">
                  <div>
                    <div className="mb-1 flex justify-between text-xs">
                      <span className="text-muted">Instruments up over 24h</span>
                      <span className="num">{fmtNum(d.breadth.pct_up_24h, 0)}%</span>
                    </div>
                    <Progress value={d.breadth.pct_up_24h} tone="up" label="Share of instruments up" />
                  </div>
                  <div>
                    <div className="mb-1 flex justify-between text-xs">
                      <span className="text-muted">Positive trend score</span>
                      <span className="num">{fmtNum(d.breadth.pct_positive_trend, 0)}%</span>
                    </div>
                    <Progress value={d.breadth.pct_positive_trend} label="Share with positive trend" />
                  </div>
                  <Stat label="Average momentum score" value={fmtNum(d.momentum.average_score, 1)} tone={(d.momentum.average_score ?? 0) >= 0 ? "up" : "down"} size="sm" />
                  <div className="flex flex-wrap gap-1">
                    {d.momentum.strongest.map((s) => (
                      <Badge key={s.symbol} tone={s.score >= 0 ? "up" : "down"}>
                        {s.symbol} {fmtNum(s.score, 0)}
                      </Badge>
                    ))}
                  </div>
                </PanelBody>
              </Panel>
              <Panel>
                <PanelHeader title="Volatility & concentration" icon={<Waves />} />
                <PanelBody className="flex flex-col gap-3">
                  <div>
                    <div className="mb-1 flex justify-between text-xs">
                      <span className="text-muted">Average volatility percentile</span>
                      <span className="num">{fmtNum(d.volatility.average_percentile, 0)}</span>
                    </div>
                    <Progress value={d.volatility.average_percentile} tone={(d.volatility.average_percentile ?? 0) > 75 ? "warn" : "accent"} label="Average volatility percentile" />
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {d.volatility.elevated.length ? d.volatility.elevated.map((s) => <Badge key={s} tone="warn">{s}</Badge>) : <span className="text-xs text-faint">No instrument in an elevated volatility state.</span>}
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Stat label="Top-2 share of moves" value={d.concentration.top2_share_of_moves === null ? "—" : `${fmtNum(d.concentration.top2_share_of_moves * 100, 0)}%`} size="sm" hint="Share of total absolute 24h moves contributed by the two biggest movers" />
                    <Stat label="Herfindahl index" value={fmtNum(d.concentration.herfindahl, 3)} size="sm" hint="Concentration of moves; 1/N = evenly spread, 1 = a single instrument" />
                  </div>
                </PanelBody>
              </Panel>
            </div>
            <div className="grid gap-3 xl:grid-cols-[1fr_380px]">
              <Panel>
                <PanelHeader title="Correlation of daily returns" icon={<GitCompareArrows />} subtitle={`${d.correlation.days} days · ${d.correlation.observations} observations · average |ρ| ${fmtNum(d.correlation.average_abs_correlation, 2)}`} />
                <PanelBody>
                  <CorrelationMatrix symbols={d.correlation.symbols} matrix={d.correlation.matrix} />
                </PanelBody>
              </Panel>
              <Panel>
                <PanelHeader title="Regime distribution" icon={<Layers />} />
                <PanelBody className="flex flex-col gap-2">
                  {Object.entries(d.regimes)
                    .sort((a, b) => b[1] - a[1])
                    .map(([k, v]) => (
                      <div key={k} className="flex items-center gap-2 text-xs">
                        <span className="w-36 shrink-0">
                          <RegimeBadge regime={k} />
                        </span>
                        <Progress value={v} max={d.breadth.instruments} label={REGIME_LABEL[k] ?? k} />
                        <span className="num w-6 text-right">{v}</span>
                      </div>
                    ))}
                </PanelBody>
              </Panel>
            </div>
            <Panel>
              <PanelHeader title="Per-instrument inputs" subtitle="1H measurements used above" />
              <Table>
                <THead>
                  <tr>
                    <TH>Asset</TH>
                    <TH align="right">24H</TH>
                    <TH align="right">Trend score</TH>
                    <TH align="right">Momentum</TH>
                    <TH align="right">Vol pct</TH>
                    <TH>Regime</TH>
                  </tr>
                </THead>
                <tbody>
                  {d.assets.map((a) => (
                    <TR key={a.symbol}>
                      <TD className="font-semibold">{a.symbol}</TD>
                      <TD align="right">
                        <Change pct={a.change_pct_24h} />
                      </TD>
                      <TD align="right" className={cn("num", (a.trend_score ?? 0) >= 0 ? "text-up" : "text-down")}>
                        {fmtNum(a.trend_score, 0)}
                      </TD>
                      <TD align="right" className={cn("num", (a.momentum_score ?? 0) >= 0 ? "text-up" : "text-down")}>
                        {fmtNum(a.momentum_score, 0)}
                      </TD>
                      <TD align="right" className="num">
                        {fmtNum(a.vol_percentile, 0)}
                      </TD>
                      <TD>
                        <RegimeBadge regime={a.regime} />
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            </Panel>
          </>
        )}
      </DataBlock>
    </PageContainer>
  );
}
