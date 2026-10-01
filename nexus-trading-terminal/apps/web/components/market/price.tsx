"use client";

import { useEffect, useRef, useState } from "react";

import { fmtPct, fmtPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Price that briefly flashes green/red when it ticks. */
export function FlashPrice({ value, symbol, digits, className }: { value: number | null | undefined; symbol?: string; digits?: number; className?: string }) {
  const prev = useRef<number | null | undefined>(value);
  const [flash, setFlash] = useState<{ dir: "up" | "down"; n: number } | null>(null);
  useEffect(() => {
    if (value !== null && value !== undefined && prev.current !== null && prev.current !== undefined && value !== prev.current) {
      const dir = value > prev.current ? "up" : "down";
      setFlash((f) => ({ dir, n: (f?.n ?? 0) + 1 }));
    }
    prev.current = value;
  }, [value]);
  return (
    <span
      key={flash?.n}
      className={cn("num rounded-xs px-0.5", flash?.dir === "up" && "animate-flash-up", flash?.dir === "down" && "animate-flash-down", className)}
    >
      {fmtPrice(value, digits ?? symbol)}
    </span>
  );
}

export function Change({ pct, className, digits = 2 }: { pct: number | null | undefined; className?: string; digits?: number }) {
  const tone = pct === null || pct === undefined ? "text-muted" : pct > 0 ? "text-up" : pct < 0 ? "text-down" : "text-muted";
  return <span className={cn("num", tone, className)}>{fmtPct(pct, digits)}</span>;
}

export function Signed({ value, children, className }: { value: number | null | undefined; children: React.ReactNode; className?: string }) {
  const tone = value === null || value === undefined ? "text-muted" : value > 0 ? "text-up" : value < 0 ? "text-down" : "text-fg";
  return <span className={cn("num", tone, className)}>{children}</span>;
}
