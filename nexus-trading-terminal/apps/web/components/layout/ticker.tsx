"use client";

import Link from "next/link";

import { Change, FlashPrice } from "@/components/market/price";
import { useLive } from "@/hooks/use-live";
import { DEFAULT_SYMBOLS } from "@/lib/constants";

/** Persistent scrolling market ticker (pauses on hover / focus). */
export function Ticker() {
  const { quotes } = useLive();
  const items = DEFAULT_SYMBOLS.map((s) => quotes[s]).filter(Boolean);
  if (!items.length) {
    return <div className="h-7 border-b border-line bg-panel/60" aria-hidden />;
  }
  const row = (dup: boolean) =>
    items.map((q) => (
      <Link
        key={`${q.symbol}-${dup}`}
        href={`/chart?symbol=${q.symbol}`}
        tabIndex={dup ? -1 : 0}
        aria-hidden={dup || undefined}
        className="flex shrink-0 items-center gap-2 px-3 text-[0.72rem] hover:bg-elevated/60"
      >
        <span className="font-semibold text-fg">{q.symbol}</span>
        <FlashPrice value={q.price} symbol={q.symbol} className="text-fg-strong" />
        <Change pct={q.change_pct_24h} />
        {q.is_demo ? <span className="text-[0.6rem] font-semibold text-demo">DEMO</span> : null}
        {!q.market_open ? <span className="text-[0.6rem] text-faint">CLOSED</span> : null}
      </Link>
    ));
  return (
    <div className="group relative h-7 overflow-hidden border-b border-line bg-panel/60" aria-label="Market ticker" role="region">
      <div className="flex h-full w-max animate-ticker items-center group-hover:[animation-play-state:paused] group-focus-within:[animation-play-state:paused]">
        {row(false)}
        {row(true)}
      </div>
    </div>
  );
}
