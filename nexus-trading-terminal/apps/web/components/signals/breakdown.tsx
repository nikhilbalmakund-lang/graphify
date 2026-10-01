import type { FilterResult, HistoricalEvidence, RiskDecision, ScoreComponent } from "@nexus/shared-types";
import { Check, X } from "lucide-react";

import { Callout } from "@/components/common/disclaimer";
import { Badge } from "@/components/ui/badge";
import { Tip } from "@/components/ui/tooltip";
import { fmtFrac, fmtMoney, fmtNum, fmtR, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

const COMPONENT_LABEL: Record<string, string> = {
  trend: "Trend",
  structure: "Market structure",
  momentum: "Momentum",
  volume_vwap: "Volume / VWAP",
  liquidity: "Liquidity",
  volatility: "Volatility",
  macro: "Macro",
  sentiment: "Sentiment",
};

/** Per-component points out of their configured weight (spec: store and show every component). */
export function ScoreBreakdown({ components, mtfAdjustment, total }: { components: ScoreComponent[]; mtfAdjustment: number; total: number }) {
  return (
    <div className="flex flex-col gap-2">
      {components.map((c) => {
        const pct = c.weight ? (c.points / c.weight) * 100 : 0;
        return (
          <div key={c.name} className="text-xs">
            <div className="mb-1 flex items-baseline justify-between gap-2">
              <Tip
                content={
                  <div className="flex flex-col gap-1">
                    {c.notes_for.length ? <span className="text-up">+ {c.notes_for.join(" · ")}</span> : null}
                    {c.notes_against.length ? <span className="text-down">− {c.notes_against.join(" · ")}</span> : null}
                    {!c.notes_for.length && !c.notes_against.length ? <span>No notes</span> : null}
                  </div>
                }
              >
                <span className="cursor-help text-fg">{COMPONENT_LABEL[c.name] ?? titleCase(c.name)}</span>
              </Tip>
              <span className="num text-muted">
                <span className="font-semibold text-fg-strong">{fmtNum(c.points, 1)}</span> / {fmtNum(c.weight, 0)}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-elevated">
              <div className={cn("h-full rounded-full", pct >= 70 ? "bg-up" : pct >= 45 ? "bg-accent" : "bg-warn")} style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
            </div>
          </div>
        );
      })}
      <div className="mt-1 flex items-center justify-between border-t border-line pt-2 text-xs">
        <Tip content="Multi-timeframe alignment adjustment: +5 when higher timeframes support the direction, −10 when they oppose.">
          <span className="cursor-help text-muted">Multi-timeframe adjustment</span>
        </Tip>
        <span className={cn("num font-semibold", mtfAdjustment > 0 ? "text-up" : mtfAdjustment < 0 ? "text-down" : "text-muted")}>
          {mtfAdjustment > 0 ? "+" : ""}
          {fmtNum(mtfAdjustment, 1)}
        </span>
      </div>
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-fg">Total signal score</span>
        <span className="num font-bold text-fg-strong">{fmtNum(total, 1)} / 100</span>
      </div>
    </div>
  );
}

export function FilterList({ filters }: { filters: FilterResult[] }) {
  return (
    <ul className="flex flex-col divide-y divide-line/60">
      {filters.map((f) => (
        <li key={f.name} className="flex items-start gap-2 py-1.5 text-xs">
          {f.passed ? <Check className="mt-0.5 size-3.5 shrink-0 text-up" /> : <X className={cn("mt-0.5 size-3.5 shrink-0", f.blocking ? "text-down" : "text-warn")} />}
          <div className="min-w-0 flex-1">
            <p className="text-fg">
              {titleCase(f.name)}
              {!f.passed && !f.blocking ? <span className="ml-1 text-[0.62rem] text-warn">(warning)</span> : null}
            </p>
            <p className="text-[0.7rem] text-muted">{f.detail}</p>
          </div>
          {f.threshold !== null && f.threshold !== undefined ? (
            <span className="num shrink-0 text-[0.66rem] text-faint">
              {String(f.value ?? "—")} / {String(f.threshold)}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

const SAMPLE_TONE = { NONE: "neutral", INSUFFICIENT: "down", SMALL: "warn", MODERATE: "info", LARGE: "up" } as const;

/** Historical similar-setup evidence, always paired with an explicit sample-size label. */
export function EvidencePanel({ evidence }: { evidence: HistoricalEvidence | null }) {
  if (!evidence) return <p className="text-xs text-faint">No historical evidence available.</p>;
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="num text-lg font-bold text-fg-strong">{evidence.sample_size}</span>
        <span className="text-xs text-muted">similar setups</span>
        <Badge tone={SAMPLE_TONE[evidence.sample_label] ?? "neutral"}>{evidence.sample_label} sample</Badge>
        {evidence.is_demo ? <Badge tone="warn">Demo data</Badge> : null}
      </div>
      {evidence.sample_size > 0 ? (
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs sm:grid-cols-4">
          <div>
            <p className="label">Win rate</p>
            <p className="num text-fg-strong">{fmtFrac(evidence.win_rate, 0)}</p>
          </div>
          <div>
            <p className="label">Average R</p>
            <p className={cn("num", (evidence.avg_r ?? 0) >= 0 ? "text-up" : "text-down")}>{fmtR(evidence.avg_r)}</p>
          </div>
          <div>
            <p className="label">Expectancy</p>
            <p className={cn("num", (evidence.expectancy ?? 0) >= 0 ? "text-up" : "text-down")}>{fmtR(evidence.expectancy)}</p>
          </div>
          <div>
            <p className="label">Max drawdown</p>
            <p className="num text-down">{evidence.max_drawdown_r !== null ? `${fmtNum(evidence.max_drawdown_r, 1)}R` : "—"}</p>
          </div>
        </div>
      ) : null}
      {evidence.sample_label === "INSUFFICIENT" || evidence.sample_label === "SMALL" ? (
        <Callout tone="warn">Small sample: these statistics are not reliable and must not be read as a forecast.</Callout>
      ) : null}
      {evidence.notes.length ? <ul className="list-disc pl-4 text-[0.7rem] text-muted">{evidence.notes.map((n, i) => <li key={i}>{n}</li>)}</ul> : null}
    </div>
  );
}

export function RiskDecisionPanel({ decision }: { decision: RiskDecision | null }) {
  if (!decision) return <p className="text-xs text-faint">Risk engine not evaluated (NO_TRADE signals are not sized).</p>;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={decision.approved ? "solidUp" : "solidDown"}>{decision.approved ? "Approved" : "Vetoed"}</Badge>
        <Badge tone={decision.state === "NORMAL" ? "up" : decision.state === "HALTED" ? "down" : "warn"}>{decision.state}</Badge>
        <span className="text-[0.66rem] text-faint">Risk engine v{decision.engine_version} · deterministic, AI cannot override</span>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
        <div>
          <p className="label">Size</p>
          <p className="num text-fg-strong">{fmtNum(decision.lots, 2)} lots</p>
        </div>
        <div>
          <p className="label">Risk</p>
          <p className="num text-fg-strong">
            {fmtMoney(decision.risk_amount, 0)} · {fmtFrac(decision.risk_pct, 2)}
          </p>
        </div>
        <div>
          <p className="label">Notional</p>
          <p className="num text-fg-strong">{fmtMoney(decision.notional, 0)}</p>
        </div>
        <div>
          <p className="label">Leverage after</p>
          <p className="num text-fg-strong">{fmtNum(decision.leverage_after, 2)}×</p>
        </div>
      </div>
      <ul className="flex flex-col divide-y divide-line/60">
        {decision.checks.map((c) => (
          <li key={c.name} className="flex items-center gap-2 py-1 text-xs">
            {c.passed ? <Check className="size-3.5 shrink-0 text-up" /> : <X className="size-3.5 shrink-0 text-down" />}
            <span className="w-44 shrink-0 text-fg">{titleCase(c.name)}</span>
            <span className="min-w-0 flex-1 truncate text-muted">{c.detail}</span>
          </li>
        ))}
      </ul>
      {decision.reasons.length ? <Callout tone="down" title="Veto reasons">{decision.reasons.join(" · ")}</Callout> : null}
      {decision.sizing_notes.length ? <p className="text-[0.68rem] text-faint">{decision.sizing_notes.join(" · ")}</p> : null}
    </div>
  );
}
