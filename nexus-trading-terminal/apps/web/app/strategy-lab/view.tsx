"use client";

import type { CalibrationReport, ConditionsSummary, StrategyInfo, Timeframe } from "@nexus/shared-types";
import { BrainCircuit, Database, FlaskConical, History, Search, Sigma } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { CountBars, ReliabilityChart } from "@/components/charts/recharts-kit";
import { Callout } from "@/components/common/disclaimer";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { Stat } from "@/components/common/stat";
import { DataBlock, EmptyState } from "@/components/common/states";
import { DirectionBadge, ModeBadge, RegimeBadge } from "@/components/market/badges";
import { SymbolSelect, TimeframeTabs } from "@/components/market/pickers";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { errorMessage, post, qs } from "@/lib/api";
import { ANALYSIS_TIMEFRAMES } from "@/lib/constants";
import { fmtDateTime, fmtNum, fmtR, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

interface PerfRow {
  strategy: string;
  regime: string;
  source: string;
  is_demo: boolean;
  trades: number;
  win_rate: number | null;
  average_r: number | null;
  net_pnl: number;
  sample_note: string;
}

interface Conditions {
  symbol: string;
  timeframe: string;
  k: number;
  current: Record<string, number | string | null>;
  summary: ConditionsSummary;
  matches: { timestamp: string; direction: string; regime: string; score: number; outcome: string; r_multiple: number | null; distance: number }[];
  is_demo: boolean;
}

const SAMPLE_TONE: Record<string, "down" | "warn" | "info" | "up" | "neutral"> = { NONE: "neutral", INSUFFICIENT: "down", SMALL: "warn", MODERATE: "info", LARGE: "up" };

function HistoryQuery() {
  const [symbol, setSymbol] = useState("XAUUSD");
  const [tf, setTf] = useState<Timeframe>("15m");
  const [k, setK] = useState(50);
  const [submitted, setSubmitted] = useState<string | null>(null);
  const { data, error, isLoading, mutate } = useApi<Conditions>(submitted);
  const s = data?.summary;
  return (
    <Panel>
      <PanelHeader title="What happened the last N times conditions looked like this?" icon={<Search />} subtitle="Nearest historical setups by feature similarity · no AI involved" />
      <PanelBody className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <SymbolSelect value={symbol} onChange={setSymbol} />
          <TimeframeTabs value={tf} onChange={setTf} options={ANALYSIS_TIMEFRAMES} />
          <label className="flex items-center gap-1.5 text-xs text-muted">
            N
            <select aria-label="Number of matches" value={k} onChange={(e) => setK(Number(e.target.value))} className="h-7 rounded-sm border border-line bg-panel-2 px-1 text-xs text-fg">
              {[10, 20, 50, 100].map((n) => (
                <option key={n}>{n}</option>
              ))}
            </select>
          </label>
          <Button variant="primary" size="sm" onClick={() => setSubmitted(`/api/history/conditions${qs({ symbol, timeframe: tf, k })}`)}>
            Query history
          </Button>
        </div>
        {error ? <Callout tone="down">{errorMessage(error)}</Callout> : null}
        {isLoading ? <p className="text-xs text-muted">Searching setup memory…</p> : null}
        {data && s ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="num text-xl font-bold text-fg-strong">{s.sample_size}</span>
              <span className="text-muted">similar setups</span>
              <Badge tone={SAMPLE_TONE[s.sample_label] ?? "neutral"}>{s.sample_label} sample</Badge>
              {data.is_demo ? <ModeBadge mode="DEMO" /> : null}
              {s.first ? (
                <span className="num text-faint">
                  {fmtDateTime(s.first)} → {fmtDateTime(s.last)}
                </span>
              ) : null}
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Current regime" value={<RegimeBadge regime={String(data.current.regime ?? "")} />} size="sm" />
              <Stat label="Average R" value={fmtR(s.average_r)} tone={(s.average_r ?? 0) >= 0 ? "up" : "down"} size="sm" />
              <Stat label="Median R" value={fmtR(s.median_r)} size="sm" />
              <Stat label="p10 / p90 R" value={`${fmtR(s.r_quantiles.p10)} / ${fmtR(s.r_quantiles.p90)}`} size="sm" />
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <div>
                <p className="label mb-1">Outcomes</p>
                <CountBars data={Object.entries(s.outcomes).map(([kk, v]) => ({ label: titleCase(kk), count: v, tone: kk === "WIN" ? "up" : kk === "LOSS" ? "down" : undefined }))} height={140} />
              </div>
              <div>
                <p className="label mb-1">Market regimes of matches</p>
                <div className="flex flex-col gap-1">
                  {Object.entries(s.regimes).map(([kk, v]) => (
                    <div key={kk} className="flex items-center justify-between text-xs">
                      <RegimeBadge regime={kk} />
                      <span className="num">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="label mb-1">Caveats</p>
                <ul className="list-disc pl-4 text-[0.7rem] text-muted">
                  {s.caveats.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            </div>
            <details>
              <summary className="cursor-pointer text-xs text-accent">Show {data.matches.length} matches</summary>
              <div className="mt-2 max-h-72 overflow-y-auto">
                <Table>
                  <THead>
                    <tr>
                      <TH>Date</TH>
                      <TH>Dir</TH>
                      <TH>Regime</TH>
                      <TH align="right">Score</TH>
                      <TH>Outcome</TH>
                      <TH align="right">R</TH>
                    </tr>
                  </THead>
                  <tbody>
                    {data.matches.map((m, i) => (
                      <TR key={i}>
                        <TD className="num text-muted">{fmtDateTime(m.timestamp)}</TD>
                        <TD>
                          <DirectionBadge direction={m.direction} />
                        </TD>
                        <TD>
                          <RegimeBadge regime={m.regime} />
                        </TD>
                        <TD align="right" className="num">
                          {fmtNum(m.score, 0)}
                        </TD>
                        <TD className="text-xs">{titleCase(m.outcome)}</TD>
                        <TD align="right" className={cn("num", (m.r_multiple ?? 0) >= 0 ? "text-up" : "text-down")}>
                          {fmtR(m.r_multiple)}
                        </TD>
                      </TR>
                    ))}
                  </tbody>
                </Table>
              </div>
            </details>
          </div>
        ) : null}
        {!submitted ? <p className="text-xs text-faint">Pick an asset and timeframe, then query. Results never generalise beyond the sample shown.</p> : null}
        {submitted && !data && !isLoading && !error ? <EmptyState title="No result" /> : null}
        {submitted ? (
          <Button size="xs" variant="ghost" className="self-start" onClick={() => mutate()}>
            Refresh
          </Button>
        ) : null}
      </PanelBody>
    </Panel>
  );
}

export function StrategyLabView() {
  const strategies = useApi<StrategyInfo[]>("/api/strategies");
  const perf = useApi<{ rows: PerfRow[]; note: string }>("/api/strategies/performance", 60_000);
  const ml = useApi<{ report: CalibrationReport | null; loaded: boolean }>("/api/strategies/ml", 60_000);
  const memory = useApi<{ status: { state: string }; counts: { symbol: string; timeframe: string; is_demo: boolean; records: number }[] }>("/api/history/memory", 60_000);
  const [training, setTraining] = useState(false);

  const train = async () => {
    setTraining(true);
    try {
      await post("/api/strategies/ml/train");
      await ml.mutate();
      toast.success("Calibration model evaluated");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setTraining(false);
    }
  };
  const r = ml.data?.report;

  return (
    <PageContainer>
      <PageHeader
        title="Strategy Lab"
        description="Deterministic strategy library, how each strategy performed by market regime, the historical setup memory and the outcome-calibration model."
        actions={
          <Button asChild size="sm" variant="primary">
            <Link href="/backtesting?new=1">
              <FlaskConical /> New backtest
            </Link>
          </Button>
        }
      />
      <Panel>
        <PanelHeader title="Strategy library" icon={<Sigma />} subtitle="Each strategy is versioned; signals record which versions voted" />
        <DataBlock data={strategies.data} error={strategies.error} isLoading={strategies.isLoading} onRetry={() => strategies.mutate()}>
          {(list) => (
            <div className="grid gap-3 p-3 md:grid-cols-2 xl:grid-cols-3">
              {list.map((s) => (
                <div key={s.name} className="flex flex-col gap-2 rounded-sm border border-line bg-panel-2/50 p-3">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-fg-strong">{s.name}</span>
                    <Badge>v{s.version}</Badge>
                  </div>
                  <p className="text-xs text-muted">{s.description}</p>
                  <div className="flex flex-wrap gap-1">
                    {s.regimes.map((g) => (
                      <RegimeBadge key={g} regime={g} />
                    ))}
                  </div>
                  <p className="num text-[0.66rem] text-faint">{Object.entries(s.params).map(([k, v]) => `${k}=${String(v)}`).join(" · ")}</p>
                  <Button asChild size="xs" variant="outline" className="mt-auto self-start">
                    <Link href={`/backtesting?new=1`}>Backtest</Link>
                  </Button>
                </div>
              ))}
            </div>
          )}
        </DataBlock>
      </Panel>

      <Panel>
        <PanelHeader title="Strategy performance by regime" icon={<BrainCircuit />} subtitle={perf.data?.note} />
        <DataBlock data={perf.data} error={perf.error} isLoading={perf.isLoading} onRetry={() => perf.mutate()} isEmpty={(d) => !d.rows.length} empty={<EmptyState title="No results yet" description="Run backtests to populate regime statistics." />}>
          {(d) => (
            <Table>
              <THead>
                <tr>
                  <TH>Strategy</TH>
                  <TH>Regime</TH>
                  <TH>Source</TH>
                  <TH align="right">Trades</TH>
                  <TH align="right">Win rate</TH>
                  <TH align="right">Avg R</TH>
                  <TH align="right">Net P&L</TH>
                  <TH>Sample</TH>
                </tr>
              </THead>
              <tbody>
                {d.rows.map((x, i) => (
                  <TR key={i}>
                    <TD className="font-medium">{x.strategy}</TD>
                    <TD>
                      <RegimeBadge regime={x.regime} />
                    </TD>
                    <TD>
                      <span className="flex items-center gap-1">
                        <Badge tone="purple">{x.source}</Badge>
                        {x.is_demo ? <ModeBadge mode="DEMO" /> : null}
                      </span>
                    </TD>
                    <TD align="right" className="num">
                      {x.trades}
                    </TD>
                    <TD align="right" className="num">
                      {x.win_rate === null ? "—" : `${fmtNum(x.win_rate * 100, 0)}%`}
                    </TD>
                    <TD align="right" className={cn("num", (x.average_r ?? 0) >= 0 ? "text-up" : "text-down")}>
                      {fmtR(x.average_r)}
                    </TD>
                    <TD align="right" className={cn("num", x.net_pnl >= 0 ? "text-up" : "text-down")}>
                      {fmtNum(x.net_pnl, 0)}
                    </TD>
                    <TD className={cn("text-xs", x.sample_note.includes("small") || x.sample_note.includes("insufficient") ? "text-warn" : "text-muted")}>{x.sample_note}</TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          )}
        </DataBlock>
      </Panel>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel>
          <PanelHeader
            title="Outcome calibration model"
            icon={<BrainCircuit />}
            subtitle="Logistic model + isotonic calibration. Probabilities are shown on signals only when status is CALIBRATED."
            actions={
              <Button size="xs" variant="outline" onClick={train} disabled={training}>
                {training ? "Evaluating…" : "Retrain & evaluate"}
              </Button>
            }
          />
          <PanelBody>
            <DataBlock data={ml.data} error={ml.error} isLoading={ml.isLoading} onRetry={() => ml.mutate()}>
              {() =>
                r ? (
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={r.status === "CALIBRATED" ? "up" : r.status === "INSUFFICIENT_DATA" ? "warn" : "down"}>{r.status.replace(/_/g, " ")}</Badge>
                      <span className="text-xs text-muted">
                        {r.model_name} v{r.model_version} · trained {fmtDateTime(r.trained_at)}
                      </span>
                      {r.data_mode === "DEMO" ? <ModeBadge mode="DEMO" title="Trained and evaluated on synthetic demo data" /> : null}
                    </div>
                    <p className="text-xs text-fg">Label: {r.label_definition}</p>
                    <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
                      <Stat label="Train" value={r.n_train} size="sm" />
                      <Stat label="Calibration" value={r.n_calibration} size="sm" />
                      <Stat label="Test" value={r.n_test} size="sm" />
                      <Stat label="Brier" value={fmtNum(r.brier, 3)} size="sm" sub={`baseline ${fmtNum(r.brier_baseline, 3)}`} />
                      <Stat label="ECE" value={fmtNum(r.ece, 3)} size="sm" hint="Expected calibration error (lower is better; must be ≤ 0.05)" />
                      <Stat label="AUC" value={fmtNum(r.auc, 3)} size="sm" />
                    </div>
                    <ReliabilityChart bins={r.reliability} />
                    {r.reasons.length ? (
                      <ul className="list-disc pl-4 text-[0.7rem] text-muted">
                        {r.reasons.map((x, i) => (
                          <li key={i}>{x}</li>
                        ))}
                      </ul>
                    ) : null}
                    {r.challenger ? (
                      <p className="text-[0.7rem] text-faint">
                        Challenger {r.challenger.name}: Brier {fmtNum(r.challenger.brier, 3)} · ECE {fmtNum(r.challenger.ece, 3)} · AUC {fmtNum(r.challenger.auc, 3)}
                      </p>
                    ) : null}
                    <Callout tone="info">Machine learning is used only to estimate the probability of a defined outcome, and only when out-of-sample calibration passes. It never replaces the deterministic signal or risk engines.</Callout>
                  </div>
                ) : (
                  <EmptyState title="Model not trained" description="Training needs enough labelled historical setups in memory." />
                )
              }
            </DataBlock>
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Historical setup memory" icon={<Database />} subtitle={memory.data ? `Build state: ${memory.data.status.state}` : undefined} />
          <DataBlock data={memory.data} error={memory.error} isLoading={memory.isLoading} onRetry={() => memory.mutate()} isEmpty={(d) => !d.counts.length} empty={<EmptyState icon={<History />} title="Memory is empty" description="It is built in the background from historical bars (or by `npm run seed`)." />}>
            {(d) => (
              <Table>
                <THead>
                  <tr>
                    <TH>Asset</TH>
                    <TH>TF</TH>
                    <TH align="right">Labelled setups</TH>
                    <TH>Data</TH>
                  </tr>
                </THead>
                <tbody>
                  {d.counts.map((c) => (
                    <TR key={`${c.symbol}-${c.timeframe}-${c.is_demo}`}>
                      <TD className="font-medium">{c.symbol}</TD>
                      <TD className="num">{c.timeframe}</TD>
                      <TD align="right" className="num">
                        {c.records.toLocaleString()}
                      </TD>
                      <TD>{c.is_demo ? <ModeBadge mode="DEMO" /> : <Badge tone="up">LIVE</Badge>}</TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            )}
          </DataBlock>
        </Panel>
      </div>
      <HistoryQuery />
    </PageContainer>
  );
}
