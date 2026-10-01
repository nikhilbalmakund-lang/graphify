"use client";

import type { NewsItem } from "@nexus/shared-types";
import { Newspaper, RefreshCw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Callout } from "@/components/common/disclaimer";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { DataBlock, EmptyState } from "@/components/common/states";
import { ImpactBadge, ModeBadge, SentimentBadge } from "@/components/market/badges";
import { Segmented, SymbolSelect } from "@/components/market/pickers";
import { Headline } from "@/components/panels/news-list";
import { Button } from "@/components/ui/button";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { Tip } from "@/components/ui/tooltip";
import { useApi } from "@/hooks/use-api";
import { useNow } from "@/hooks/use-now";
import { errorMessage, post, qs } from "@/lib/api";
import { fmtTime, timeAgo } from "@/lib/format";

export function NewsView() {
  const [symbol, setSymbol] = useState("");
  const [sentiment, setSentiment] = useState<"" | "BULLISH" | "BEARISH" | "NEUTRAL" | "UNCERTAIN">("");
  const [importance, setImportance] = useState<"" | "HIGH" | "MEDIUM" | "LOW">("");
  const [busy, setBusy] = useState(false);
  const { data, error, isLoading, mutate } = useApi<NewsItem[]>(`/api/news${qs({ symbol, limit: 150 })}`, 60_000);
  const now = useNow();
  const items = (data ?? []).filter((n) => (!sentiment || n.sentiment === sentiment) && (!importance || n.importance === importance));
  const isDemo = data?.some((n) => n.is_demo);
  const counts = (data ?? []).reduce<Record<string, number>>((acc, n) => ({ ...acc, [n.sentiment ?? "UNCLASSIFIED"]: (acc[n.sentiment ?? "UNCLASSIFIED"] ?? 0) + 1 }), {});

  const refresh = async () => {
    setBusy(true);
    try {
      await post("/api/news/refresh");
      await mutate();
      toast.success("News refreshed");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <PageContainer>
      <PageHeader
        title="News"
        description="Normalised headlines with source attribution, asset relevance, importance and sentiment (AI-classified when a provider is configured, otherwise labelled rule-based)."
        badges={data ? <ModeBadge mode={isDemo ? "DEMO" : "LIVE"} /> : null}
        actions={
          <Button size="sm" variant="outline" onClick={refresh} disabled={busy}>
            <RefreshCw className={busy ? "animate-spin" : ""} /> Refresh
          </Button>
        }
      />
      {isDemo ? <Callout tone="warn" title="DEMO MODE news">Demo headlines are synthetic descriptions of simulated price moves. They have no source article, so they are never linked to a URL.</Callout> : null}
      <div className="flex flex-wrap items-center gap-2">
        <SymbolSelect value={symbol} onChange={setSymbol} allowAll className="h-7 text-xs" />
        <Segmented
          label="Sentiment"
          value={sentiment}
          onChange={setSentiment}
          options={[
            { value: "", label: "All" },
            { value: "BULLISH", label: `Bullish ${counts.BULLISH ?? 0}` },
            { value: "BEARISH", label: `Bearish ${counts.BEARISH ?? 0}` },
            { value: "NEUTRAL", label: `Neutral ${counts.NEUTRAL ?? 0}` },
            { value: "UNCERTAIN", label: `Uncertain ${counts.UNCERTAIN ?? 0}` },
          ]}
        />
        <Segmented
          label="Importance"
          value={importance}
          onChange={setImportance}
          options={[
            { value: "", label: "Any importance" },
            { value: "HIGH", label: "High" },
            { value: "MEDIUM", label: "Medium" },
            { value: "LOW", label: "Low" },
          ]}
        />
      </div>
      <Panel>
        <PanelHeader title="Headlines" icon={<Newspaper />} subtitle={`${items.length} items`} />
        <DataBlock data={data} error={error} isLoading={isLoading} onRetry={() => mutate()} rows={10} isEmpty={() => !items.length} empty={<EmptyState title="No headlines match" />}>
          {() => (
            <Table>
              <THead>
                <tr>
                  <TH>Time (UTC)</TH>
                  <TH>Headline</TH>
                  <TH>Source</TH>
                  <TH>Assets</TH>
                  <TH>Sentiment</TH>
                  <TH>Importance</TH>
                </tr>
              </THead>
              <tbody>
                {items.map((n) => (
                  <TR key={n.id}>
                    <TD className="num align-top text-muted">
                      {fmtTime(n.published_at, true)}
                      <span className="block text-[0.62rem] text-faint">{now ? timeAgo(n.published_at, now) : ""}</span>
                    </TD>
                    <TD className="min-w-72 whitespace-normal align-top">
                      <Headline item={n} className="text-[0.8rem] font-medium leading-snug text-fg" />
                      {n.summary ? <p className="mt-0.5 line-clamp-2 text-[0.7rem] text-muted">{n.summary}</p> : null}
                    </TD>
                    <TD className="align-top text-xs text-muted">{n.source}</TD>
                    <TD className="align-top">
                      <div className="flex flex-wrap gap-1">
                        {n.symbols.map((s) => (
                          <span key={s} className="rounded-xs bg-elevated px-1 text-[0.66rem] text-fg">
                            {s}
                          </span>
                        ))}
                      </div>
                    </TD>
                    <TD className="align-top">
                      <Tip content={n.sentiment_rationale ? `${n.sentiment_rationale} (${n.sentiment_source ?? "unknown source"})` : n.sentiment_source ?? "Not classified"}>
                        <span className="inline-flex cursor-help flex-col items-start gap-0.5">
                          <SentimentBadge sentiment={n.sentiment} />
                          <span className="text-[0.6rem] text-faint">{n.sentiment_source ?? ""}</span>
                        </span>
                      </Tip>
                    </TD>
                    <TD className="align-top">
                      <ImpactBadge impact={n.importance} />
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          )}
        </DataBlock>
      </Panel>
    </PageContainer>
  );
}
