import type { AIAnalysisRow, AISummary } from "@nexus/shared-types";
import { Bot, Scale, ShieldAlert } from "lucide-react";

import { BulletList } from "@/components/common/explained";
import { Callout } from "@/components/common/disclaimer";
import { DirectionBadge } from "@/components/market/badges";
import { Badge } from "@/components/ui/badge";
import { fmtMoney, fmtNum } from "@/lib/format";
import { cn } from "@/lib/utils";

import { AgreementBadge } from "./signal-card";

type Out = Record<string, unknown>;
const arr = (o: Out | null, k: string): string[] => (Array.isArray(o?.[k]) ? (o?.[k] as unknown[]).map(String) : []);
const str = (o: Out | null, k: string): string => (typeof o?.[k] === "string" ? (o?.[k] as string) : "");

function Meta({ row }: { row: AIAnalysisRow }) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[0.66rem] text-faint">
      <span>
        {row.provider}
        {row.model ? ` · ${row.model}` : ""}
      </span>
      {row.prompt_name ? (
        <span>
          prompt {row.prompt_name}@{row.prompt_version} ({row.prompt_date})
        </span>
      ) : null}
      {row.latency_ms !== null ? <span className="num">{fmtNum(row.latency_ms / 1000, 1)}s</span> : null}
      {row.input_tokens !== null ? (
        <span className="num">
          {row.input_tokens}→{row.output_tokens} tok
        </span>
      ) : null}
      {row.cost_usd !== null ? <span className="num">≈{fmtMoney(row.cost_usd, 4)}</span> : <span>cost n/a</span>}
    </div>
  );
}

function Validation({ row }: { row: AIAnalysisRow }) {
  const v = row.validation;
  if (!v) return null;
  if (v.valid && !v.issues.length) return <Badge tone="up">Validated</Badge>;
  return (
    <div className="flex flex-col gap-1">
      <Badge tone={v.valid ? "warn" : "down"}>{v.valid ? "Validated with warnings" : "Failed validation"}</Badge>
      <ul className="text-[0.68rem] text-muted">
        {v.issues.map((i, n) => (
          <li key={n}>
            <span className={i.severity === "ERROR" ? "text-down" : "text-warn"}>{i.code}</span> · {i.detail}
          </li>
        ))}
      </ul>
    </div>
  );
}

function AnalystCard({ row, title }: { row: AIAnalysisRow; title: string }) {
  const o = row.output;
  return (
    <div className="flex min-w-0 flex-col gap-2 rounded-sm border border-line bg-panel-2/50 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Bot className="size-3.5 text-accent-2" />
        <p className="text-xs font-semibold text-fg-strong">{title}</p>
        {o ? <DirectionBadge direction={str(o, "direction")} /> : null}
        {o && str(o, "analysis_quality") ? <Badge>Quality {str(o, "analysis_quality")}</Badge> : null}
        <Badge tone={row.status === "OK" ? "up" : "down"}>{row.status}</Badge>
      </div>
      <Meta row={row} />
      {row.error ? <Callout tone="down">{row.error}</Callout> : null}
      {o ? (
        <div className="grid gap-3 text-xs md:grid-cols-2">
          <div>
            <p className="label mb-1">Reasoning (AI interpretation)</p>
            <BulletList items={arr(o, "reasoning")} />
          </div>
          <div>
            <p className="label mb-1">Key risks</p>
            <BulletList items={arr(o, "key_risks")} tone="warn" />
          </div>
          <div>
            <p className="label mb-1">Supporting</p>
            <BulletList items={arr(o, "supporting_factors")} tone="up" />
          </div>
          <div>
            <p className="label mb-1">Opposing</p>
            <BulletList items={arr(o, "opposing_factors")} tone="down" />
          </div>
          {str(o, "invalidation") ? (
            <div className="md:col-span-2">
              <p className="label mb-1">Invalidation</p>
              <p className="text-fg">{str(o, "invalidation")}</p>
            </div>
          ) : null}
          {arr(o, "disagreements").length ? (
            <div className="md:col-span-2">
              <p className="label mb-1">Disagrees with quant engine on</p>
              <BulletList items={arr(o, "disagreements")} tone="warn" />
            </div>
          ) : null}
        </div>
      ) : null}
      <Validation row={row} />
    </div>
  );
}

