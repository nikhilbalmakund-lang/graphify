import { describe, expect, it } from "vitest";

import { decimate, R_BUCKETS, rDistribution } from "@/lib/series";

describe("decimate", () => {
  it("returns short series unchanged", () => {
    const pts = [1, 2, 3];
    expect(decimate(pts, 10, (x) => x)).toBe(pts);
  });

  it("keeps global extremes (drawdown troughs are never smoothed away)", () => {
    const pts = Array.from({ length: 5000 }, (_, i) => ({ i, v: Math.sin(i / 50) * 100 + i / 100 }));
    pts[3210].v = -9999; // deep trough
    pts[777].v = 9999; // spike
    const out = decimate(pts, 400, (p) => p.v);
    expect(out.length).toBeLessThanOrEqual(402);
    expect(out.some((p) => p.v === -9999)).toBe(true);
    expect(out.some((p) => p.v === 9999)).toBe(true);
    expect(out[out.length - 1]).toBe(pts[pts.length - 1]);
    for (let k = 1; k < out.length; k++) expect(out[k].i).toBeGreaterThan(out[k - 1].i);
  });
});

describe("rDistribution", () => {
  it("orders buckets from losses to wins and tones them", () => {
    const dist = Object.fromEntries([...R_BUCKETS].reverse().map((k, i) => [k, i]));
    const out = rDistribution(dist);
    expect(out.map((b) => b.label)).toEqual(R_BUCKETS);
    expect(out[0].tone).toBe("down");
    expect(out[out.length - 1].tone).toBe("up");
    expect(rDistribution(undefined)).toEqual([]);
  });
});
