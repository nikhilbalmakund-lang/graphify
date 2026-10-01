"use client";

import type { Bar, Overlays } from "@nexus/shared-types";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  CrosshairMode,
  HistogramSeries,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  LineSeries,
  LineStyle,
  type MouseEventParams,
  type SeriesMarker,
  type SeriesType,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

import { cn } from "@/lib/utils";

export interface ChartLevel {
  price: number;
  label: string;
  color: string;
  style?: "solid" | "dashed" | "dotted";
  width?: 1 | 2 | 3;
  /** Keep this level inside the visible price range (trade-plan levels). */
  fit?: boolean;
}

export interface ChartMarker {
  time: number;
  position: "aboveBar" | "belowBar" | "inBar";
  shape: "arrowUp" | "arrowDown" | "circle" | "square";
  color: string;
  text?: string;
}

export type Drawing =
  | { id: string; kind: "hline"; price: number }
  | { id: string; kind: "trend"; a: { time: number; price: number }; b: { time: number; price: number } };

export type DrawTool = "cursor" | "hline" | "trend";

export const LINE_OVERLAYS: Record<string, { label: string; keys: string[]; color: string }> = {
  ema20: { label: "EMA 20", keys: ["ema20"], color: "#22d3ee" },
  ema50: { label: "EMA 50", keys: ["ema50"], color: "#a78bfa" },
  ema200: { label: "EMA 200", keys: ["ema200"], color: "#f5a524" },
  sma20: { label: "SMA 20", keys: ["sma20"], color: "#60a5fa" },
  bb: { label: "Bollinger", keys: ["bb_upper", "bb_mid", "bb_lower"], color: "#64748b" },
  vwap: { label: "VWAP", keys: ["vwap"], color: "#e879f9" },
};

export const PANE_INDICATORS: Record<string, { label: string; lines: { key: string; color: string }[]; hist?: string; levels?: number[] }> = {
  rsi: { label: "RSI 14", lines: [{ key: "rsi14", color: "#a78bfa" }], levels: [70, 30] },
  macd: { label: "MACD", lines: [{ key: "macd", color: "#22d3ee" }, { key: "macd_signal", color: "#f5a524" }], hist: "macd_hist" },
  stoch: { label: "Stochastic", lines: [{ key: "stoch_k", color: "#22d3ee" }, { key: "stoch_d", color: "#f5a524" }], levels: [80, 20] },
  adx: { label: "ADX", lines: [{ key: "adx", color: "#f0525c" }], levels: [25] },
  cci: { label: "CCI 20", lines: [{ key: "cci20", color: "#60a5fa" }], levels: [100, -100] },
  atr: { label: "ATR 14", lines: [{ key: "atr14", color: "#f5a524" }] },
  obv: { label: "OBV", lines: [{ key: "obv", color: "#26c281" }] },
};

export interface PriceChartHandle {
  fit: () => void;
  screenshot: () => HTMLCanvasElement | null;
}

interface Props {
  bars: Bar[];
  precision: number;
  overlays?: Overlays | null;
  lines?: string[];
  panes?: string[];
  showVolume?: boolean;
  showAvgVolume?: boolean;
  levels?: ChartLevel[];
  markers?: ChartMarker[];
  drawings?: Drawing[];
  tool?: DrawTool;
  onAddDrawing?: (d: Drawing) => void;
  liveBar?: Bar | null;
  fitKey?: string;
  className?: string;
  ariaLabel?: string;
}

const css = (name: string, fallback: string) => {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
};

const lineStyle = (s?: ChartLevel["style"]) => (s === "dashed" ? LineStyle.Dashed : s === "dotted" ? LineStyle.Dotted : LineStyle.Solid);

const t = (sec: number) => sec as UTCTimestamp;