function CriticCard({ row }: { row: AIAnalysisRow }) {
  const o = row.output;
  const verdict = str(o, "verdict").toLowerCase();
  const sections: [string, string][] = [
    ["reasons", "Reasons"],
    ["unsupported_claims", "Unsupported claims"],
    ["missing_evidence", "Missing evidence"],
    ["contradictions", "Contradictions"],
    ["overconfidence", "Overconfidence"],
    ["risk_reward_issues", "Risk/reward issues"],
    ["news_risk_issues", "News-risk issues"],
    ["data_problems", "Data problems"],
  ];
  return (
    <div className="flex min-w-0 flex-col gap-2 rounded-sm border border-line bg-panel-2/50 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <ShieldAlert className="size-3.5 text-warn" />
        <p className="text-xs font-semibold text-fg-strong">AI critic</p>
        {verdict ? <Badge tone={verdict === "approved" ? "up" : verdict === "rejected" ? "solidDown" : "warn"}>{verdict.replace(/_/g, " ")}</Badge> : null}
        <Badge tone={row.status === "OK" ? "up" : "neutral"}>{row.status}</Badge>
      </div>
      <Meta row={row} />
      {row.error ? <Callout tone="down">{row.error}</Callout> : null}
      <div className="grid gap-3 text-xs md:grid-cols-2">
        {sections
          .filter(([k]) => arr(o, k).length)
          .map(([k, label]) => (
            <div key={k}>
              <p className="label mb-1">{label}</p>
              <BulletList items={arr(o, k)} tone={k === "reasons" ? undefined : "warn"} />
            </div>
          ))}
      </div>
    </div>
  );
}

/** Independent Claude + Gemini reviews, consensus and the critic. AI can only downgrade a signal, never upgrade it. */
export function AIReview({ rows, summary }: { rows: AIAnalysisRow[]; summary: AISummary | null }) {
  const claude = rows.find((r) => r.role === "claude_analyst");
  const gemini = rows.find((r) => r.role === "gemini_analyst");
  const critic = rows.find((r) => r.role === "critic");
  const consensus = rows.find((r) => r.role === "consensus");
  const co = consensus?.output ?? null;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Scale className="size-3.5 text-accent" />
        <span className="text-xs font-semibold text-fg">Consensus</span>
        <AgreementBadge agreement={summary?.agreement} />
        {summary?.downgraded ? <Badge tone="solidWarn">Downgraded to NO TRADE by AI review</Badge> : null}
        {summary?.critic ? <Badge tone={summary.critic.toLowerCase() === "approved" ? "up" : summary.critic.toLowerCase() === "rejected" ? "solidDown" : "warn"}>Critic {summary.critic.replace(/_/g, " ")}</Badge> : null}
      </div>
      {summary?.note ? <p className="text-xs text-muted">{summary.note}</p> : null}
      {co && arr(co, "notes").length ? <BulletList items={arr(co, "notes")} /> : null}
      {summary?.reasons?.length ? <BulletList items={summary.reasons} tone="warn" /> : null}
      {!rows.length ? (
        <Callout tone="info" title="No AI review stored for this signal">
          The quantitative pipeline, filters and risk engine ran without AI. Configure ANTHROPIC_API_KEY and/or GEMINI_API_KEY in Settings to add independent reviews. AI agreement is never treated as proof of correctness.
        </Callout>
      ) : null}
      <div className={cn("grid gap-3", claude && gemini ? "xl:grid-cols-2" : "")}>
        {claude ? <AnalystCard row={claude} title="Claude analyst" /> : null}
        {gemini ? <AnalystCard row={gemini} title="Gemini analyst" /> : null}
      </div>
      {critic ? <CriticCard row={critic} /> : null}
    </div>
  );
}
