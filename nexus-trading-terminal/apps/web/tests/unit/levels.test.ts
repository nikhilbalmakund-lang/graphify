import { describe, expect, it } from "vitest";

import { entryMarker, signalLevels, structureLevels } from "@/components/charts/levels";

const base = {
  direction: "LONG" as const,
  entry_price: 100,
  entry_zone_low: null,
  entry_zone_high: null,
  stop: 95,
  targets: [
    { label: "TP1", price: 107.5, rr: 1.5, basis: "R-MULTIPLE", allocation: 0.5 },
    { label: "TP2", price: 112.5, rr: 2.5, basis: "STRUCTURE", allocation: 0.5 },
  ],
};

describe("chart levels", () => {
  it("draws nothing for NO_TRADE signals", () => {
    expect(signalLevels({ ...base, direction: "NO_TRADE" })).toEqual([]);
    expect(entryMarker({ direction: "NO_TRADE", bar_time: "2026-10-01T00:00:00Z" })).toEqual([]);
  });

  it("plots entry, stop and every target and keeps them in view", () => {
    const lv = signalLevels(base);
    expect(lv.map((l) => l.label)).toEqual(["Entry", "Stop", "TP1", "TP2"]);
    expect(lv.every((l) => l.fit)).toBe(true);
  });

  it("plots both bounds of an entry zone", () => {
    const lv = signalLevels({ ...base, entry_price: null, entry_zone_low: 99, entry_zone_high: 101 });
    expect(lv.filter((l) => l.price === 99 || l.price === 101)).toHaveLength(2);
  });

  it("marks long entries below the bar with an up arrow", () => {
    const [m] = entryMarker({ direction: "LONG", bar_time: "2026-10-01T00:15:00Z" });
    expect(m.shape).toBe("arrowUp");
    expect(m.position).toBe("belowBar");
    expect(m.time).toBe(Date.parse("2026-10-01T00:15:00Z") / 1000);
  });

  it("labels heuristic liquidity levels", () => {
    const st = {
      trend: "BULLISH",
      last_swing_high: null,
      last_swing_low: null,
      recent_labels: [],
      last_event: null,
      supports: [{ price: 90, kind: "SUPPORT", touches: 3, last_touch: "", strength: 1, distance_atr: 1 }],
      resistances: [],
      range: { is_range: false, high: null, low: null, height_atr: null },
      breakout: null,
      sweep: null,
      liquidity_zones: [{ kind: "EQUAL_LOWS", price: 89, touches: 2, heuristic: true, note: "" }],
      swings: [],
      heuristic_note: "",
    } as const;
    const lv = structureLevels(st as never, { liquidity: true });
    expect(lv.find((l) => l.price === 89)?.label).toBe("Liq*");
    expect(lv.find((l) => l.price === 90)?.label).toBe("S ×3");
  });
});
