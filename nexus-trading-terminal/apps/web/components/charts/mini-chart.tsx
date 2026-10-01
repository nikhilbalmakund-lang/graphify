"use client";

import type { Candles, Timeframe } from "@nexus/shared-types";

import { ErrorState, LoadingRows } from "@/components/common/states";
import { useApi } from "@/hooks/use-api";
import { qs } from "@/lib/api";

import { type ChartLevel, type ChartMarker, PriceChart } from "./price-chart";

/** Compact candle chart with plan levels (used on signal detail and scanner). */
export function MiniChart({ symbol, timeframe, levels, markers, height = 320, limit = 240 }: { symbol: string; timeframe: Timeframe; levels?: ChartLevel[]; markers?: ChartMarker[]; height?: number; limit?: number }) {
  const { data, error, mutate } = useApi<Candles>(`/api/market/candles${qs({ symbol, timeframe, limit })}`, 60_000);
  if (error && !data) return <ErrorState error={error} onRetry={() => mutate()} />;
  if (!data) return <LoadingRows rows={6} />;
  return (
    <div style={{ height }} className="w-full">
      <PriceChart bars={data.bars} precision={data.price_precision} levels={levels} markers={markers} fitKey={`${symbol}-${timeframe}`} className="h-full w-full" ariaLabel={`${symbol} ${timeframe} chart with trade plan levels`} key={`${symbol}-${timeframe}`} />
    </div>
  );
}
