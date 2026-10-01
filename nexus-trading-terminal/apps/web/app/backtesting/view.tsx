"use client";

import type { BacktestDetail, BacktestSummary, StrategyInfo, Timeframe } from "@nexus/shared-types";
import { FlaskConical, History, Play } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { BacktestResultView } from "@/components/backtest/result-view";
import { Callout, RiskNotice } from "@/components/common/disclaimer";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { DataBlock, EmptyState, Spinner } from "@/components/common/states";
import { ModeBadge } from "@/components/market/badges";
import { Segmented, SymbolSelect } from "@/components/market/pickers";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Switch } from "@/components/ui/switch";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { errorMessage, post } from "@/lib/api";
import { ANALYSIS_TIMEFRAMES } from "@/lib/constants";
import { fmtDateTime, fmtMoney, fmtNum, fmtR } from "@/lib/format";
import { cn } from "@/lib/utils";

interface ImportBatch {
  batch: string;
  symbol: string;
  timeframe: string;
  rows: number;
  data_source: string;
}

const isoDate = (d: Date) => d.toISOString().slice(0, 10);

function ParamInput({ name, value, onChange }: { name: string; value: unknown; onChange: (v: unknown) => void }) {
  if (typeof value === "boolean") {
    return (
      <label className="flex items-center justify-between gap-2 rounded-sm border border-line bg-panel-2 px-2 py-1 text-xs">
        {name}
        <Switch checked={value} onCheckedChange={onChange} aria-label={name} />
      </label>
    );
  }
  return (
    <Field label={name} htmlFor={`p-${name}`}>
      <Input id={`p-${name}`} type="number" step="any" value={String(value ?? "")} onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))} />
    </Field>
  );
}

