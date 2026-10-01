"use client";

import type { MTFAnalysis } from "@nexus/shared-types";

import { Tip } from "@/components/ui/tooltip";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { fmtNum, fmtPrice, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

import { RegimeBadge, TrendBadge } from "./badges";

export function AlignmentMeter({ value }: { value: number }) {
  const pct = ((value + 1) / 2) * 100;
  return (
    <Tip content="Weighted multi-timeframe alignment from −1 (all bearish) to +1 (all bullish). Higher timeframes carry more weight.">
      <div className="flex cursor-help items-center gap-2">
        <span className="text-[0.62rem] text-down">Bear</span>
        <div className="relative h-1.5 w-32 rounded-full bg-gradient-to-r from-down/60 via-line-strong to-up/60">
          <span className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-bg bg-fg-strong" style={{ left: `${pct}%` }} />
        </div>
        <span className="text-[0.62rem] text-up">Bull</span>
        <span className={cn("num text-xs font-semibold", value > 0.2 ? "text-up" : value < -0.2 ? "text-down" : "text-muted")}>{fmtNum(value, 2)}</span>
      </div>
    </Tip>
  );
}

export function MTFTable({ mtf, symbol }: { mtf: MTFAnalysis; symbol: string }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-3">
        <AlignmentMeter value={mtf.alignment} />
        <span className="text-xs text-muted">{mtf.summary}</span>
      </div>
      <Table>
        <THead>
          <tr>
            <TH>TF</TH>
            <TH>Trend</TH>
            <TH align="right">Trend score</TH>
            <TH align="right">Momentum</TH>
            <TH>Structure</TH>
            <TH>Regime</TH>
            <TH align="right">RSI</TH>
            <TH align="right">Vol pct</TH>
            <TH>VWAP</TH>
            <TH align="right">Support</TH>
            <TH align="right">Resistance</TH>
          </tr>
        </THead>
        <tbody>
          {mtf.views.map((v) => (
            <TR key={v.timeframe} className={!v.available ? "opacity-50" : undefined}>
              <TD className="num font-semibold text-fg">{v.timeframe}</TD>
              {v.available ? (
                <>
                  <TD>
                    <TrendBadge trend={v.trend} />
                  </TD>
                  <TD align="right" className={cn("num", (v.trend_score ?? 0) > 0 ? "text-up" : (v.trend_score ?? 0) < 0 ? "text-down" : "")}>
                    {fmtNum(v.trend_score, 0)}
                  </TD>
                  <TD align="right" className={cn("num", (v.momentum_score ?? 0) > 0 ? "text-up" : (v.momentum_score ?? 0) < 0 ? "text-down" : "")}>
                    {fmtNum(v.momentum_score, 0)}
                  </TD>
                  <TD className="text-xs">{titleCase(v.structure_trend)}</TD>
                  <TD>
                    <RegimeBadge regime={v.regime} />
                  </TD>
                  <TD align="right" className="num">
                    {fmtNum(v.rsi14, 0)}
                  </TD>
                  <TD align="right" className={cn("num", (v.vol_percentile ?? 0) >= 85 && "text-warn")}>
                    {fmtNum(v.vol_percentile, 0)}
                  </TD>
                  <TD className="text-xs">{titleCase(v.vwap_relation)}</TD>
                  <TD align="right" className="num text-up">
                    {fmtPrice(v.nearest_support, symbol)}
                  </TD>
                  <TD align="right" className="num text-down">
                    {fmtPrice(v.nearest_resistance, symbol)}
                  </TD>
                </>
              ) : (
                <TD colSpan={10} className="text-xs text-faint">
                  {v.note || "Not enough data"}
                </TD>
              )}
            </TR>
          ))}
        </tbody>
      </Table>
    </div>
  );
}
