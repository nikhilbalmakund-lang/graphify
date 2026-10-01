"use client";

import type { CalibrationReport, ConditionsSummary, SignalDetail } from "@nexus/shared-types";
import { ArrowLeft, BrainCircuit, CandlestickChart, ClipboardCheck, Gauge, History, Layers, ListChecks, MessageSquareText, ShieldCheck, Sigma, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { ProviderLabel } from "@/components/ai/briefing-panel";
import { entryMarker, signalLevels } from "@/components/charts/levels";
import { MiniChart } from "@/components/charts/mini-chart";
import { Callout, RiskNotice } from "@/components/common/disclaimer";
import { BulletList, ExplainedSections, type Explained } from "@/components/common/explained";
import { PageContainer } from "@/components/common/page-header";
import { KV } from "@/components/common/stat";
import { DataBlock, ErrorState, LoadingRows } from "@/components/common/states";
import { DataBadge, DirectionBadge, RegimeBadge, StatusBadge } from "@/components/market/badges";
import { MTFTable } from "@/components/market/mtf-table";
import { AIReview } from "@/components/signals/ai-review";
import { EvidencePanel, FilterList, RiskDecisionPanel, ScoreBreakdown } from "@/components/signals/breakdown";
import { ScoreGauge } from "@/components/signals/score";
import { AgreementBadge, entryText } from "@/components/signals/signal-card";
import { usePaperTrade } from "@/components/signals/use-paper-trade";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApi } from "@/hooks/use-api";
import { useNow } from "@/hooks/use-now";
import { errorMessage, post } from "@/lib/api";
import { SYMBOL_NAMES } from "@/lib/constants";
import { fmtCountdown, fmtDateTime, fmtFrac, fmtNum, fmtPrice, fmtR, fmtRR, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

interface Similar {
  summary: ConditionsSummary;
  matches: { timestamp: string; direction: string; regime: string; score: number; outcome: string; r_multiple: number | null; distance: number }[];
}

interface ExplainResult {
  explanation: Explained;
  provider: string;
  model: string;
  is_ai: boolean;
  warnings: string[];
}

function Plan({ s }: { s: SignalDetail }) {
  const now = useNow();
  const mins = s.expires_at && now ? (new Date(s.expires_at).getTime() - now) / 60000 : null;
  const risk = s.entry_price !== null && s.stop !== null ? Math.abs(s.entry_price - s.stop) : null;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <ScoreGauge score={s.score} size={76} />
        <div className="flex flex-col gap-1 text-xs">
          <span className="label">Signal score</span>
          <span className="num text-muted">
            Long {fmtNum(s.score_long, 1)} · Short {fmtNum(s.score_short, 1)}
          </span>
          <span className="text-[0.66rem] text-faint">Rule-based quality score, not a win probability.</span>
        </div>
      </div>
      {s.direction !== "NO_TRADE" ? (
        <div className="flex flex-col divide-y divide-line/60 text-xs">
          <KV k={`Entry (${s.entry_type ?? "—"})`} v={<span className="text-accent">{entryText(s)}</span>} />
          <KV k="Stop" v={<span className="text-down">{fmtPrice(s.stop, s.symbol)}</span>} />
          {risk !== null ? <KV k="Risk distance" v={fmtPrice(risk, s.symbol)} /> : null}
          {s.targets.map((t) => (
            <div key={t.label} className="py-1">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-muted">
                  {t.label} <span className="text-faint">· {(t.allocation * 100).toFixed(0)}% of position</span>
                </span>
                <span className="num text-up">
                  {fmtPrice(t.price, s.symbol)} <span className="text-faint">({t.rr.toFixed(1)}R)</span>
                </span>
              </div>
              <p className="text-[0.66rem] text-faint">{t.basis}</p>
            </div>
          ))}
          <KV k="R:R to TP1" v={fmtRR(s.rr)} />
          <KV k="Effective R:R (exit plan)" v={fmtRR(s.effective_rr)} />
          <KV k="Expiry" v={s.status === "ACTIVE" && mins !== null ? `${s.expiry_bars} candles · ${mins > 0 ? fmtCountdown(mins) : "now"}` : `${s.expiry_bars} candles`} />
        </div>
      ) : null}
      {s.invalidation_text ? (
        <div>
          <p className="label mb-1">Invalidation</p>
          <p className="text-xs text-fg">{s.invalidation_text}</p>
        </div>
      ) : null}
    </div>
  );
}