export function BacktestingView() {
  const params = useSearchParams();
  const { mutate } = useSWRConfig();
  const formRef = useRef<HTMLDivElement>(null);
  const strategies = useApi<StrategyInfo[]>("/api/strategies");
  const imports = useApi<ImportBatch[]>("/api/market/imports");
  const history = useApi<BacktestSummary[]>("/api/backtests?limit=50", 30_000);

  const today = new Date();
  const [mode, setMode] = useState<"single" | "wf">("single");
  const [strategy, setStrategy] = useState("TrendFollowing");
  const [symbol, setSymbol] = useState(params.get("symbol") ?? "XAUUSD");
  const [tf, setTf] = useState<Timeframe>((params.get("timeframe") as Timeframe) ?? "1H");
  const [source, setSource] = useState(params.get("source") ?? "provider");
  const [start, setStart] = useState(isoDate(new Date(today.getTime() - 180 * 86400_000)));
  const [end, setEnd] = useState(isoDate(today));
  const [capital, setCapital] = useState(100000);
  const [riskPct, setRiskPct] = useState(1);
  const [spread, setSpread] = useState<string>("");
  const [commission, setCommission] = useState<string>("");
  const [slippage, setSlippage] = useState(1);
  const [sizing, setSizing] = useState("FIXED_PERCENT");
  const [partialR, setPartialR] = useState(1);
  const [partialFrac, setPartialFrac] = useState(0.5);
  const [breakeven, setBreakeven] = useState(true);
  const [maxBars, setMaxBars] = useState(100);
  const [maxDaily, setMaxDaily] = useState(3);
  const [paramEdits, setParamEdits] = useState<Record<string, Record<string, unknown>>>({});
  const [wf, setWf] = useState({ train_bars: 2000, validation_bars: 500, test_bars: 500, max_windows: 6 });
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [result, setResult] = useState<BacktestDetail | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const selectedDetail = useApi<BacktestDetail>(selected && selected !== result?.id ? `/api/backtests/${selected}` : null);

  const info = strategies.data?.find((s) => s.name === strategy);
  // Defaults come from the strategy definition; user edits are kept per strategy.
  const stratParams: Record<string, unknown> = { ...(info?.params ?? {}), ...(paramEdits[strategy] ?? {}) };
  const setParam = (k: string, v: unknown) => setParamEdits((all) => ({ ...all, [strategy]: { ...(all[strategy] ?? {}), [k]: v } }));
  useEffect(() => {
    if (params.get("new")) formRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [params]);
  useEffect(() => {
    if (!busy) return;
    const t0 = Date.now();
    const id = setInterval(() => setElapsed(Math.round((Date.now() - t0) / 1000)), 500);
    return () => clearInterval(id);
  }, [busy]);

  const run = async () => {
    setBusy(true);
    setErr(null);
    setElapsed(0);
    const cfg = {
      symbol,
      timeframe: tf,
      strategy,
      params: stratParams,
      start: `${start}T00:00:00Z`,
      end: `${end}T23:59:59Z`,
      initial_capital: capital,
      risk_per_trade: riskPct / 100,
      spread: spread === "" ? null : Number(spread),
      commission_per_lot: commission === "" ? null : Number(commission),
      slippage_bps: slippage,
      partial_exit_r: partialR > 0 ? partialR : null,
      partial_fraction: partialFrac,
      move_stop_to_breakeven: breakeven,
      max_bars_in_trade: maxBars,
      max_daily_loss: maxDaily > 0 ? maxDaily / 100 : null,
      sizing_method: sizing,
    };
    try {
      const res =
        mode === "single"
          ? await post<BacktestDetail>("/api/backtests", { ...cfg, data_source: source })
          : await post<BacktestDetail>("/api/backtests/walk-forward", { backtest: cfg, ...wf, data_source: source });
      setResult(res);
      setSelected(res.id);
      void mutate((k) => typeof k === "string" && (k.startsWith("/api/backtests") || k.startsWith("/api/strategies")));
      toast.success(`${mode === "single" ? "Backtest" : "Walk-forward"} finished: ${res.metrics?.total_trades ?? 0} trades`);
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const shown = selected && result?.id === selected ? result : selectedDetail.data ?? null;
  const sourceOptions = (imports.data ?? []).filter((b) => b.symbol === symbol && b.timeframe === tf);

  return (
    <PageContainer>
      <PageHeader
        title="Backtesting"
        description="Event-driven simulation with next-bar fills, spread, slippage, commission, partial exits and stop-first handling inside a bar. No look-ahead: strategies only see closed bars."
        badges={<ModeBadge mode="BACKTEST" />}
        actions={
          <Button asChild size="sm" variant="outline">
            <Link href="/strategy-lab">
              <FlaskConical /> Strategy Lab
            </Link>
          </Button>
        }
      />
      <div className="grid gap-3 xl:grid-cols-[400px_1fr]">
        <div ref={formRef}>
          <Panel>
            <PanelHeader title="Configuration" icon={<Play />} actions={<Segmented label="Mode" value={mode} onChange={setMode} options={[{ value: "single", label: "Backtest" }, { value: "wf", label: "Walk-forward" }]} />} />
            <PanelBody className="flex flex-col gap-3">
              <Field label="Strategy" htmlFor="bt-strategy" hint={info?.description}>
                <Select id="bt-strategy" value={strategy} onChange={(e) => setStrategy(e.target.value)}>
                  {(strategies.data ?? []).map((s) => (
                    <option key={s.name} value={s.name}>
                      {s.name} v{s.version}
                    </option>
                  ))}
                </Select>
              </Field>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Asset" htmlFor="bt-symbol">
                  <SymbolSelect id="bt-symbol" value={symbol} onChange={setSymbol} className="w-full" />
                </Field>
                <Field label="Timeframe" htmlFor="bt-tf">
                  <Select id="bt-tf" value={tf} onChange={(e) => setTf(e.target.value as Timeframe)}>
                    {ANALYSIS_TIMEFRAMES.map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </Select>
                </Field>
                <Field label="Start date" htmlFor="bt-start">
                  <Input id="bt-start" type="date" value={start} max={end} onChange={(e) => setStart(e.target.value)} />
                </Field>
                <Field label="End date" htmlFor="bt-end">
                  <Input id="bt-end" type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} />
                </Field>
              </div>
              <Field label="Data source" htmlFor="bt-source" hint={source === "provider" ? "Configured market data provider (DEMO synthetic data when no provider key is set)" : "User-imported CSV data"}>
                <Select id="bt-source" value={source} onChange={(e) => setSource(e.target.value)}>
                  <option value="provider">Market data provider</option>
                  {sourceOptions.map((b) => (
                    <option key={b.batch} value={b.data_source}>
                      Imported {b.batch} ({b.rows} bars)
                    </option>
                  ))}
                  {source !== "provider" && !sourceOptions.some((b) => b.data_source === source) ? <option value={source}>{source}</option> : null}
                </Select>
              </Field>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Starting capital ($)" htmlFor="bt-cap">
                  <Input id="bt-cap" type="number" min={100} step={1000} value={capital} onChange={(e) => setCapital(Number(e.target.value))} />
                </Field>
                <Field label="Risk per trade (%)" htmlFor="bt-risk">
                  <Input id="bt-risk" type="number" min={0.05} max={5} step={0.05} value={riskPct} onChange={(e) => setRiskPct(Number(e.target.value))} />
                </Field>
                <Field label="Spread (price units)" htmlFor="bt-spread" hint="Blank = instrument typical spread">
                  <Input id="bt-spread" type="number" min={0} step="any" placeholder="typical" value={spread} onChange={(e) => setSpread(e.target.value)} />
                </Field>
                <Field label="Commission ($/lot)" htmlFor="bt-comm" hint="Blank = asset-class default">
                  <Input id="bt-comm" type="number" min={0} step="any" placeholder="default" value={commission} onChange={(e) => setCommission(e.target.value)} />
                </Field>
                <Field label="Slippage (bps)" htmlFor="bt-slip">
                  <Input id="bt-slip" type="number" min={0} max={100} step={0.5} value={slippage} onChange={(e) => setSlippage(Number(e.target.value))} />
                </Field>
                <Field label="Position sizing" htmlFor="bt-sizing">
                  <Select id="bt-sizing" value={sizing} onChange={(e) => setSizing(e.target.value)}>
                    <option value="FIXED_PERCENT">Fixed % risk</option>
                    <option value="FIXED_AMOUNT">Fixed $ risk</option>
                    <option value="VOLATILITY_ADJUSTED">Volatility-adjusted</option>
                  </Select>
                </Field>
                <Field label="Partial exit at (R)" htmlFor="bt-pr" hint="0 = no partial exit">
                  <Input id="bt-pr" type="number" min={0} step={0.25} value={partialR} onChange={(e) => setPartialR(Number(e.target.value))} />
                </Field>
                <Field label="Partial fraction" htmlFor="bt-pf">
                  <Input id="bt-pf" type="number" min={0.1} max={0.9} step={0.1} value={partialFrac} onChange={(e) => setPartialFrac(Number(e.target.value))} />
                </Field>
                <Field label="Max bars in trade" htmlFor="bt-mb">
                  <Input id="bt-mb" type="number" min={1} step={1} value={maxBars} onChange={(e) => setMaxBars(Number(e.target.value))} />
                </Field>
                <Field label="Daily loss stop (%)" htmlFor="bt-dl" hint="0 = off">
                  <Input id="bt-dl" type="number" min={0} max={20} step={0.5} value={maxDaily} onChange={(e) => setMaxDaily(Number(e.target.value))} />
                </Field>
              </div>
              <label className="flex items-center justify-between gap-2 rounded-sm border border-line bg-panel-2 px-2.5 py-1.5 text-xs">
                Move stop to breakeven after partial
                <Switch checked={breakeven} onCheckedChange={setBreakeven} aria-label="Move stop to breakeven" />
              </label>
              {Object.keys(stratParams).length ? (
                <details className="rounded-sm border border-line bg-panel-2/50 p-2" open={mode === "single"}>
                  <summary className="cursor-pointer text-xs font-medium text-fg">Strategy parameters</summary>
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    {Object.entries(stratParams).map(([k, v]) => (
                      <ParamInput key={k} name={k} value={v} onChange={(nv) => setParam(k, nv)} />
                    ))}
                  </div>
                  {mode === "wf" ? <p className="mt-2 text-[0.66rem] text-faint">Walk-forward searches the strategy&apos;s predefined parameter grid on each TRAIN window; values here are the baseline.</p> : null}
                </details>
              ) : null}
              {mode === "wf" ? (
                <div className="grid grid-cols-2 gap-2 rounded-sm border border-accent-2/30 bg-accent-2/5 p-2">
                  <Field label="Train bars" htmlFor="wf-train">
                    <Input id="wf-train" type="number" min={200} step={100} value={wf.train_bars} onChange={(e) => setWf({ ...wf, train_bars: Number(e.target.value) })} />
                  </Field>
                  <Field label="Validation bars" htmlFor="wf-val">
                    <Input id="wf-val" type="number" min={50} step={50} value={wf.validation_bars} onChange={(e) => setWf({ ...wf, validation_bars: Number(e.target.value) })} />
                  </Field>
                  <Field label="Test bars" htmlFor="wf-test">
                    <Input id="wf-test" type="number" min={50} step={50} value={wf.test_bars} onChange={(e) => setWf({ ...wf, test_bars: Number(e.target.value) })} />
                  </Field>
                  <Field label="Max windows" htmlFor="wf-win">
                    <Input id="wf-win" type="number" min={1} max={50} value={wf.max_windows} onChange={(e) => setWf({ ...wf, max_windows: Number(e.target.value) })} />
                  </Field>
                  <p className="col-span-2 text-[0.66rem] text-muted">TRAIN → choose parameters · VALIDATION → confirm · TEST → report on unseen data, then roll the window forward.</p>
                </div>
              ) : null}
              {err ? <Callout tone="down" title="Run failed">{err}</Callout> : null}
              <Button variant="primary" size="lg" onClick={run} disabled={busy || !strategies.data}>
                {busy ? <Spinner label={`Running… ${elapsed}s`} className="text-bg" /> : <><Play /> {mode === "single" ? "Run Backtest" : "Run Walk-Forward"}</>}
              </Button>
            </PanelBody>
          </Panel>
        </div>

        <div className="flex min-w-0 flex-col gap-3">
          <Panel>
            <PanelHeader title="Run history" icon={<History />} subtitle="Click a run to view its full report" />
            <DataBlock data={history.data} error={history.error} isLoading={history.isLoading} onRetry={() => history.mutate()} isEmpty={(d) => !d.length} empty={<EmptyState title="No backtests yet" description="Configure a run on the left." />}>
              {(rows) => (
                <div className="max-h-72 overflow-y-auto">
                  <Table>
                    <THead>
                      <tr>
                        <TH>When</TH>
                        <TH>Kind</TH>
                        <TH>Strategy</TH>
                        <TH>Market</TH>
                        <TH align="right">Trades</TH>
                        <TH align="right">Exp. R</TH>
                        <TH align="right">Net</TH>
                        <TH align="right">Max DD</TH>
                        <TH>Data</TH>
                      </tr>
                    </THead>
                    <tbody>
                      {rows.map((b) => (
                        <TR key={b.id} onClick={() => setSelected(b.id)} className={cn("cursor-pointer", selected === b.id && "bg-elevated/70")} aria-selected={selected === b.id}>
                          <TD className="num text-muted">{fmtDateTime(b.created_at).slice(0, 18)}</TD>
                          <TD>
                            <Badge tone={b.kind === "WALK_FORWARD" ? "purple" : "neutral"}>{b.kind === "WALK_FORWARD" ? "WF" : "BT"}</Badge>
                          </TD>
                          <TD className="font-medium">{b.strategy}</TD>
                          <TD className="num text-muted">
                            {b.symbol} {b.timeframe}
                          </TD>
                          <TD align="right" className="num">
                            {b.metrics?.total_trades ?? "—"}
                          </TD>
                          <TD align="right" className={cn("num", (b.metrics?.expectancy_r ?? 0) >= 0 ? "text-up" : "text-down")}>
                            {fmtR(b.metrics?.expectancy_r)}
                          </TD>
                          <TD align="right" className={cn("num", (b.metrics?.net_profit ?? 0) >= 0 ? "text-up" : "text-down")}>
                            {b.metrics ? fmtMoney(b.metrics.net_profit, 0, true) : "—"}
                          </TD>
                          <TD align="right" className="num text-down">
                            {b.metrics ? `${fmtNum(b.metrics.max_drawdown_pct, 1)}%` : "—"}
                          </TD>
                          <TD>{b.is_demo ? <ModeBadge mode="DEMO" /> : <Badge tone="info">{b.provider}</Badge>}</TD>
                        </TR>
                      ))}
                    </tbody>
                  </Table>
                </div>
              )}
            </DataBlock>
          </Panel>
          {shown ? (
            <>
              <div className="flex justify-end">
                <Link href={`/backtesting/${shown.id}`} className="text-[0.7rem] text-muted hover:text-accent">
                  Permalink →
                </Link>
              </div>
              <BacktestResultView bt={shown} />
            </>
          ) : selected && selectedDetail.isLoading ? (
            <Spinner label="Loading report…" />
          ) : (
            <Panel>
              <EmptyState icon={<FlaskConical />} title="No run selected" description="Run a backtest or pick one from the history to see equity, drawdown, monthly returns, trade distribution and the full trade list." />
            </Panel>
          )}
        </div>
      </div>
      <RiskNotice>Backtests are simulations. Results on DEMO data describe synthetic prices only. Past or simulated performance does not guarantee future results.</RiskNotice>
    </PageContainer>
  );
}
