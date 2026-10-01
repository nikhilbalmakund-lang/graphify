/**
 * Reduce a long time series for plotting while keeping every bucket's extreme
 * values, so drawdown troughs and equity peaks are never smoothed away.
 */
export function decimate<T>(points: T[], maxPoints: number, value: (p: T) => number): T[] {
  if (points.length <= maxPoints) return points;
  const buckets = Math.max(1, Math.floor(maxPoints / 2));
  const size = points.length / buckets;
  const out: T[] = [];
  for (let b = 0; b < buckets; b++) {
    const start = Math.floor(b * size);
    const end = Math.min(points.length, Math.floor((b + 1) * size));
    if (start >= end) continue;
    let lo = start;
    let hi = start;
    for (let i = start + 1; i < end; i++) {
      if (value(points[i]) < value(points[lo])) lo = i;
      if (value(points[i]) > value(points[hi])) hi = i;
    }
    if (lo === hi) out.push(points[lo]);
    else if (lo < hi) out.push(points[lo], points[hi]);
    else out.push(points[hi], points[lo]);
  }
  const last = points[points.length - 1];
  if (out[out.length - 1] !== last) out.push(last);
  return out;
}

/** Ordered R-multiple distribution buckets as produced by the backend. */
export const R_BUCKETS = ["<-2R", "-2..-1.5R", "-1.5..-1R", "-1..-0.5R", "-0.5..0R", "0..0.5R", "0.5..1R", "1..1.5R", "1.5..2R", "2..3R", ">3R"];

export function rDistribution(dist: Record<string, number> | undefined): { label: string; count: number; tone: "up" | "down" }[] {
  if (!dist) return [];
  const keys = R_BUCKETS.filter((k) => k in dist);
  const extra = Object.keys(dist).filter((k) => !R_BUCKETS.includes(k));
  return [...keys, ...extra].map((k) => ({ label: k, count: dist[k], tone: k.startsWith("-") || k.startsWith("<") ? "down" : "up" }));
}
