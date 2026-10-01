"use client";

import type { Signal } from "@nexus/shared-types";
import { ArrowRight, Clock, ShieldX } from "lucide-react";
import Link from "next/link";

import { BulletList } from "@/components/common/explained";
import { DataBadge, DirectionBadge, RegimeBadge, StatusBadge } from "@/components/market/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tip } from "@/components/ui/tooltip";
import { useNow } from "@/hooks/use-now";
import { SYMBOL_NAMES } from "@/lib/constants";
import { fmtCountdown, fmtPrice, fmtRR, fmtTime } from "@/lib/format";
import { cn } from "@/lib/utils";

import { ScoreGauge } from "./score";

export function entryText(s: Pick<Signal, "entry_type" | "entry_price" | "entry_zone_low" | "entry_zone_high" | "symbol">): string {
  if (s.entry_zone_low !== null && s.entry_zone_high !== null) return `${fmtPrice(s.entry_zone_low, s.symbol)} – ${fmtPrice(s.entry_zone_high, s.symbol)}`;
  return fmtPrice(s.entry_price, s.symbol);
}

const AGREEMENT_TONE = { HIGH: "up", MEDIUM: "accent", LOW: "warn", CONFLICT: "down", SINGLE: "info", UNAVAILABLE: "neutral" } as const;

export function AgreementBadge({ agreement }: { agreement: string | undefined }) {
  const a = (agreement ?? "UNAVAILABLE") as keyof typeof AGREEMENT_TONE;
  return (
    <Tip content="Agreement between independent Claude and Gemini reviews. Agreement does not prove correctness.">
      <Badge tone={AGREEMENT_TONE[a] ?? "neutral"} className="cursor-help">
        AI {a === "UNAVAILABLE" ? "N/A" : a}
      </Badge>
    </Tip>
  );
}

function Level({ label, value, tone, sub }: { label: string; value: string; tone?: "up" | "down" | "accent"; sub?: string }) {
  return (
    <div className="flex min-w-0 flex-col">
      <span className="label">{label}</span>
      <span className={cn("num truncate text-[0.82rem] font-semibold", tone === "up" ? "text-up" : tone === "down" ? "text-down" : tone === "accent" ? "text-accent" : "text-fg-strong")}>{value}</span>
      {sub ? <span className="num text-[0.62rem] text-faint">{sub}</span> : null}
    </div>
  );
}

