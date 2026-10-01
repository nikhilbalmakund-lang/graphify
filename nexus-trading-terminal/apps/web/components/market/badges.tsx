import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Tip } from "@/components/ui/tooltip";
import { REGIME_LABEL } from "@/lib/constants";
import { titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

type Tone = NonNullable<BadgeProps["tone"]>;

/** Data provenance. Every number on screen is LIVE, DEMO, IMPORTED, BACKTEST, PAPER or IMAGE ANALYSIS. */
export function ModeBadge({ mode, className, title }: { mode: string; className?: string; title?: string }) {
  const m = mode.toUpperCase();
  const tone: Tone = m === "LIVE" ? "up" : m === "DEMO" ? "warn" : m === "PAPER" || m === "SIMULATED" ? "info" : m === "BACKTEST" ? "purple" : m === "IMAGE ANALYSIS" ? "purple" : "neutral";
  const hint =
    title ??
    (m === "DEMO"
      ? "DEMO MODE: deterministic simulated market data. Not real prices."
      : m === "LIVE"
        ? "Live data from a configured provider."
        : m === "PAPER" || m === "SIMULATED"
          ? "Paper trading: simulated orders, no real money."
          : m === "BACKTEST"
            ? "Historical simulation results."
            : m === "IMPORTED"
              ? "User-imported historical data."
              : m === "IMAGE ANALYSIS"
                ? "Derived from a screenshot - not exchange/broker data."
                : undefined);
  return (
    <Tip content={hint}>
      <Badge tone={tone} className={cn("cursor-default", className)} data-mode={m}>
        {m === "DEMO" ? "DEMO MODE" : m}
      </Badge>
    </Tip>
  );
}

export function DataBadge({ isDemo, provider, className }: { isDemo: boolean | undefined; provider?: string; className?: string }) {
  if (isDemo === undefined) return null;
  return <ModeBadge mode={isDemo ? "DEMO" : "LIVE"} className={className} title={provider ? `${isDemo ? "DEMO MODE - simulated data" : "Live data"} · provider: ${provider}` : undefined} />;
}

export function DirectionBadge({ direction, className, size = "sm" }: { direction: string | null | undefined; className?: string; size?: "sm" | "lg" }) {
  const d = (direction ?? "NO_TRADE").toUpperCase();
  const tone: Tone = d === "LONG" || d === "BUY" ? "solidUp" : d === "SHORT" || d === "SELL" ? "solidDown" : "neutral";
  return (
    <Badge tone={tone} className={cn(size === "lg" && "px-2 py-0.5 text-xs", className)}>
      {d === "NO_TRADE" ? "NO TRADE" : d}
    </Badge>
  );
}

export function TrendBadge({ trend, className }: { trend: string | null | undefined; className?: string }) {
  const t = (trend ?? "NEUTRAL").toUpperCase();
  const Icon = t === "BULLISH" ? ArrowUpRight : t === "BEARISH" ? ArrowDownRight : Minus;
  return (
    <span className={cn("inline-flex items-center gap-0.5 text-xs font-medium", t === "BULLISH" ? "text-up" : t === "BEARISH" ? "text-down" : "text-muted", className)}>
      <Icon className="size-3.5" />
      {titleCase(t)}
    </span>
  );
}

const REGIME_TONE: Record<string, Tone> = {
  TRENDING_BULLISH: "up",
  TRENDING_BEARISH: "down",
  RANGING: "info",
  BREAKOUT: "accent",
  HIGH_VOLATILITY: "warn",
  LOW_VOLATILITY: "neutral",
  MEAN_REVERSION: "purple",
  UNCERTAIN: "neutral",
};

export function RegimeBadge({ regime, className }: { regime: string | null | undefined; className?: string }) {
  if (!regime) return <span className="text-xs text-faint">—</span>;
  return (
    <Badge tone={REGIME_TONE[regime] ?? "neutral"} className={className}>
      {REGIME_LABEL[regime] ?? titleCase(regime)}
    </Badge>
  );
}

export function ImpactBadge({ impact, className }: { impact: string; className?: string }) {
  const tone: Tone = impact === "HIGH" ? "solidDown" : impact === "MEDIUM" ? "warn" : "neutral";
  return (
    <Badge tone={tone} className={className}>
      {impact}
    </Badge>
  );
}

export function SentimentBadge({ sentiment, className }: { sentiment: string | null | undefined; className?: string }) {
  if (!sentiment) return <Badge className={className}>Unclassified</Badge>;
  const tone: Tone = sentiment === "BULLISH" ? "up" : sentiment === "BEARISH" ? "down" : sentiment === "UNCERTAIN" ? "warn" : "neutral";
  return (
    <Badge tone={tone} className={className}>
      {sentiment}
    </Badge>
  );
}

const STATUS_TONE: Record<string, Tone> = {
  ACTIVE: "accent",
  TRIGGERED: "info",
  TP1_HIT: "up",
  TP2_HIT: "up",
  TP3_HIT: "up",
  WIN: "up",
  STOPPED: "down",
  LOSS: "down",
  INVALIDATED: "down",
  EXPIRED: "neutral",
  NO_TRADE: "neutral",
  BREAKEVEN: "neutral",
  CLOSED: "neutral",
  OPEN: "accent",
  PENDING: "warn",
  FILLED: "up",
  CANCELLED: "neutral",
  REJECTED: "down",
};

export function StatusBadge({ status, className }: { status: string | null | undefined; className?: string }) {
  const s = (status ?? "—").toUpperCase();
  return (
    <Badge tone={STATUS_TONE[s] ?? "neutral"} className={className}>
      {s.replace(/_/g, " ")}
    </Badge>
  );
}

const CONN_TONE: Record<string, Tone> = {
  CONNECTED: "up",
  OK: "up",
  READY: "up",
  DEMO: "warn",
  CONFIGURED_UNVERIFIED: "info",
  NOT_CONFIGURED: "neutral",
  DISCONNECTED: "down",
  ERROR: "down",
  SIMULATED: "info",
};

export function ConnBadge({ status, className }: { status: string; className?: string }) {
  return (
    <Badge tone={CONN_TONE[status] ?? "neutral"} className={className}>
      {status.replace(/_/g, " ")}
    </Badge>
  );
}

export function ConnDot({ status, className }: { status: string; className?: string }) {
  const color =
    status === "CONNECTED" || status === "OK" || status === "open"
      ? "bg-up"
      : status === "DEMO" || status === "connecting"
        ? "bg-warn"
        : status === "NOT_CONFIGURED" || status === "idle"
          ? "bg-faint"
          : status === "CONFIGURED_UNVERIFIED"
            ? "bg-info"
            : "bg-down";
  return <span aria-hidden className={cn("inline-block size-1.5 shrink-0 rounded-full", color, (status === "CONNECTED" || status === "open") && "animate-pulse-dot", className)} />;
}
