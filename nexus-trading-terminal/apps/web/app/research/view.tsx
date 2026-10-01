"use client";

import type { ResearchResult, ScenarioCase, Timeframe } from "@nexus/shared-types";
import { Microscope, Play } from "lucide-react";
import { useState } from "react";

import { ProviderLabel } from "@/components/ai/briefing-panel";
import { Callout, RiskNotice } from "@/components/common/disclaimer";
import { BulletList } from "@/components/common/explained";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { Spinner } from "@/components/common/states";
import { ModeBadge } from "@/components/market/badges";
import { SymbolSelect, TimeframeTabs } from "@/components/market/pickers";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { errorMessage, post } from "@/lib/api";
import { ANALYSIS_TIMEFRAMES } from "@/lib/constants";
import { fmtDateTime, fmtPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

function ScenarioCard({ s, symbol }: { s: ScenarioCase; symbol: string }) {
  const tone = s.name === "BULLISH" ? "border-up/40 text-up" : s.name === "BEARISH" ? "border-down/40 text-down" : "border-line-strong text-muted";
  return (
    <div className={cn("flex flex-col gap-2 rounded-sm border bg-panel-2/50 p-3", tone.split(" ")[0])}>
      <p className={cn("text-xs font-bold tracking-wider", tone.split(" ")[1])}>{s.name.replace("_", "-")} SCENARIO</p>
      <dl className="grid grid-cols-[96px_1fr] gap-x-2 gap-y-1.5 text-xs">
        <dt className="text-muted">{s.name === "NO_TRADE" ? "Conditions" : "Trigger"}</dt>
        <dd className="text-fg">
          {s.trigger}
          {s.trigger_level !== null ? <span className="num ml-1 text-accent">({fmtPrice(s.trigger_level, symbol)})</span> : null}
        </dd>
        <dt className="text-muted">Confirmation</dt>
        <dd className="text-fg">{s.confirmation}</dd>
        <dt className="text-muted">Invalidation</dt>
        <dd className="text-fg">
          {s.invalidation}
          {s.invalidation_level !== null ? <span className="num ml-1 text-down">({fmtPrice(s.invalidation_level, symbol)})</span> : null}
        </dd>
        {s.targets.length ? (
          <>
            <dt className="text-muted">Reference levels</dt>
            <dd className="num text-up">{s.targets.map((t) => fmtPrice(t, symbol)).join(" · ")}</dd>
          </>
        ) : null}
      </dl>
      {s.notes ? <p className="text-[0.7rem] text-faint">{s.notes}</p> : null}
    </div>
  );
}

const SECTIONS: [keyof ResearchResult["report"], string, "up" | "down" | "warn" | undefined][] = [
  ["technical_analysis", "Technical analysis", undefined],
  ["macro_context", "Macro context", undefined],
  ["risks", "Risks", "warn"],
  ["historical_evidence", "Historical evidence", undefined],
  ["uncertainty", "Uncertainty", "warn"],
];

export function ResearchView() {
  const [symbol, setSymbol] = useState("XAUUSD");
  const [tf, setTf] = useState<Timeframe>("1H");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [res, setRes] = useState<ResearchResult | null>(null);

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      setRes(await post<ResearchResult>("/api/ai/research", { symbol, timeframe: tf }));
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <PageContainer>
      <PageHeader
        title="Research Workspace"
        description="Select an asset. The researcher gathers available price, technical, macro, news and historical-setup data and writes a structured report with scenarios - never a guaranteed prediction."
        actions={
          <>
            <SymbolSelect value={symbol} onChange={setSymbol} />
            <TimeframeTabs value={tf} onChange={setTf} options={ANALYSIS_TIMEFRAMES} />
            <Button variant="primary" size="sm" onClick={run} disabled={busy}>
              {busy ? <Spinner label="Researching…" className="text-bg" /> : <><Play /> Run research</>}
            </Button>
          </>
        }
      />
      {err ? <Callout tone="down">{err}</Callout> : null}
      {!res && !busy ? (
        <Panel>
          <PanelBody className="flex flex-col items-center gap-2 py-12 text-center">
            <Microscope className="size-7 text-accent" />
            <p className="text-sm text-fg">Market overview · technical analysis · macro context · risks · historical evidence · scenarios</p>
            <p className="max-w-xl text-xs text-muted">The deterministic scenario engine always produces BULLISH, BEARISH and NO-TRADE cases with explicit triggers, confirmations and invalidation levels. When an AI provider is configured it adds a written report grounded in the same data.</p>
          </PanelBody>
        </Panel>
      ) : null}
      {res ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-lg font-bold text-fg-strong">
              {res.symbol} · {res.timeframe}
            </span>
            <ProviderLabel isAi={res.is_ai} provider={res.provider} model={res.model} />
            {res.is_demo_data ? <ModeBadge mode="DEMO" /> : null}
            <span className="num text-[0.7rem] text-faint">generated {fmtDateTime(res.generated_at)}</span>
          </div>
          <Panel>
            <PanelHeader title="Market overview" />
            <PanelBody>
              <p className="text-sm leading-relaxed text-fg">{res.report.market_overview}</p>
            </PanelBody>
          </Panel>
          <div className="grid gap-3 lg:grid-cols-2">
            {SECTIONS.map(([k, label, tone]) => (
              <Panel key={k}>
                <PanelHeader title={label} />
                <PanelBody>
                  <BulletList items={res.report[k] as string[]} tone={tone} empty="Nothing available." />
                </PanelBody>
              </Panel>
            ))}
          </div>
          <Panel>
            <PanelHeader title="Scenarios" subtitle={res.scenarios.basis} />
            <PanelBody className="grid gap-3 lg:grid-cols-3">
              {res.scenarios.scenarios.map((s) => (
                <ScenarioCard key={s.name} s={s} symbol={res.symbol} />
              ))}
            </PanelBody>
            {res.report.scenarios.length && res.is_ai ? (
              <PanelBody className="border-t border-line">
                <p className="label mb-2">AI scenario commentary</p>
                <div className="grid gap-3 lg:grid-cols-3">
                  {res.report.scenarios.map((s, i) => (
                    <div key={i} className="text-xs">
                      <p className="mb-1 font-semibold text-fg">{s.name}</p>
                      <p className="text-muted">
                        {s.trigger} · {s.confirmation} · invalid if {s.invalidation}
                      </p>
                      {s.notes ? <p className="mt-1 text-faint">{s.notes}</p> : null}
                    </div>
                  ))}
                </div>
              </PanelBody>
            ) : null}
          </Panel>
          {res.warnings.length ? <Callout tone="warn" title="Validation warnings">{res.warnings.join(" · ")}</Callout> : null}
        </>
      ) : null}
      <RiskNotice />
    </PageContainer>
  );
}
