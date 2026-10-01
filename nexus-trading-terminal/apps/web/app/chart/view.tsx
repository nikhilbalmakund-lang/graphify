"use client";

import type { Bar, Candles, FeatureSnapshot, Overlays, RegimeResult, Signal, Timeframe } from "@nexus/shared-types";
import { Camera, Crosshair, Expand, Minus, MousePointer2, Shrink, Spline, Trash2, ZoomIn } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { entryMarker, signalLevels, structureLevels, structureMarkers } from "@/components/charts/levels";
import { type Drawing, type DrawTool, LINE_OVERLAYS, PANE_INDICATORS, PriceChart, type PriceChartHandle } from "@/components/charts/price-chart";
import { KV } from "@/components/common/stat";
import { ErrorState, LoadingRows } from "@/components/common/states";
import { DataBadge, RegimeBadge, TrendBadge } from "@/components/market/badges";
import { SymbolSelect, TimeframeTabs } from "@/components/market/pickers";
import { Change, FlashPrice } from "@/components/market/price";
import { GenerateSignalDialog } from "@/components/signals/generate-dialog";
import { SignalCard } from "@/components/signals/signal-card";
import { usePaperTrade } from "@/components/signals/use-paper-trade";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Tip } from "@/components/ui/tooltip";
import { useApi } from "@/hooks/use-api";
import { useLiveQuote } from "@/hooks/use-live";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { qs } from "@/lib/api";
import { ANALYSIS_TIMEFRAMES, DEFAULT_SYMBOLS, TIMEFRAMES } from "@/lib/constants";
import { downloadBlob } from "@/lib/download";
import { fmtNum, fmtPrice, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

const TF_SECONDS: Record<string, number> = { "1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1H": 3600, "4H": 14400, "1D": 86400, "1W": 604800 };

interface Prefs {
  lines: string[];
  panes: string[];
  volume: boolean;
  avgVolume: boolean;
  sr: boolean;
  liquidity: boolean;
  range: boolean;
  events: boolean;
  swings: boolean;
  plan: boolean;
}

const DEFAULT_PREFS: Prefs = { lines: ["ema20", "ema50", "vwap"], panes: ["rsi"], volume: true, avgVolume: false, sr: true, liquidity: false, range: false, events: true, swings: false, plan: true };

function Chip({ on, onClick, children, hint }: { on: boolean; onClick: () => void; children: React.ReactNode; hint?: string }) {
  const btn = (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        "h-6 cursor-pointer whitespace-nowrap rounded-xs border px-1.5 text-[0.68rem] font-medium transition-colors",
        on ? "border-accent/50 bg-accent/10 text-accent" : "border-line bg-panel-2 text-muted hover:text-fg",
      )}
    >
      {children}
    </button>
  );
  return hint ? <Tip content={hint}>{btn}</Tip> : btn;
}

function ToolButton({ active, onClick, label, children }: { active?: boolean; onClick: () => void; label: string; children: React.ReactNode }) {
  return (
    <Tip content={label}>
      <Button variant={active ? "outline" : "ghost"} size="icon" aria-label={label} aria-pressed={active} onClick={onClick} className={cn(active && "border-accent/60 text-accent")}>
        {children}
      </Button>
    </Tip>
  );
}