export const PriceChart = forwardRef<PriceChartHandle, Props>(function PriceChart(
  { bars, precision, overlays, lines = [], panes = [], showVolume = true, showAvgVolume = false, levels = [], markers = [], drawings = [], tool = "cursor", onAddDrawing, liveBar, fitKey, className, ariaLabel },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const legendRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const extraSeries = useRef<ISeriesApi<SeriesType>[]>([]);
  const drawingSeries = useRef<ISeriesApi<SeriesType>[]>([]);
  const priceLines = useRef<IPriceLine[]>([]);
  const pending = useRef<{ time: number; price: number } | null>(null);
  const toolRef = useRef(tool);
  const onAddRef = useRef(onAddDrawing);
  const barsRef = useRef(bars);
  const lastFitKey = useRef<string | undefined>(undefined);
  const legendFn = useRef<((p?: MouseEventParams<Time>) => void) | null>(null);
  const scaleLevels = useRef<number[]>([]);

  useEffect(() => {
    toolRef.current = tool;
    onAddRef.current = onAddDrawing;
    barsRef.current = bars;
    if (tool !== "trend") pending.current = null;
  });

  useImperativeHandle(ref, () => ({
    fit: () => chartRef.current?.timeScale().fitContent(),
    screenshot: () => chartRef.current?.takeScreenshot(true, false) ?? null,
  }));

  // Create the chart once.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const up = css("--color-up", "#26c281");
    const down = css("--color-down", "#f0525c");
    const lineC = css("--color-line", "#1b2533");
    const chart = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: css("--color-panel", "#0b1017") },
        textColor: css("--color-muted", "#8090a5"),
        fontFamily: css("--font-mono", "monospace"),
        fontSize: 11,
        attributionLogo: false,
        panes: { separatorColor: css("--color-line-strong", "#283446"), separatorHoverColor: "rgba(34,211,238,0.25)", enableResize: true },
      },
      grid: { vertLines: { color: lineC }, horzLines: { color: lineC } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: lineC },
      timeScale: { borderColor: lineC, timeVisible: true, secondsVisible: false, rightOffset: 6 },
      localization: { locale: "en-GB" },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: up,
      downColor: down,
      wickUpColor: up,
      wickDownColor: down,
      borderVisible: false,
      priceLineColor: css("--color-accent", "#22d3ee"),
      autoscaleInfoProvider: (original: () => { priceRange: { minValue: number; maxValue: number } | null } | null) => {
        const res = original();
        const extra = scaleLevels.current;
        if (!res?.priceRange || !extra.length) return res;
        return {
          ...res,
          priceRange: {
            minValue: Math.min(res.priceRange.minValue, ...extra),
            maxValue: Math.max(res.priceRange.maxValue, ...extra),
          },
        };
      },
    });
    const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "vol", lastValueVisible: false, priceLineVisible: false });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    chartRef.current = chart;
    candleRef.current = candles;
    volumeRef.current = volume;
    markersRef.current = createSeriesMarkers(candles, []);

    const onMove = (p?: MouseEventParams<Time>) => {
      const legend = legendRef.current;
      if (!legend) return;
      const d = p?.seriesData.get(candles) as { open: number; high: number; low: number; close: number } | undefined;
      const last = barsRef.current[barsRef.current.length - 1];
      const o = d?.open ?? last?.[1];
      const h = d?.high ?? last?.[2];
      const l = d?.low ?? last?.[3];
      const c = d?.close ?? last?.[4];
      if (o === undefined) {
        legend.textContent = "";
        return;
      }
      const prec = candles.options().priceFormat;
      const digits = "precision" in prec && typeof prec.precision === "number" ? prec.precision : 2;
      const chg = o ? ((c! - o) / o) * 100 : 0;
      legend.innerHTML = "";
      const parts: [string, string, string?][] = [
        ["O", o.toFixed(digits)],
        ["H", h!.toFixed(digits)],
        ["L", l!.toFixed(digits)],
        ["C", c!.toFixed(digits), chg >= 0 ? up : down],
        ["", `${chg >= 0 ? "+" : ""}${chg.toFixed(2)}%`, chg >= 0 ? up : down],
      ];
      for (const [k, v, color] of parts) {
        const span = document.createElement("span");
        span.style.marginRight = "8px";
        if (k) {
          const kk = document.createElement("span");
          kk.style.opacity = "0.6";
          kk.textContent = `${k} `;
          span.appendChild(kk);
        }
        const vv = document.createElement("span");
        vv.textContent = v;
        if (color) vv.style.color = color;
        span.appendChild(vv);
        legend.appendChild(span);
      }
    };
    const onClick = (p: MouseEventParams<Time>) => {
      const mode = toolRef.current;
      if (mode === "cursor" || !p.point) return;
      const price = candles.coordinateToPrice(p.point.y);
      if (price === null) return;
      const id = `d${Date.now().toString(36)}`;
      if (mode === "hline") {
        onAddRef.current?.({ id, kind: "hline", price });
        return;
      }
      const time = typeof p.time === "number" ? p.time : null;
      if (time === null) return;
      if (!pending.current) {
        pending.current = { time, price };
      } else {
        const a = pending.current;
        pending.current = null;
        if (a.time !== time) onAddRef.current?.({ id, kind: "trend", a, b: { time, price } });
      }
    };
    legendFn.current = onMove;
    chart.subscribeCrosshairMove(onMove);
    chart.subscribeClick(onClick);
    return () => {
      chart.unsubscribeCrosshairMove(onMove);
      chart.unsubscribeClick(onClick);
      chart.remove();
      chartRef.current = null;
      legendFn.current = null;
      candleRef.current = null;
      volumeRef.current = null;
      markersRef.current = null;
      extraSeries.current = [];
      drawingSeries.current = [];
      priceLines.current = [];
    };
  }, []);

  // Candles + volume.
  useEffect(() => {
    const candles = candleRef.current;
    const volume = volumeRef.current;
    if (!candles || !volume) return;
    candles.applyOptions({ priceFormat: { type: "price", precision, minMove: 1 / 10 ** precision } });
    candles.setData(bars.map((b) => ({ time: t(b[0]), open: b[1], high: b[2], low: b[3], close: b[4] })));
    const up = css("--color-up", "#26c281");
    const down = css("--color-down", "#f0525c");
    volume.setData(showVolume ? bars.map((b) => ({ time: t(b[0]), value: b[5], color: `${b[4] >= b[1] ? up : down}55` })) : []);
    legendFn.current?.();
    if (fitKey !== lastFitKey.current && bars.length) {
      lastFitKey.current = fitKey;
      chartRef.current?.timeScale().fitContent();
    }
  }, [bars, precision, showVolume, fitKey]);

  // Live tick on the forming bar.
  useEffect(() => {
    const candles = candleRef.current;
    const last = bars[bars.length - 1];
    if (!candles || !liveBar || !last || liveBar[0] < last[0]) return;
    try {
      candles.update({ time: t(liveBar[0]), open: liveBar[1], high: liveBar[2], low: liveBar[3], close: liveBar[4] });
    } catch {
      /* out-of-order tick; the next refresh resyncs */
    }
  }, [liveBar, bars]);

  // Indicator lines + panes.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    for (const s of extraSeries.current) chart.removeSeries(s);
    extraSeries.current = [];
    while (chart.panes().length > 1) chart.removePane(chart.panes().length - 1);
    if (!overlays) return;
    const first = bars[0]?.[0] ?? 0;
    const pts = (arr: [number, number][] | undefined) => (arr ?? []).filter(([ts]) => ts >= first).map(([ts, v]) => ({ time: t(ts), value: v }));
    for (const key of lines) {
      const def = LINE_OVERLAYS[key];
      if (!def) continue;
      def.keys.forEach((k, i) => {
        const s = chart.addSeries(LineSeries, {
          color: def.color,
          lineWidth: 1,
          lineStyle: key === "bb" && i !== 1 ? LineStyle.Solid : key === "bb" ? LineStyle.Dashed : LineStyle.Solid,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
          title: i === 0 ? def.label : "",
        });
        s.setData(pts(overlays.lines[k]));
        extraSeries.current.push(s);
      });
    }
    if (showAvgVolume && showVolume) {
      const s = chart.addSeries(LineSeries, { color: "#94a3b8", lineWidth: 1, priceScaleId: "vol", priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      s.setData(pts(overlays.panes.volume_sma20));
      extraSeries.current.push(s);
    }
    let paneIndex = 1;
    for (const key of panes) {
      const def = PANE_INDICATORS[key];
      if (!def) continue;
      if (def.hist) {
        const h = chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, paneIndex);
        h.setData(pts(overlays.panes[def.hist]).map((p) => ({ ...p, color: p.value >= 0 ? "#26c28188" : "#f0525c88" })));
        extraSeries.current.push(h);
      }
      def.lines.forEach((ln, i) => {
        const s = chart.addSeries(LineSeries, { color: ln.color, lineWidth: 1, priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false, title: i === 0 ? def.label : "" }, paneIndex);
        s.setData(pts(overlays.panes[ln.key]));
        if (i === 0) for (const lv of def.levels ?? []) s.createPriceLine({ price: lv, color: "#536073", lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: "" });
        extraSeries.current.push(s);
      });
      paneIndex += 1;
    }
    const all = chart.panes();
    all[0]?.setStretchFactor(all.length > 1 ? 3 : 1);
    for (let i = 1; i < all.length; i++) all[i].setStretchFactor(1);
  }, [overlays, lines, panes, bars, showAvgVolume, showVolume]);

  // Horizontal levels (structure, signal plan, user lines).
  useEffect(() => {
    const candles = candleRef.current;
    if (!candles) return;
    for (const pl of priceLines.current) candles.removePriceLine(pl);
    priceLines.current = [];
    scaleLevels.current = levels.filter((l) => l.fit).map((l) => l.price);
    chartRef.current?.priceScale("right").applyOptions({ autoScale: true });
    const all: ChartLevel[] = [...levels, ...drawings.filter((d) => d.kind === "hline").map((d) => ({ price: (d as { price: number }).price, label: "", color: "#94a3b8", style: "solid" as const }))];
    for (const lv of all) {
      priceLines.current.push(candles.createPriceLine({ price: lv.price, color: lv.color, lineWidth: lv.width ?? 1, lineStyle: lineStyle(lv.style), axisLabelVisible: true, title: lv.label }));
    }
  }, [levels, drawings]);

  // Trend-line drawings.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    for (const s of drawingSeries.current) chart.removeSeries(s);
    drawingSeries.current = [];
    for (const d of drawings) {
      if (d.kind !== "trend") continue;
      const pts = [d.a, d.b].sort((x, y) => x.time - y.time);
      const s = chart.addSeries(LineSeries, { color: "#e2e8f0", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, pointMarkersVisible: true });
      s.setData(pts.map((p) => ({ time: t(p.time), value: p.price })));
      drawingSeries.current.push(s);
    }
  }, [drawings]);

  // Markers (entry, BOS/CHoCH events, swings).
  useEffect(() => {
    const m = markersRef.current;
    if (!m) return;
    const first = bars[0]?.[0] ?? 0;
    const sorted: SeriesMarker<Time>[] = markers
      .filter((x) => x.time >= first)
      .sort((a, b) => a.time - b.time)
      .map((x) => ({ time: t(x.time), position: x.position, shape: x.shape, color: x.color, text: x.text }));
    m.setMarkers(sorted);
  }, [markers, bars]);

  return (
    <div className={cn("relative", tool !== "cursor" && "cursor-crosshair", className)}>
      <div ref={containerRef} className="absolute inset-0" role="img" aria-label={ariaLabel ?? "Price chart"} />
      <div ref={legendRef} className="num pointer-events-none absolute left-2 top-1.5 z-[2] text-[0.68rem] text-fg" aria-hidden />
    </div>
  );
});
