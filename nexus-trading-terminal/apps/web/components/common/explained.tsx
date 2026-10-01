import { Brain, Calculator, CircleHelp, ListChecks } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

const SECTIONS = [
  { key: "facts", label: "Facts", icon: ListChecks, cls: "text-info" },
  { key: "calculations", label: "Calculations", icon: Calculator, cls: "text-accent" },
  { key: "interpretation", label: "AI interpretation", icon: Brain, cls: "text-accent-2" },
  { key: "uncertainty", label: "Uncertainty", icon: CircleHelp, cls: "text-warn" },
] as const;

export interface Explained {
  facts?: string[];
  calculations?: string[];
  interpretation?: string[];
  uncertainty?: string[];
}

/** FACTS / CALCULATIONS / AI INTERPRETATION / UNCERTAINTY - every AI answer is split this way. */
export function ExplainedSections({ value, className, interpretationLabel }: { value: Explained; className?: string; interpretationLabel?: string }) {
  return (
    <div className={cn("grid gap-3 md:grid-cols-2", className)}>
      {SECTIONS.map(({ key, label, icon: Icon, cls }) => {
        const items = value[key] ?? [];
        return (
          <div key={key} className="min-w-0 rounded-sm border border-line bg-panel-2/60 p-2.5">
            <p className={cn("mb-1.5 flex items-center gap-1.5 text-[0.66rem] font-semibold uppercase tracking-wider", cls)}>
              <Icon className="size-3" /> {key === "interpretation" && interpretationLabel ? interpretationLabel : label}
            </p>
            {items.length ? (
              <ul className="flex flex-col gap-1 text-xs leading-relaxed text-fg">
                {items.map((t, i) => (
                  <li key={i} className="flex gap-1.5">
                    <span className="mt-[0.45rem] size-1 shrink-0 rounded-full bg-line-strong" />
                    <span className="min-w-0">{t}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-faint">None stated.</p>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function BulletList({ items, empty = "None.", tone }: { items: string[] | undefined; empty?: string; tone?: "up" | "down" | "warn" }) {
  if (!items?.length) return <p className="text-xs text-faint">{empty}</p>;
  const mark = tone === "up" ? "✓" : tone === "down" ? "✕" : tone === "warn" ? "!" : "•";
  const cls = tone === "up" ? "text-up" : tone === "down" ? "text-down" : tone === "warn" ? "text-warn" : "text-faint";
  return (
    <ul className="flex flex-col gap-1 text-xs leading-relaxed">
      {items.map((t, i) => (
        <li key={i} className="flex gap-1.5">
          <span className={cn("w-3 shrink-0 text-center font-semibold", cls)} aria-hidden>
            {mark}
          </span>
          <span className="min-w-0 text-fg">{t}</span>
        </li>
      ))}
    </ul>
  );
}
