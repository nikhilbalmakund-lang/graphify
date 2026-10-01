import * as React from "react";

import { Tip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type Tone = "up" | "down" | "warn" | "accent" | "flat" | undefined;

const toneClass = (t: Tone) => (t === "up" ? "text-up" : t === "down" ? "text-down" : t === "warn" ? "text-warn" : t === "accent" ? "text-accent" : "text-fg-strong");

export function Stat({ label, value, sub, tone, hint, className, size = "md" }: { label: React.ReactNode; value: React.ReactNode; sub?: React.ReactNode; tone?: Tone; hint?: React.ReactNode; className?: string; size?: "sm" | "md" | "lg" }) {
  const body = (
    <div className={cn("flex min-w-0 flex-col gap-0.5", className)}>
      <span className="label truncate">{label}</span>
      <span className={cn("num truncate font-semibold", size === "lg" ? "text-xl" : size === "sm" ? "text-sm" : "text-base", toneClass(tone))}>{value}</span>
      {sub ? <span className="truncate text-[0.7rem] text-muted">{sub}</span> : null}
    </div>
  );
  return hint ? (
    <Tip content={hint}>
      <div tabIndex={0} className="min-w-0 cursor-help rounded-xs">
        {body}
      </div>
    </Tip>
  ) : (
    body
  );
}

export function StatGrid({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 lg:grid-cols-4", className)}>{children}</div>;
}

export function KV({ k, v, className, mono = true }: { k: React.ReactNode; v: React.ReactNode; className?: string; mono?: boolean }) {
  return (
    <div className={cn("flex items-baseline justify-between gap-3 py-1 text-xs", className)}>
      <span className="shrink-0 text-muted">{k}</span>
      <span className={cn("min-w-0 truncate text-right text-fg", mono && "num")}>{v}</span>
    </div>
  );
}
