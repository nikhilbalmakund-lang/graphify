"use client";

import type { Asset, Timeframe } from "@nexus/shared-types";

import { Select } from "@/components/ui/input";
import { useApi } from "@/hooks/use-api";
import { DEFAULT_SYMBOLS, SYMBOL_NAMES, TIMEFRAMES } from "@/lib/constants";
import { cn } from "@/lib/utils";

export function SymbolSelect({ value, onChange, className, id, allowAll }: { value: string; onChange: (v: string) => void; className?: string; id?: string; allowAll?: boolean }) {
  const { data } = useApi<Asset[]>("/api/market/assets");
  const symbols = data?.map((a) => a.symbol) ?? DEFAULT_SYMBOLS;
  return (
    <Select id={id} aria-label="Asset" value={value} onChange={(e) => onChange(e.target.value)} className={cn("w-auto min-w-28", className)}>
      {allowAll ? <option value="">All assets</option> : null}
      {symbols.map((s) => (
        <option key={s} value={s}>
          {s} · {data?.find((a) => a.symbol === s)?.name ?? SYMBOL_NAMES[s] ?? s}
        </option>
      ))}
    </Select>
  );
}

/** Segmented timeframe control. */
export function TimeframeTabs({ value, onChange, options = TIMEFRAMES, className }: { value: string; onChange: (v: Timeframe) => void; options?: Timeframe[]; className?: string }) {
  return (
    <div role="radiogroup" aria-label="Timeframe" className={cn("inline-flex items-center rounded-sm border border-line bg-panel-2 p-0.5", className)}>
      {options.map((tf) => (
        <button
          key={tf}
          type="button"
          role="radio"
          aria-checked={value === tf}
          onClick={() => onChange(tf)}
          className={cn(
            "num h-6 min-w-8 cursor-pointer rounded-xs px-1.5 text-[0.72rem] font-medium text-muted transition-colors hover:text-fg",
            value === tf && "bg-elevated text-accent shadow-[inset_0_0_0_1px_var(--color-line-strong)]",
          )}
        >
          {tf}
        </button>
      ))}
    </div>
  );
}

export function Segmented<T extends string>({ value, onChange, options, className, label }: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; className?: string; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className={cn("inline-flex flex-wrap items-center rounded-sm border border-line bg-panel-2 p-0.5", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "h-6 cursor-pointer rounded-xs px-2 text-[0.72rem] font-medium text-muted transition-colors hover:text-fg",
            value === o.value && "bg-elevated text-accent shadow-[inset_0_0_0_1px_var(--color-line-strong)]",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
