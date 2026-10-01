import { Tip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const SCORE_HINT = "SIGNAL SCORE: a rule-based 0-100 quality score from trend, structure, momentum, volume/VWAP, liquidity, volatility, macro and sentiment. It is NOT a probability of winning.";

export function scoreTone(score: number): string {
  return score >= 75 ? "var(--color-up)" : score >= 60 ? "var(--color-accent)" : score >= 45 ? "var(--color-warn)" : "var(--color-muted)";
}

/** Circular SIGNAL SCORE gauge, always rendered as "NN/100" (never as a % chance). */
export function ScoreGauge({ score, size = 64, className }: { score: number; size?: number; className?: string }) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  return (
    <Tip content={SCORE_HINT}>
      <div className={cn("relative shrink-0 cursor-help", className)} style={{ width: size, height: size }} role="img" aria-label={`Signal score ${score.toFixed(0)} out of 100`}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-line)" strokeWidth={4} />
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={scoreTone(score)} strokeWidth={4} strokeLinecap="round" strokeDasharray={`${c * pct} ${c}`} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
          <span className="num text-base font-bold text-fg-strong" style={{ fontSize: size * 0.28 }}>
            {score.toFixed(0)}
          </span>
          <span className="num text-[0.55rem] text-faint">/100</span>
        </div>
      </div>
    </Tip>
  );
}

export function ScoreText({ score, className }: { score: number; className?: string }) {
  return (
    <Tip content={SCORE_HINT}>
      <span className={cn("num cursor-help whitespace-nowrap", className)}>
        <span className="text-[0.62rem] font-semibold uppercase tracking-wider text-muted">Signal score </span>
        <span className="font-bold" style={{ color: scoreTone(score) }}>
          {score.toFixed(0)}
        </span>
        <span className="text-faint">/100</span>
      </span>
    </Tip>
  );
}

export function ScoreBar({ score, className }: { score: number; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="h-1 w-14 overflow-hidden rounded-full bg-elevated">
        <div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, score))}%`, background: scoreTone(score) }} />
      </div>
      <span className="num text-xs text-fg">{score.toFixed(0)}</span>
    </div>
  );
}
