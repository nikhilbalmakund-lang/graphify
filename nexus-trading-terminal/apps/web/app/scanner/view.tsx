"use client";

import type { ScannerRow, Timeframe } from "@nexus/shared-types";
import { Radar, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Callout, RiskNotice } from "@/components/common/disclaimer";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { DataBlock, EmptyState } from "@/components/common/states";
import { DirectionBadge, ModeBadge, RegimeBadge, StatusBadge, TrendBadge } from "@/components/market/badges";
import { TimeframeTabs } from "@/components/market/pickers";
import { Change } from "@/components/market/price";
import { ScoreBar, ScoreGauge } from "@/components/signals/score";
import { Badge } from "@/components/ui/badge";
import { Field, Input, Select } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Switch } from "@/components/ui/switch";
import { Table, TD, TH, THead, TR, useSort } from "@/components/ui/table";
import { Tip } from "@/components/ui/tooltip";
import { useApi } from "@/hooks/use-api";
import { qs } from "@/lib/api";
import { ANALYSIS_TIMEFRAMES, REGIME_LABEL } from "@/lib/constants";
import { fmtCountdown, fmtNum, fmtPrice, fmtRR } from "@/lib/format";
import { cn } from "@/lib/utils";

interface ScanResult {
  timeframe: string;
  mode: string;
  is_demo: boolean;
  provider: string;
  rows: ScannerRow[];
  errors: ScannerRow[];
  note: string;
}