function Calibration({ s }: { s: SignalDetail }) {
  const { data } = useApi<{ report: CalibrationReport | null; loaded: boolean }>("/api/strategies/ml");
  if (s.calibrated_probability === null) {
    return (
      <p className="text-[0.7rem] text-faint">
        No calibrated probability shown: the outcome model is not calibrated for this context, so the score is not converted into a probability.
      </p>
    );
  }
  const r = data?.report;
  return (
    <Callout tone="accent" title={`Calibrated estimate: TP1 reached before stop ≈ ${fmtFrac(s.calibrated_probability, 0)}`}>
      From a statistically calibrated model ({r?.model_name ?? "outcome model"} v{r?.model_version ?? "?"}) evaluated out-of-sample
      {r ? ` (test n=${r.n_test}, ECE ${fmtNum(r.ece, 3)}, Brier skill ${fmtNum(r.brier_skill, 3)})` : ""}. {r?.data_mode === "DEMO" || s.is_demo ? "Trained on DEMO data - illustrative only." : ""} It is an estimate with uncertainty, not a guarantee.
    </Callout>
  );
}

export function SignalDetailView({ id }: { id: string }) {
  const { data: s, error, mutate } = useApi<SignalDetail>(`/api/signals/${id}`, 20_000);
  const similar = useApi<Similar>(s ? `/api/signals/${id}/similar` : null);
  const { execute, busy } = usePaperTrade();
  const [explain, setExplain] = useState<ExplainResult | null>(null);
  const [explaining, setExplaining] = useState(false);

  if (error && !s) {
    return (
      <PageContainer>
        <ErrorState error={error} onRetry={() => mutate()} />
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link href="/signals">
            <ArrowLeft /> Back to signals
          </Link>
        </Button>
      </PageContainer>
    );
  }
  if (!s) {
    return (
      <PageContainer>
        <LoadingRows rows={10} />
      </PageContainer>
    );
  }

  const isTrade = s.direction !== "NO_TRADE";
  const runExplain = async () => {
    setExplaining(true);
    try {
      setExplain(await post<ExplainResult>(`/api/signals/${id}/explain`));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setExplaining(false);
    }
  };
  const a = s.analysis;

  return (
    <PageContainer>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <Link href="/signals" className="mb-1 inline-flex items-center gap-1 text-[0.7rem] text-muted hover:text-accent">
            <ArrowLeft className="size-3" /> Signals
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-bold tracking-wide text-fg-strong">{s.symbol}</h1>
            <span className="text-sm text-muted">{SYMBOL_NAMES[s.symbol]}</span>
            <span className="num rounded-xs border border-line px-1.5 text-xs text-muted">{s.timeframe}</span>
            <DirectionBadge direction={s.direction} size="lg" />
            <StatusBadge status={s.status} />
            <RegimeBadge regime={s.regime} />
            <DataBadge isDemo={s.is_demo} provider={s.provider} />
            {s.ai_summary ? <AgreementBadge agreement={s.ai_summary.agreement} /> : null}
          </div>
          <p className="num mt-1 text-[0.7rem] text-faint">
            {s.id} · generated {fmtDateTime(s.created_at)} on bar {fmtDateTime(s.bar_time)} · price {fmtPrice(s.price, s.symbol)} · source {s.source}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm" variant="outline">
            <Link href={`/chart?symbol=${s.symbol}&tf=${s.timeframe}&signal=${s.id}`}>
              <CandlestickChart /> Chart
            </Link>
          </Button>
          <Button size="sm" variant="outline" onClick={runExplain} disabled={explaining}>
            <MessageSquareText /> {explaining ? "Explaining…" : "Explain"}
          </Button>
          {isTrade && s.status === "ACTIVE" ? (
            <Button size="sm" variant="primary" onClick={() => execute(s)} disabled={busy === s.id}>
              <Gauge /> Paper trade
            </Button>
          ) : null}
        </div>
      </div>

      {explain ? (
        <Panel>
          <PanelHeader title="Explanation" icon={<Sparkles />} actions={<ProviderLabel isAi={explain.is_ai} provider={explain.provider} model={explain.model} />} />
          <PanelBody>
            <ExplainedSections value={explain.explanation} />
            {explain.warnings.length ? <BulletList items={explain.warnings} tone="warn" /> : null}
          </PanelBody>
        </Panel>
      ) : null}

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel className="xl:col-span-2">
          <PanelHeader title="Chart & plan levels" icon={<CandlestickChart />} subtitle={`${s.timeframe} candles · entry, stop and targets`} />
          <MiniChart symbol={s.symbol} timeframe={s.timeframe} levels={signalLevels(s)} markers={entryMarker(s)} height={360} />
        </Panel>
        <Panel>
          <PanelHeader title={isTrade ? "Trade plan" : "No-trade decision"} icon={<ClipboardCheck />} />
          <PanelBody className="flex flex-col gap-3">
            <Plan s={s} />
            {!isTrade ? (
              <div>
                <p className="label mb-1">Reasons</p>
                <BulletList items={s.no_trade_reasons} tone="down" />
              </div>
            ) : null}
            <Calibration s={s} />
          </PanelBody>
        </Panel>
      </div>

      <Tabs defaultValue="factors">
        <TabsList>
          <TabsTrigger value="factors">Factors & score</TabsTrigger>
          <TabsTrigger value="ai">AI review</TabsTrigger>
          <TabsTrigger value="evidence">Historical evidence</TabsTrigger>
          <TabsTrigger value="risk">Risk engine</TabsTrigger>
          <TabsTrigger value="context">Market context</TabsTrigger>
          <TabsTrigger value="strategies">Strategies</TabsTrigger>
          <TabsTrigger value="audit">Versions & outcome</TabsTrigger>
        </TabsList>

        <TabsContent value="factors">
          <div className="grid gap-3 lg:grid-cols-3">
            <Panel>
              <PanelHeader title="Score breakdown" icon={<Sigma />} />
              <PanelBody>
                <ScoreBreakdown components={s.components} mtfAdjustment={s.mtf_adjustment} total={s.score} />
              </PanelBody>
            </Panel>
            <Panel>
              <PanelHeader title="Supporting / opposing" icon={<ListChecks />} />
              <PanelBody className="flex flex-col gap-3">
                <div>
                  <p className="label mb-1">Supporting factors</p>
                  <BulletList items={s.supporting} tone="up" />
                </div>
                <div>
                  <p className="label mb-1">Opposing factors</p>
                  <BulletList items={s.opposing} tone="warn" />
                </div>
              </PanelBody>
            </Panel>
            <Panel>
              <PanelHeader title="Filters" icon={<ShieldCheck />} subtitle="A high score alone never creates a signal" />
              <PanelBody className="py-1">
                <FilterList filters={s.filters} />
              </PanelBody>
            </Panel>
          </div>
        </TabsContent>

        <TabsContent value="ai">
          <Panel>
            <PanelBody>
              <AIReview rows={s.ai_analyses} summary={s.ai_summary} />
            </PanelBody>
          </Panel>
        </TabsContent>

        <TabsContent value="evidence">
          <div className="grid gap-3 lg:grid-cols-2">
            <Panel>
              <PanelHeader title="Similar historical setups" icon={<History />} subtitle="Nearest neighbours in feature space (same asset & timeframe, before this signal)" />
              <PanelBody>
                <EvidencePanel evidence={s.evidence} />
              </PanelBody>
            </Panel>
            <Panel>
              <PanelHeader title="Nearest matches" subtitle="Outcome of each similar past setup" />
              <DataBlock data={similar.data} error={similar.error} isLoading={similar.isLoading} onRetry={() => similar.mutate()}>
                {(d) => (
                  <div className="max-h-80 overflow-y-auto">
                    <Table>
                      <THead>
                        <tr>
                          <TH>Date</TH>
                          <TH>Dir</TH>
                          <TH>Regime</TH>
                          <TH align="right">Score</TH>
                          <TH>Outcome</TH>
                          <TH align="right">R</TH>
                          <TH align="right">Dist.</TH>
                        </tr>
                      </THead>
                      <tbody>
                        {d.matches.slice(0, 50).map((m, i) => (
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
                            <TD align="right" className="num text-faint">
                              {fmtNum(m.distance, 2)}
                            </TD>
                          </TR>
                        ))}
                      </tbody>
                    </Table>
                    <ul className="list-disc px-6 py-2 text-[0.68rem] text-muted">
                      {d.summary.caveats.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </DataBlock>
            </Panel>
          </div>
        </TabsContent>

        <TabsContent value="risk">
          <Panel>
            <PanelHeader title="Deterministic risk engine" icon={<ShieldCheck />} subtitle="Final veto. Neither AI nor the signal engine can bypass it." />
            <PanelBody>
              <RiskDecisionPanel decision={s.risk_decision} />
            </PanelBody>
          </Panel>
        </TabsContent>

        <TabsContent value="context">
          {a ? (
            <div className="grid gap-3 xl:grid-cols-3">
              <Panel className="xl:col-span-2">
                <PanelHeader title="Multi-timeframe alignment" icon={<Layers />} />
                <PanelBody>
                  <MTFTable mtf={a.mtf} symbol={s.symbol} />
                </PanelBody>
              </Panel>
              <Panel>
                <PanelHeader title="Regime" icon={<BrainCircuit />} subtitle={`v${a.regime.version} · clarity ${fmtNum(a.regime.clarity, 2)}`} />
                <PanelBody className="flex flex-col gap-2 text-xs">
                  <RegimeBadge regime={a.regime.regime} />
                  <p className="text-fg">{a.regime.explanation}</p>
                  <div className="flex flex-wrap gap-1">
                    {a.regime.flags.map((f) => (
                      <RegimeBadge key={f} regime={f} />
                    ))}
                  </div>
                </PanelBody>
              </Panel>
              <Panel>
                <PanelHeader title="Market structure" subtitle="Heuristic concepts are labelled" />
                <PanelBody className="flex flex-col text-xs">
                  <KV k="Structure trend" v={titleCase(a.structure.trend)} mono={false} />
                  <KV k="Recent swings" v={a.structure.recent_labels.join(" · ") || "—"} />
                  <KV k="Last event" v={a.structure.last_event ? `${a.structure.last_event.type} ${titleCase(a.structure.last_event.direction)} · ${a.structure.last_event.bars_ago} bars ago` : "—"} />
                  <KV k="Range" v={a.structure.range.is_range ? `${fmtPrice(a.structure.range.low, s.symbol)} – ${fmtPrice(a.structure.range.high, s.symbol)}` : "No range"} />
                  <KV k="Breakout" v={a.structure.breakout ? `${titleCase(a.structure.breakout.direction)} @ ${fmtPrice(a.structure.breakout.level, s.symbol)}${a.structure.breakout.retested ? " (retested)" : ""}${a.structure.breakout.failed ? " (failed)" : ""}` : "—"} />
                  <KV k="Liquidity sweep*" v={a.structure.sweep ? `${titleCase(a.structure.sweep.direction)} @ ${fmtPrice(a.structure.sweep.level, s.symbol)}` : "—"} />
                  <p className="mt-2 text-[0.66rem] text-faint">* {a.structure.heuristic_note}</p>
                </PanelBody>
              </Panel>
              <Panel>
                <PanelHeader title="Macro, sentiment & events" />
                <PanelBody className="flex flex-col gap-1 text-xs">
                  {Object.entries(a.context).map(([k, v]) => (
                    <div key={k} className="border-b border-line/60 pb-1.5 last:border-0">
                      <p className="label">{titleCase(k)}</p>
                      <p className="text-fg">
                        {String(v.detail ?? "") ||
                          Object.entries(v)
                            .filter(([, x]) => typeof x === "number" || typeof x === "string" || typeof x === "boolean")
                            .slice(0, 5)
                            .map(([kk, x]) => `${kk}: ${typeof x === "number" ? fmtNum(x, 2) : String(x)}`)
                            .join(" · ")}
                      </p>
                    </div>
                  ))}
                </PanelBody>
              </Panel>
              <Panel>
                <PanelHeader title="Data quality" subtitle={`${a.data_quality.bars} bars · ${a.data_quality.provider}`} />
                <PanelBody className="flex flex-col text-xs">
                  <KV k="Quality score" v={fmtNum(a.data_quality.quality_score, 2)} />
                  <KV k="Usable" v={a.data_quality.usable ? "Yes" : "No"} mono={false} />
                  <KV k="Stale" v={a.data_quality.is_stale ? "Yes" : "No"} mono={false} />
                  <KV k="Missing / duplicate bars" v={`${a.data_quality.missing_bars} / ${a.data_quality.duplicate_bars}`} />
                  {a.data_quality.issues.map((i) => (
                    <p key={i.code} className={cn("mt-1 text-[0.68rem]", i.severity === "CRITICAL" ? "text-down" : "text-warn")}>
                      {i.code}: {i.detail}
                    </p>
                  ))}
                </PanelBody>
              </Panel>
            </div>
          ) : (
            <Callout tone="info">Analysis snapshot not stored for this signal.</Callout>
          )}
        </TabsContent>

        <TabsContent value="strategies">
          <Panel>
            <PanelHeader title="Strategy ensemble" subtitle={s.ensemble?.summary} />
            {s.ensemble ? (
              <Table>
                <THead>
                  <tr>
                    <TH>Strategy</TH>
                    <TH>Applicable</TH>
                    <TH>Vote</TH>
                    <TH align="right">Strength</TH>
                    <TH>Reasons</TH>
                  </tr>
                </THead>
                <tbody>
                  {s.ensemble.votes.map((v) => (
                    <TR key={v.strategy}>
                      <TD className="font-medium">{v.strategy}</TD>
                      <TD className={v.applicable ? "text-up" : "text-faint"}>{v.applicable ? "Yes" : "No (regime)"}</TD>
                      <TD>
                        <DirectionBadge direction={v.direction} />
                      </TD>
                      <TD align="right" className="num">
                        {fmtNum(v.strength, 2)}
                      </TD>
                      <TD className="whitespace-normal text-xs text-muted">{v.reasons.join(" · ")}</TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            ) : (
              <PanelBody>
                <p className="text-xs text-faint">No ensemble data.</p>
              </PanelBody>
            )}
          </Panel>
        </TabsContent>

        <TabsContent value="audit">
          <div className="grid gap-3 lg:grid-cols-2">
            <Panel>
              <PanelHeader title="Versions" subtitle="Stored with the signal for reproducibility" />
              <PanelBody className="flex flex-col text-xs">
                <KV k="Signal engine" v={s.versions.signal_engine} />
                <KV k="Features" v={s.versions.features} />
                <KV k="Risk engine" v={s.versions.risk_engine ?? "—"} />
                {Object.entries(s.versions.prompts).map(([k, v]) => (
                  <KV key={k} k={`Prompt ${k}`} v={v} />
                ))}
                {Object.entries(s.versions.models).map(([k, v]) => (
                  <KV key={k} k={`Model ${k}`} v={v} />
                ))}
                {Object.entries(s.versions.strategies).map(([k, v]) => (
                  <KV key={k} k={`Strategy ${k}`} v={v} />
                ))}
                <KV k="Data mode" v={s.data_mode} />
                <KV k="Provider" v={s.provider} />
              </PanelBody>
            </Panel>
            <Panel>
              <PanelHeader title="Outcome tracking" subtitle="Updated by the signal tracker as price evolves" />
              <PanelBody className="flex flex-col text-xs">
                {s.outcome ? (
                  <>
                    <KV k="Status" v={<StatusBadge status={s.outcome.status} />} />
                    <KV k="Filled" v={s.outcome.filled ? `${fmtPrice(s.outcome.fill_price, s.symbol)} @ ${fmtDateTime(s.outcome.fill_time)}` : "No"} />
                    <KV k="Exit" v={s.outcome.exit_time ? `${titleCase(s.outcome.exit_reason)} @ ${fmtDateTime(s.outcome.exit_time)}` : "—"} />
                    <KV k="R multiple" v={fmtR(s.outcome.r_multiple)} />
                    <KV k="MFE / MAE" v={`${fmtR(s.outcome.mfe_r)} / ${fmtR(s.outcome.mae_r)}`} />
                    <KV k="Targets hit" v={s.outcome.tp_hits.join(", ") || "—"} />
                    <KV k="Updated" v={fmtDateTime(s.outcome.updated_at)} />
                  </>
                ) : (
                  <p className="text-faint">Not tracked (NO_TRADE).</p>
                )}
                {s.is_demo ? (
                  <Badge tone="warn" className="mt-2 self-start">
                    Outcome measured on DEMO prices
                  </Badge>
                ) : null}
              </PanelBody>
            </Panel>
          </div>
        </TabsContent>
      </Tabs>
      <RiskNotice />
    </PageContainer>
  );
}