export function ChartView() {
  const router = useRouter();
  const params = useSearchParams();
  const symParam = (params.get("symbol") ?? "XAUUSD").toUpperCase();
  const symbol = DEFAULT_SYMBOLS.includes(symParam) ? symParam : "XAUUSD";
  const tfParam = params.get("tf") ?? "15m";
  const tf = (TIMEFRAMES as string[]).includes(tfParam) ? (tfParam as Timeframe) : "15m";
  const signalId = params.get("signal");

  const [prefs, setPrefs] = useLocalStorage<Prefs>("nexus.chart.prefs", DEFAULT_PREFS);
  const [drawingsAll, setDrawingsAll] = useLocalStorage<Record<string, Drawing[]>>("nexus.chart.drawings", {});
  const [tool, setTool] = useState<DrawTool>("cursor");
  const [fullscreen, setFullscreen] = useState(false);
  const [showIndicators, setShowIndicators] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<PriceChartHandle>(null);
  const { execute } = usePaperTrade();

  const analysable = (ANALYSIS_TIMEFRAMES as string[]).includes(tf);
  const candles = useApi<Candles>(`/api/market/candles${qs({ symbol, timeframe: tf, limit: 800 })}`, 30_000);
  const overlays = useApi<Overlays>(analysable ? `/api/market/overlays${qs({ symbol, timeframe: tf })}` : null, 60_000);
  const features = useApi<FeatureSnapshot>(analysable ? `/api/market/features${qs({ symbol, timeframe: tf })}` : null, 60_000);
  const regime = useApi<RegimeResult>(analysable ? `/api/market/regime${qs({ symbol, timeframe: tf })}` : null, 60_000);
  const linked = useApi<Signal>(signalId ? `/api/signals/${signalId}` : null);
  const latest = useApi<Signal[]>(`/api/signals${qs({ symbol, limit: 20 })}`, 30_000);
  const quote = useLiveQuote(symbol);

  const signal = linked.data ?? latest.data?.find((s) => s.timeframe === tf && s.direction !== "NO_TRADE" && ["ACTIVE", "TRIGGERED", "TP1_HIT", "TP2_HIT"].includes(s.status)) ?? null;
  const drawings = useMemo(() => drawingsAll[symbol] ?? [], [drawingsAll, symbol]);

  const setParam = (next: { symbol?: string; tf?: string }) => {
    const sp = new URLSearchParams({ symbol: next.symbol ?? symbol, tf: next.tf ?? tf });
    router.replace(`/chart?${sp.toString()}`, { scroll: false });
  };

  useEffect(() => {
    const onFs = () => setFullscreen(document.fullscreenElement === wrapRef.current);
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setTool("cursor");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const bars = useMemo(() => candles.data?.bars ?? [], [candles.data]);
  const liveBar = useMemo<Bar | null>(() => {
    const last = bars[bars.length - 1];
    const step = TF_SECONDS[tf];
    if (!quote || !last || step >= 86400) return null;
    const ts = Math.floor(new Date(quote.timestamp).getTime() / 1000);
    const period = Math.floor(ts / step) * step;
    const p = quote.price;
    if (period === last[0]) return [last[0], last[1], Math.max(last[2], p), Math.min(last[3], p), p, last[5]];
    if (period === last[0] + step) return [period, last[4], Math.max(last[4], p), Math.min(last[4], p), p, 0];
    return null;
  }, [quote, bars, tf]);

  const st = overlays.data?.structure;
  const levels = useMemo(
    () => [...structureLevels(st, { sr: prefs.sr, liquidity: prefs.liquidity, range: prefs.range }), ...(prefs.plan && signal ? signalLevels(signal) : [])],
    [st, prefs.sr, prefs.liquidity, prefs.range, prefs.plan, signal],
  );
  const markers = useMemo(
    () => [...structureMarkers(overlays.data, { events: prefs.events, swings: prefs.swings }), ...(prefs.plan && signal && signal.timeframe === tf ? entryMarker(signal) : [])],
    [overlays.data, prefs.events, prefs.swings, prefs.plan, signal, tf],
  );

  const toggle = (key: keyof Prefs) => setPrefs((p) => ({ ...DEFAULT_PREFS, ...p, [key]: !p[key] }));
  const toggleList = (key: "lines" | "panes", v: string) =>
    setPrefs((p) => {
      const cur = p[key] ?? [];
      return { ...DEFAULT_PREFS, ...p, [key]: cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v] };
    });
  const addDrawing = (d: Drawing) => setDrawingsAll((all) => ({ ...all, [symbol]: [...(all[symbol] ?? []), d] }));
  const clearDrawings = () => setDrawingsAll((all) => ({ ...all, [symbol]: [] }));
  const goFullscreen = () => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void wrapRef.current?.requestFullscreen();
  };
  const screenshot = () => {
    const canvas = chartRef.current?.screenshot();
    canvas?.toBlob((b) => b && downloadBlob(b, `nexus-${symbol}-${tf}.png`));
  };

  const f = features.data;
  const spread = quote ? quote.ask - quote.bid : null;

  return (
    <div className="flex flex-col gap-3 p-3 sm:p-4">
      <div className="flex flex-wrap items-center gap-2">
        <SymbolSelect value={symbol} onChange={(v) => setParam({ symbol: v })} />
        <TimeframeTabs value={tf} onChange={(v) => setParam({ tf: v })} />
        <div className="flex items-baseline gap-2 pl-1">
          <FlashPrice value={quote?.price ?? bars[bars.length - 1]?.[4]} symbol={symbol} className="text-lg font-semibold text-fg-strong" />
          <Change pct={quote?.change_pct_24h} className="text-xs" />
          {candles.data ? <DataBadge isDemo={candles.data.is_demo} provider={candles.data.provider} /> : null}
        </div>
        <div className="ml-auto flex items-center gap-1">
          <GenerateSignalDialog defaultSymbol={symbol} defaultTf={analysable ? tf : "15m"} />
        </div>
      </div>

      <div className="grid gap-3 xl:grid-cols-[1fr_320px]">
        <div ref={wrapRef} className={cn("panel flex min-w-0 flex-col", fullscreen && "h-screen rounded-none border-0")}>
          <div className="flex flex-wrap items-center gap-1 border-b border-line px-2 py-1.5">
            <div className="flex items-center gap-0.5 border-r border-line pr-1.5">
              <ToolButton active={tool === "cursor"} onClick={() => setTool("cursor")} label="Cursor (Esc)">
                <MousePointer2 />
              </ToolButton>
              <ToolButton active={tool === "hline"} onClick={() => setTool("hline")} label="Horizontal line: click the chart">
                <Minus />
              </ToolButton>
              <ToolButton active={tool === "trend"} onClick={() => setTool("trend")} label="Trend line: click two points">
                <Spline />
              </ToolButton>
              <ToolButton onClick={clearDrawings} label={`Clear ${drawings.length} drawing(s) on ${symbol}`}>
                <Trash2 />
              </ToolButton>
            </div>
            <Button size="xs" variant="outline" className="sm:hidden" aria-expanded={showIndicators} onClick={() => setShowIndicators((v) => !v)}>
              Indicators
            </Button>
            <div className={cn("w-full flex-wrap items-center gap-1 sm:flex sm:w-auto", showIndicators ? "flex" : "hidden")}>
              {Object.entries(LINE_OVERLAYS).map(([k, d]) => (
                <Chip key={k} on={prefs.lines?.includes(k)} onClick={() => toggleList("lines", k)}>
                  {d.label}
                </Chip>
              ))}
              <span className="mx-1 h-4 w-px bg-line" />
              {Object.entries(PANE_INDICATORS).map(([k, d]) => (
                <Chip key={k} on={prefs.panes?.includes(k)} onClick={() => toggleList("panes", k)}>
                  {d.label}
                </Chip>
              ))}
              <span className="mx-1 h-4 w-px bg-line" />
              <Chip on={prefs.volume} onClick={() => toggle("volume")}>
                Volume
              </Chip>
              <Chip on={prefs.avgVolume} onClick={() => toggle("avgVolume")} hint="20-bar average volume">
                Avg vol
              </Chip>
              <span className="mx-1 h-4 w-px bg-line" />
              <Chip on={prefs.sr} onClick={() => toggle("sr")} hint="Support / resistance from swing clusters">
                S/R
              </Chip>
              <Chip on={prefs.events} onClick={() => toggle("events")} hint="Break of structure / change of character">
                BOS/CHoCH
              </Chip>
              <Chip on={prefs.swings} onClick={() => toggle("swings")} hint="Swing labels HH / HL / LH / LL">
                Swings
              </Chip>
              <Chip on={prefs.liquidity} onClick={() => toggle("liquidity")} hint="Heuristic: equal highs/lows and swing clusters where stops may rest (*)">
                Liquidity*
              </Chip>
              <Chip on={prefs.range} onClick={() => toggle("range")}>
                Range
              </Chip>
              <Chip on={prefs.plan} onClick={() => toggle("plan")} hint="Entry, stop and target levels of the current signal">
                Signal plan
              </Chip>
            </div>
            <div className="ml-auto flex items-center gap-0.5">
              <ToolButton onClick={() => chartRef.current?.fit()} label="Fit content">
                <ZoomIn />
              </ToolButton>
              <ToolButton onClick={screenshot} label="Save screenshot (PNG)">
                <Camera />
              </ToolButton>
              <ToolButton onClick={goFullscreen} label={fullscreen ? "Exit fullscreen" : "Fullscreen"}>
                {fullscreen ? <Shrink /> : <Expand />}
              </ToolButton>
            </div>
          </div>
          <div className={cn("relative", fullscreen ? "min-h-0 flex-1" : "h-[min(68vh,720px)] min-h-[380px]")}>
            {candles.error && !candles.data ? (
              <div className="p-4">
                <ErrorState error={candles.error} onRetry={() => candles.mutate()} />
              </div>
            ) : !candles.data ? (
              <LoadingRows rows={10} className="p-4" />
            ) : (
              <PriceChart
                ref={chartRef}
                className="absolute inset-0"
                bars={bars}
                precision={candles.data.price_precision}
                overlays={overlays.data ?? null}
                lines={prefs.lines ?? []}
                panes={prefs.panes ?? []}
                showVolume={prefs.volume && candles.data.volume_available}
                showAvgVolume={prefs.avgVolume}
                levels={levels}
                markers={markers}
                drawings={drawings}
                tool={tool}
                onAddDrawing={addDrawing}
                liveBar={liveBar}
                fitKey={`${symbol}-${tf}`}
                ariaLabel={`${symbol} ${tf} candlestick chart`}
              />
            )}
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line px-3 py-1.5 text-[0.66rem] text-faint">
            <span className="flex items-center gap-1">
              <Crosshair className="size-3" /> Scroll to zoom · drag to pan · times in UTC
            </span>
            {tool !== "cursor" ? <span className="text-accent">{tool === "hline" ? "Click to place a horizontal line" : "Click two points to draw a trend line"} · Esc to cancel</span> : null}
            {!candles.data?.volume_available ? <span>Volume not available from this provider for {symbol}</span> : null}
            {!analysable ? <span>Indicators and structure are computed for 1m–1D; 1W shows price only.</span> : null}
            {candles.data && !candles.data.last_bar_complete ? <span>Last bar is still forming</span> : null}
            <span className="ml-auto">* heuristic concept</span>
          </div>
        </div>

        <div className="flex min-w-0 flex-col gap-3">
          <Panel>
            <PanelHeader title="Quote" subtitle={quote ? (quote.market_open ? "Market open" : "Market closed") : undefined} />
            <PanelBody className="grid grid-cols-3 gap-2 text-xs">
              <div>
                <p className="label">Bid</p>
                <p className="num text-fg-strong">{fmtPrice(quote?.bid, symbol)}</p>
              </div>
              <div>
                <p className="label">Ask</p>
                <p className="num text-fg-strong">{fmtPrice(quote?.ask, symbol)}</p>
              </div>
              <div>
                <p className="label">Spread{quote?.spread_is_estimate ? "*" : ""}</p>
                <p className="num text-fg-strong">{spread !== null ? fmtPrice(spread, symbol) : "—"}</p>
              </div>
            </PanelBody>
          </Panel>
          {signal ? (
            <SignalCard signal={signal} compact onPaper={execute} />
          ) : (
            <Panel>
              <PanelHeader title="Signal" />
              <PanelBody className="text-xs text-muted">No open signal for {symbol} on {tf}. Run the pipeline to evaluate the latest closed bar.</PanelBody>
            </Panel>
          )}
          {analysable ? (
            <Panel>
              <PanelHeader title={`Analysis · ${tf}`} subtitle={f ? `features v${f.feature_version}` : undefined} />
              <PanelBody className="flex flex-col text-xs">
                {regime.data ? (
                  <div className="mb-2 flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <RegimeBadge regime={regime.data.regime} />
                      <span className="num text-faint">clarity {fmtNum(regime.data.clarity, 2)}</span>
                    </div>
                    <p className="text-[0.7rem] text-muted">{regime.data.explanation}</p>
                  </div>
                ) : null}
                {st ? (
                  <>
                    <KV k="Structure" v={<TrendBadge trend={st.trend} />} />
                    <KV k="Swings" v={st.recent_labels.join(" · ") || "—"} />
                    <KV k="Last event" v={st.last_event ? `${st.last_event.type} ${titleCase(st.last_event.direction)} (${st.last_event.bars_ago} bars)` : "—"} />
                  </>
                ) : null}
                {f ? (
                  <>
                    <KV k="Trend score" v={fmtNum(f.trend_score as number, 0)} />
                    <KV k="Momentum score" v={fmtNum(f.momentum_score as number, 0)} />
                    <KV k="RSI 14" v={fmtNum(f.rsi14 as number, 1)} />
                    <KV k="ADX" v={fmtNum(f.adx as number, 1)} />
                    <KV k="ATR 14 / ATR %" v={`${fmtPrice(f.atr14 as number, symbol)} / ${fmtNum(f.atr_pct as number, 2)}%`} />
                    <KV k="Volatility percentile" v={fmtNum(f.vol_percentile as number, 0)} />
                    <KV k="Dist. VWAP" v={`${fmtNum(f.dist_vwap_pct as number, 2)}%`} />
                    <KV k="Dist. EMA20 / EMA50 / EMA200" v={`${fmtNum(f.dist_ema20_pct as number, 2)} / ${fmtNum(f.dist_ema50_pct as number, 2)} / ${fmtNum(f.dist_ema200_pct as number, 2)}%`} />
                    <KV k="Volume ratio" v={f.volume_available ? `${fmtNum(f.volume_ratio as number, 2)}×` : "n/a"} />
                  </>
                ) : (
                  <LoadingRows rows={4} />
                )}
              </PanelBody>
            </Panel>
          ) : null}
        </div>
      </div>
    </div>
  );
}
