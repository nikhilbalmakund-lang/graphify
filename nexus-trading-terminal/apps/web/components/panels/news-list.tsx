"use client";

import type { NewsItem } from "@nexus/shared-types";
import { ExternalLink } from "lucide-react";

import { ImpactBadge, SentimentBadge } from "@/components/market/badges";
import { Tip } from "@/components/ui/tooltip";
import { useNow } from "@/hooks/use-now";
import { timeAgo } from "@/lib/format";

/** Headline links only open a real source URL; demo items have none and are never given a fake one. */
export function Headline({ item, className }: { item: NewsItem; className?: string }) {
  if (item.url) {
    return (
      <a href={item.url} target="_blank" rel="noopener noreferrer nofollow" className={`group inline hover:text-accent ${className ?? ""}`}>
        {item.headline}
        <ExternalLink className="ml-1 inline size-3 opacity-50 group-hover:opacity-100" aria-label="(opens source in new tab)" />
      </a>
    );
  }
  return (
    <Tip content={item.is_demo ? "DEMO headline: synthetic, no source article exists" : "No source URL provided by the news provider"}>
      <span className={className}>{item.headline}</span>
    </Tip>
  );
}

export function NewsList({ items, limit = 6 }: { items: NewsItem[]; limit?: number }) {
  const now = useNow();
  return (
    <ul className="flex flex-col divide-y divide-line/60">
      {items.slice(0, limit).map((n) => (
        <li key={n.id} className="flex flex-col gap-1 py-2">
          <Headline item={n} className="text-xs font-medium leading-snug text-fg" />
          <div className="flex flex-wrap items-center gap-1.5 text-[0.66rem] text-muted">
            <span>{n.source}</span>
            <span>·</span>
            <span>{now ? timeAgo(n.published_at, now) : ""}</span>
            {n.symbols.slice(0, 3).map((s) => (
              <span key={s} className="rounded-xs bg-elevated px-1 text-fg">
                {s}
              </span>
            ))}
            <span className="ml-auto flex items-center gap-1">
              <SentimentBadge sentiment={n.sentiment} />
              {n.importance === "HIGH" ? <ImpactBadge impact="HIGH" /> : null}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}