/** The signal card from the product spec: score, entry/stop/targets, R:R, regime, factors, invalidation, expiry. */
export function SignalCard({ signal: s, compact, onPaper }: { signal: Signal; compact?: boolean; onPaper?: (s: Signal) => void }) {
  const now = useNow();
  const isTrade = s.direction !== "NO_TRADE";
  const minsLeft = s.expires_at && now ? (new Date(s.expires_at).getTime() - now) / 60000 : null;
  const factorLimit = compact ? 4 : 8;
  return (
    <article
      className={cn(
        "panel flex flex-col overflow-hidden transition-colors hover:border-line-strong",
        isTrade && (s.direction === "LONG" ? "shadow-[inset_0_2px_0_var(--color-up)]" : "shadow-[inset_0_2px_0_var(--color-down)]"),
      )}
      aria-label={`${s.symbol} ${s.direction} signal, score ${s.score.toFixed(0)} of 100`}
    >
      <header className="flex items-start gap-3 border-b border-line px-3 py-2.5">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <Link href={`/signals/${s.id}`} className="text-[0.95rem] font-bold tracking-wide text-fg-strong hover:text-accent">
              {s.symbol}
            </Link>
            <span className="num rounded-xs border border-line px-1 text-[0.66rem] text-muted">{s.timeframe}</span>
            <DataBadge isDemo={s.is_demo} provider={s.provider} />
          </div>
          <p className="truncate text-[0.7rem] text-muted">{SYMBOL_NAMES[s.symbol] ?? s.symbol}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <DirectionBadge direction={s.direction} size="lg" />
            <StatusBadge status={s.status} />
            {s.direction === "NO_TRADE" && s.proposed_direction !== "NO_TRADE" ? <Badge tone="neutral">Proposed {s.proposed_direction}</Badge> : null}
            {s.ai_summary ? <AgreementBadge agreement={s.ai_summary.agreement} /> : null}
          </div>
        </div>
        <div className="flex flex-col items-center gap-0.5">
          <ScoreGauge score={s.score} size={compact ? 52 : 60} />
          <span className="text-[0.55rem] font-semibold uppercase tracking-wider text-faint">Signal score</span>
        </div>
      </header>

      {isTrade ? (
        <div className="grid grid-cols-3 gap-x-3 gap-y-2 border-b border-line px-3 py-2.5">
          <Level label={`Entry · ${s.entry_type ?? "—"}`} value={entryText(s)} tone="accent" />
          <Level label="Stop" value={fmtPrice(s.stop, s.symbol)} tone="down" />
          <Level label="R:R" value={fmtRR(s.effective_rr ?? s.rr)} sub={s.effective_rr && s.rr && s.effective_rr !== s.rr ? `TP1 ${fmtRR(s.rr)}` : undefined} />
          {s.targets.slice(0, 3).map((t) => (
            <Tip key={t.label} content={`${t.basis} · ${(t.allocation * 100).toFixed(0)}% of position`}>
              <div className="cursor-help">
                <Level label={`Target ${t.label.replace("TP", "")}`} value={fmtPrice(t.price, s.symbol)} tone="up" sub={`${t.rr.toFixed(1)}R`} />
              </div>
            </Tip>
          ))}
        </div>
      ) : null}

      <div className="flex flex-col gap-2.5 px-3 py-2.5">
        <div className="flex items-center justify-between gap-2">
          <span className="label">Market regime</span>
          <RegimeBadge regime={s.regime} />
        </div>
        {isTrade ? (
          <>
            <div>
              <p className="label mb-1">Supporting factors</p>
              <BulletList items={s.supporting.slice(0, factorLimit)} tone="up" />
            </div>
            <div>
              <p className="label mb-1">Opposing factors</p>
              <BulletList items={s.opposing.slice(0, factorLimit)} tone="warn" empty="None identified." />
            </div>
            {s.invalidation_text ? (
              <div>
                <p className="label mb-1">Invalidation</p>
                <p className="text-xs text-fg">{s.invalidation_text}</p>
              </div>
            ) : null}
          </>
        ) : (
          <div>
            <p className="label mb-1 flex items-center gap-1">
              <ShieldX className="size-3" /> Why no trade
            </p>
            <BulletList items={s.no_trade_reasons.slice(0, factorLimit)} tone="down" empty="Score below threshold." />
          </div>
        )}
      </div>

      <footer className="mt-auto flex items-center gap-2 border-t border-line px-3 py-2 text-[0.68rem] text-muted">
        <Clock className="size-3 shrink-0" />
        {isTrade && s.status === "ACTIVE" && minsLeft !== null ? (
          <span>
            Expires after {s.expiry_bars} candles · <span className="num text-fg">{minsLeft > 0 ? fmtCountdown(minsLeft) : "now"}</span> or when invalidated
          </span>
        ) : (
          <span className="num">{fmtTime(s.created_at, true)} UTC</span>
        )}
        <div className="ml-auto flex items-center gap-1">
          {onPaper && isTrade && s.status === "ACTIVE" ? (
            <Button size="xs" variant="outline" onClick={() => onPaper(s)}>
              Paper trade
            </Button>
          ) : null}
          <Button asChild size="xs" variant="ghost">
            <Link href={`/signals/${s.id}`}>
              Details <ArrowRight />
            </Link>
          </Button>
        </div>
      </footer>
    </article>
  );
}
