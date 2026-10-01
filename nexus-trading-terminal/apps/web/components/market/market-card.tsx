"use client";

import type { OverviewCard } from "@nexus/shared-types";
import Link from "next/link";

import { Tip } from "@/components/ui/tooltip";
import { useLiveQuote } from "@/hooks/use-live";
import { fmtNum } from "@/lib/format";
import { cn } from "@/lib/utils";

import { RegimeBadge, TrendBadge } from "./badges";
import { Change, FlashPrice } from "./price";
import { Sparkline } from "./sparkline";

export function MarketCard({ card }: { card: OverviewCard }) {
  const q = useLiveQuote(card.symbol);
  const price = q?.price ?? card.price;
  const pct = q?.change_pct_24h ?? card.change_pct_24h;
  if (card.status !== "OK") {
    return (
      <div className="panel flex flex-col gap-1 p-3">
        <span className="text-sm font-semibold text-fg">{card.symbol}</span>
        <span className="text-xs text-down">Data unavailable</span>
        <span className="text-[0.68rem] text-muted">{card.error}</span>
      </div>
    );
  }
  const volHot = (card.vol_percentile ?? 0) >= 85;
  return (
    <Link
      href={`/chart?symbol=${card.symbol}`}
      className="panel group flex min-w-0 flex-col gap-1.5 p-3 transition-colors hover:border-accent/40"
      aria-label={`${card.symbol} ${card.name}: open chart`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[0.82rem] font-bold tracking-wide text-fg-strong">{card.symbol}</p>
          <p className="truncate text-[0.66rem] text-muted">{card.name}</p>
        </div>
        <div className="flex flex-col items-end gap-0.5">
          {card.is_demo ? <span className="text-[0.55rem] font-bold tracking-wider text-demo">DEMO</span> : null}
          {!(q?.market_open ?? card.market_open) ? <span className="text-[0.55rem] font-semibold tracking-wider text-faint">CLOSED</span> : null}
        </div>
      </div>
      <div className="flex items-end justify-between gap-2">
        <div className="flex min-w-0 flex-col">
          <FlashPrice value={price} digits={card.price_precision} className="text-base font-semibold text-fg-strong" />
          <Change pct={pct} className="text-xs" />
        </div>
        <Sparkline data={card.sparkline} width={84} height={30} />
      </div>
      <div className="flex items-center justify-between gap-2 border-t border-line/70 pt-1.5">
        <TrendBadge trend={card.trend} />
        <Tip content={`ATR ${fmtNum(card.atr_pct, 2)}% of price · volatility percentile ${fmtNum(card.vol_percentile, 0)} (1H)`}>
          <span className={cn("num cursor-help text-[0.68rem]", volHot ? "text-warn" : "text-muted")}>Vol {fmtNum(card.vol_percentile, 0)}p</span>
        </Tip>
      </div>
      <RegimeBadge regime={card.regime} className="self-start" />
    </Link>
  );
}