export function ScannerView() {
  const router = useRouter();
  const [tf, setTf] = useState<Timeframe>("15m");
  const [minScore, setMinScore] = useState(0);
  const [minRr, setMinRr] = useState(0);
  const [maxVol, setMaxVol] = useState(100);
  const [noNews, setNoNews] = useState(false);
  const [onlySignals, setOnlySignals] = useState(false);
  const [regime, setRegime] = useState("");
  const { data, error, isLoading, mutate } = useApi<ScanResult>(
    `/api/scanner${qs({ timeframe: tf, min_score: minScore || undefined, min_rr: minRr || undefined, max_vol_percentile: maxVol < 100 ? maxVol : undefined, exclude_news_risk: noNews || undefined, only_signals: onlySignals || undefined, regime: regime || undefined })}`,
    60_000,
  );
  const { sorted, sort, onSort } = useSort(data?.rows ?? [], { key: "score", dir: "desc" });
  const top = (data?.rows ?? []).filter((r) => r.direction !== "NO_TRADE").slice(0, 3);

  return (
    <PageContainer>
      <PageHeader
        title="Market Scanner"
        description="Scores every configured instrument with the deterministic pipeline (no AI calls). Filter by score, R:R, volatility, news risk and regime."
        badges={data ? <ModeBadge mode={data.is_demo ? "DEMO" : "LIVE"} /> : null}
        actions={<TimeframeTabs value={tf} onChange={setTf} options={ANALYSIS_TIMEFRAMES} />}
      />
      <Panel>
        <PanelHeader title="Filters" icon={<SlidersHorizontal />} />
        <PanelBody className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Field label={`Min score · ${minScore}`} htmlFor="f-score">
            <Input id="f-score" type="range" min={0} max={100} step={5} value={minScore} onChange={(e) => setMinScore(+e.target.value)} className="h-8 accent-[var(--color-accent)]" />
          </Field>
          <Field label="Min R:R" htmlFor="f-rr">
            <Input id="f-rr" type="number" min={0} step={0.5} value={minRr} onChange={(e) => setMinRr(Math.max(0, +e.target.value))} />
          </Field>
          <Field label={`Max volatility pct · ${maxVol}`} htmlFor="f-vol">
            <Input id="f-vol" type="range" min={50} max={100} step={5} value={maxVol} onChange={(e) => setMaxVol(+e.target.value)} className="h-8 accent-[var(--color-accent)]" />
          </Field>
          <Field label="Regime" htmlFor="f-regime">
            <Select id="f-regime" value={regime} onChange={(e) => setRegime(e.target.value)}>
              <option value="">Any regime</option>
              {Object.entries(REGIME_LABEL).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </Select>
          </Field>
          <label className="flex items-center justify-between gap-2 self-end rounded-sm border border-line bg-panel-2 px-2.5 py-1.5 text-xs text-fg">
            Exclude news risk
            <Switch checked={noNews} onCheckedChange={setNoNews} aria-label="Exclude news risk" />
          </label>
          <label className="flex items-center justify-between gap-2 self-end rounded-sm border border-line bg-panel-2 px-2.5 py-1.5 text-xs text-fg">
            Only LONG / SHORT
            <Switch checked={onlySignals} onCheckedChange={setOnlySignals} aria-label="Only directional signals" />
          </label>
        </PanelBody>
      </Panel>

      {data?.note ? <Callout tone="warn">{data.note}</Callout> : null}

      {top.length ? (
        <section aria-label="Top setups" className="grid gap-3 md:grid-cols-3">
          {top.map((r, i) => (
            <Link key={r.symbol} href={`/signals/${r.signal_id}`} className="panel flex items-center gap-3 p-3 transition-colors hover:border-accent/40">
              <span className="num text-2xl font-bold text-faint">#{i + 1}</span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-fg-strong">{r.symbol}</span>
                  <DirectionBadge direction={r.direction} />
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted">
                  <RegimeBadge regime={r.regime} />
                  <span className="num">R:R {fmtRR(r.rr)}</span>
                </div>
              </div>
              <ScoreGauge score={r.score} size={52} />
            </Link>
          ))}
        </section>
      ) : null}

      <Panel>
        <PanelHeader title="Scan results" icon={<Radar />} subtitle={data ? `${data.rows.length} instruments · ${tf}` : undefined} />
        <DataBlock
          data={data}
          error={error}
          isLoading={isLoading}
          onRetry={() => mutate()}
          rows={10}
          isEmpty={(d) => !d.rows.length}
          empty={<EmptyState title="No instruments match these filters" description="Loosen the filters to see more of the market. A short list is normal: most bars are NO_TRADE." />}
        >
          {() => (
            <Table>
              <THead>
                <tr>
                  <TH sortKey="symbol" sort={sort} onSort={onSort}>
                    Asset
                  </TH>
                  <TH sortKey="price" sort={sort} onSort={onSort} align="right">
                    Price
                  </TH>
                  <TH sortKey="change_pct_24h" sort={sort} onSort={onSort} align="right">
                    24H
                  </TH>
                  <TH sortKey="trend_score" sort={sort} onSort={onSort}>
                    Trend
                  </TH>
                  <TH sortKey="regime" sort={sort} onSort={onSort}>
                    Regime
                  </TH>
                  <TH sortKey="score" sort={sort} onSort={onSort}>
                    Score
                  </TH>
                  <TH sortKey="rr" sort={sort} onSort={onSort} align="right">
                    R:R
                  </TH>
                  <TH sortKey="direction" sort={sort} onSort={onSort}>
                    Signal
                  </TH>
                  <TH sortKey="risk" sort={sort} onSort={onSort}>
                    Risk
                  </TH>
                  <TH>Why / next event</TH>
                </tr>
              </THead>
              <tbody>
                {sorted.map((r) => (
                  <TR key={r.symbol} className="cursor-pointer" onClick={() => router.push(`/signals/${r.signal_id}`)}>
                    <TD className="font-semibold text-fg">{r.symbol}</TD>
                    <TD align="right" className="num">
                      {fmtPrice(r.price, r.symbol)}
                    </TD>
                    <TD align="right">
                      <Change pct={r.change_pct_24h} />
                    </TD>
                    <TD>
                      <TrendBadge trend={r.trend} />
                    </TD>
                    <TD>
                      <RegimeBadge regime={r.regime} />
                    </TD>
                    <TD>
                      <ScoreBar score={r.score} />
                    </TD>
                    <TD align="right" className="num">
                      {fmtRR(r.rr)}
                    </TD>
                    <TD>
                      <div className="flex items-center gap-1">
                        <DirectionBadge direction={r.direction} />
                        {r.direction !== "NO_TRADE" ? <StatusBadge status={r.signal_status} /> : null}
                      </div>
                    </TD>
                    <TD>
                      <Tip content={`Volatility percentile ${fmtNum(r.vol_percentile, 0)}${r.news_risk ? " · high-impact event within 2h" : ""}`}>
                        <Badge tone={r.risk === "HIGH" ? "down" : r.risk === "ELEVATED" ? "warn" : "neutral"} className="cursor-help">
                          {r.risk}
                        </Badge>
                      </Tip>
                    </TD>
                    <TD className={cn("max-w-80 truncate text-xs", r.news_risk ? "text-warn" : "text-muted")}>
                      {r.direction === "NO_TRADE" && r.no_trade_reasons.length ? r.no_trade_reasons[0] : r.next_event ? `${r.next_event}${r.next_event_minutes !== null ? ` in ${fmtCountdown(r.next_event_minutes)}` : ""}` : "—"}
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          )}
        </DataBlock>
        {data?.errors.length ? (
          <PanelBody className="border-t border-line text-xs text-down">
            {data.errors.map((e) => (
              <p key={e.symbol}>
                {e.symbol}: {e.error}
              </p>
            ))}
          </PanelBody>
        ) : null}
      </Panel>
      <RiskNotice />
    </PageContainer>
  );
}
