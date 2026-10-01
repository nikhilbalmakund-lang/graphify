import { describe, expect, it } from "vitest";

import { fmtCountdown, fmtMoney, fmtPct, fmtPrice, fmtR, fmtRR, timeAgo, titleCase, toneOf } from "@/lib/format";

describe("format", () => {
  it("formats prices with instrument precision", () => {
    expect(fmtPrice(1.0987654, "EURUSD")).toBe("1.09877");
    expect(fmtPrice(2147.8, "XAUUSD")).toBe("2,147.80");
    expect(fmtPrice(153.4, "USDJPY")).toBe("153.400");
    expect(fmtPrice(12.3456, 1)).toBe("12.3");
    expect(fmtPrice(null)).toBe("—");
    expect(fmtPrice(Number.NaN)).toBe("—");
  });

  it("signs percentages and money", () => {
    expect(fmtPct(1.234)).toBe("+1.23%");
    expect(fmtPct(-0.5, 1)).toBe("-0.5%");
    expect(fmtPct(0)).toBe("0.00%");
    expect(fmtMoney(-1234.5)).toBe("-$1,234.50");
    expect(fmtMoney(10, 0, true)).toBe("+$10");
    expect(fmtR(0.4)).toBe("+0.40R");
    expect(fmtR(-1)).toBe("-1.00R");
  });

  it("renders risk/reward as a ratio, never as a percentage", () => {
    expect(fmtRR(2.4)).toBe("1 : 2.40");
    expect(fmtRR(null)).toBe("—");
  });

  it("formats countdowns and relative times", () => {
    expect(fmtCountdown(80)).toBe("1h 20m");
    expect(fmtCountdown(5)).toBe("5m");
    expect(fmtCountdown(60 * 24 + 61)).toBe("1d 1h");
    expect(fmtCountdown(-30)).toBe("30m ago");
    const now = Date.parse("2026-10-01T12:00:00Z");
    expect(timeAgo("2026-10-01T11:58:00Z", now)).toBe("2m ago");
    expect(timeAgo("2026-10-01T15:00:00Z", now)).toBe("in 3h");
    expect(timeAgo(null, now)).toBe("—");
  });

  it("derives tone and title case", () => {
    expect(toneOf(1)).toBe("up");
    expect(toneOf(-1)).toBe("down");
    expect(toneOf(0)).toBe("flat");
    expect(toneOf(null)).toBe("flat");
    expect(titleCase("TRENDING_BULLISH")).toBe("Trending Bullish");
  });
});
