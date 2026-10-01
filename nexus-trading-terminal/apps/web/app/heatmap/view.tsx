"use client";

import { LayoutGrid } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageContainer, PageHeader } from "@/components/common/page-header";
import { DataBlock } from "@/components/common/states";
import { ModeBadge, RegimeBadge } from "@/components/market/badges";
import { Segmented } from "@/components/market/pickers";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Tip } from "@/components/ui/tooltip";
import { useApi } from "@/hooks/use-api";
import { useLive } from "@/hooks/use-live";
import { qs } from "@/lib/api";
import { fmtNum, fmtPct, fmtPrice, titleCase } from "@/lib/format";

interface HeatRow {
  symbol: string;
  name: string;
  asset_class: string;
  price: number;
  change_pct_24h: number | null;
  volume_ratio: number | null;
  volume_available: boolean;
  atr_pct: number | null;
  vol_percentile: number | null;
  trend: string;
  trend_score: number | null;
  regime: string;
  signal_score: number | null;
  is_demo: boolean;
  status: string;
}

type Metric = "change" | "trend" | "volatility" | "score" | "volume";

const METRICS: Record<Metric, { label: string; get: (r: HeatRow) => number | null; fmt: (v: number | null) => string; diverging: boolean; scale: number }> = {
  change: { label: "24H change", get: (r) => r.change_pct_24h, fmt: (v) => fmtPct(v, 2), diverging: true, scale: 3 },
  trend: { label: "Trend score", get: (r) => r.trend_score, fmt: (v) => fmtNum(v, 0), diverging: true, scale: 100 },
  volatility: { label: "Volatility pct", get: (r) => r.vol_percentile, fmt: (v) => fmtNum(v, 0), diverging: false, scale: 100 },
  score: { label: "Signal score", get: (r) => r.signal_score, fmt: (v) => (v === null ? "—" : `${v.toFixed(0)}/100`), diverging: false, scale: 100 },
  volume: { label: "Volume vs avg", get: (r) => (r.volume_available ? r.volume_ratio : null), fmt: (v) => (v === null ? "n/a" : `${v.toFixed(2)}×`), diverging: false, scale: 2 },
};

function color(v: number | null, m: (typeof METRICS)[Metric]): string {
  if (v === null || Number.isNaN(v)) return "rgba(83,96,115,0.18)";
  if (m.diverging) {
    const a = Math.min(1, Math.abs(v) / m.scale);
    return v >= 0 ? `rgba(38,194,129,${0.12 + a * 0.62})` : `rgba(240,82,92,${0.12 + a * 0.62})`;
  }
  const a = Math.min(1, Math.max(0, v / m.scale));
  return `rgba(34,211,238,${0.08 + a * 0.6})`;
}

export function HeatmapView() {
  const [cls, setCls] = useState<"" | "FOREX" | "CRYPTO" | "INDICES" | "COMMODITIES">("");
  const [metric, setMetric] = useState<Metric>("change");
  const { data, error, isLoading, mutate } = useApi<{ is_demo: boolean; rows: HeatRow[] }>(`/api/heatmap${qs({ asset_class: cls })}`, 30_000);
  const { quotes } = useLive();
  const m = METRICS[metric];
  const rows = (data?.rows ?? []).map((r) => (quotes[r.symbol] && metric === "change" ? { ...r, change_pct_24h: quotes[r.symbol].change_pct_24h, price: quotes[r.symbol].price } : r));
  const byClass = new Map<string, HeatRow[]>();
  for (const r of rows) byClass.set(r.asset_class, [...(byClass.get(r.asset_class) ?? []), r]);

  return (
    <PageContainer>
      <PageHeader
        title="Heatmap"
        description="Price change, volume, volatility, trend and signal score across instruments. Colour intensity encodes the selected metric."
        badges={data ? <ModeBadge mode={data.is_demo ? "DEMO" : "LIVE"} /> : null}
        actions={
          <>
            <Segmented
              label="Asset class"
              value={cls}
              onChange={setCls}
              options={[
                { value: "", label: "All" },
                { value: "FOREX", label: "Forex" },
                { value: "CRYPTO", label: "Crypto" },
                { value: "INDICES", label: "Indices" },
                { value: "COMMODITIES", label: "Commodities" },
              ]}
            />
            <Segmented label="Metric" value={metric} onChange={setMetric} options={Object.entries(METRICS).map(([k, v]) => ({ value: k as Metric, label: v.label }))} />
          </>
        }
      />
      <DataBlock data={data} error={error} isLoading={isLoading} onRetry={() => mutate()} rows={6}>
        {() => (
          <div className="flex flex-col gap-3">
            {[...byClass.entries()].map(([klass, items]) => (
              <Panel key={klass}>
                <PanelHeader title={titleCase(klass)} icon={<LayoutGrid />} subtitle={`${items.length} instruments · ${m.label}`} />
                <PanelBody className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-5">
                  {items.map((r) => {
                    const v = m.get(r);
                    return (
                      <Tip
                        key={r.symbol}
                        content={
                          <div className="flex flex-col gap-0.5">
                            <span className="font-semibold">{r.name}</span>
                            <span>24H {fmtPct(r.change_pct_24h)} · trend {fmtNum(r.trend_score, 0)} ({titleCase(r.trend)})</span>
                            <span>ATR {fmtNum(r.atr_pct, 2)}% · vol pct {fmtNum(r.vol_percentile, 0)}</span>
                            <span>Volume {r.volume_available ? `${fmtNum(r.volume_ratio, 2)}× avg` : "not available"}</span>
                            <span>Signal score {r.signal_score === null ? "—" : `${r.signal_score.toFixed(0)}/100`}</span>
                          </div>
                        }
                      >
                        <Link
                          href={`/chart?symbol=${r.symbol}`}
                          className="flex min-h-24 flex-col justify-between rounded-sm border border-line/60 p-2.5 transition-transform hover:scale-[1.015] hover:border-line-strong"
                          style={{ background: color(v, m) }}
                        >
                          <div className="flex items-start justify-between gap-1">
                            <span className="text-sm font-bold text-fg-strong">{r.symbol}</span>
                            {r.is_demo ? <span className="text-[0.55rem] font-bold text-demo">DEMO</span> : null}
                          </div>
                          <span className="num text-lg font-semibold text-fg-strong">{m.fmt(v)}</span>
                          <div className="flex items-center justify-between gap-1">
                            <span className="num text-[0.66rem] text-fg/80">{fmtPrice(r.price, r.symbol)}</span>
                            <RegimeBadge regime={r.regime} className="bg-bg/40" />
                          </div>
                        </Link>
                      </Tip>
                    );
                  })}
                </PanelBody>
              </Panel>
            ))}
          </div>
        )}
      </DataBlock>
    </PageContainer>
  );
}
