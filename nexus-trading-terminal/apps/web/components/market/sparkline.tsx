import { useId } from "react";

import { cn } from "@/lib/utils";

/** Lightweight SVG sparkline (no chart library needed for tiny trend lines). */
export function Sparkline({ data, width = 120, height = 32, className, tone }: { data: number[] | undefined; width?: number; height?: number; className?: string; tone?: "up" | "down" | "flat" }) {
  const id = useId();
  if (!data || data.length < 2) return <div style={{ width, height }} className={className} />;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const pts = data.map((v, i) => [(i / (data.length - 1)) * width, height - 2 - ((v - min) / span) * (height - 4)] as const);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const t = tone ?? (data[data.length - 1] >= data[0] ? "up" : "down");
  const color = t === "up" ? "var(--color-up)" : t === "down" ? "var(--color-down)" : "var(--color-muted)";
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={cn("overflow-visible", className)} aria-hidden preserveAspectRatio="none">
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.22} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={`${line} L${width},${height} L0,${height} Z`} fill={`url(#${id})`} />
      <path d={line} fill="none" stroke={color} strokeWidth={1.3} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
