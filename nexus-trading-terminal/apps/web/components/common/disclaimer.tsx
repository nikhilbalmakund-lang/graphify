import { Info, ShieldAlert } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

/** Persistent, short risk notice. Shown wherever signals or results are presented. */
export function RiskNotice({ className, children }: { className?: string; children?: React.ReactNode }) {
  return (
    <p className={cn("flex items-start gap-1.5 text-[0.7rem] leading-snug text-faint", className)}>
      <ShieldAlert className="mt-px size-3 shrink-0" />
      <span>
        {children ??
          "Research tool, not financial advice. Signal scores are rule-based quality scores, not probabilities of profit. Past or simulated performance does not guarantee future results."}
      </span>
    </p>
  );
}

export function Callout({ tone = "info", title, children, className }: { tone?: "info" | "warn" | "down" | "accent"; title?: React.ReactNode; children: React.ReactNode; className?: string }) {
  const tones = {
    info: "border-info/30 bg-info/5 text-info",
    warn: "border-warn/35 bg-warn/5 text-warn",
    down: "border-down/35 bg-down/5 text-down",
    accent: "border-accent/30 bg-accent/5 text-accent",
  }[tone];
  return (
    <div className={cn("flex gap-2 rounded-sm border px-3 py-2", tones, className)}>
      <Info className="mt-0.5 size-3.5 shrink-0" />
      <div className="min-w-0 text-xs leading-relaxed text-fg">
        {title ? <p className={cn("mb-0.5 font-semibold", tones.split(" ").at(-1))}>{title}</p> : null}
        {children}
      </div>
    </div>
  );
}
