import { cn } from "@/lib/utils";

export function Progress({ value, max = 100, tone = "accent", className, label }: { value: number | null | undefined; max?: number; tone?: "accent" | "up" | "down" | "warn"; className?: string; label?: string }) {
  const pct = value === null || value === undefined ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
  const color = { accent: "bg-accent", up: "bg-up", down: "bg-down", warn: "bg-warn" }[tone];
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuenow={value ?? undefined}
      aria-valuemin={0}
      aria-valuemax={max}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-elevated", className)}
    >
      <div className={cn("h-full rounded-full transition-[width]", color)} style={{ width: `${pct}%` }} />
    </div>
  );
}
