"use client";

import type { Signal } from "@nexus/shared-types";
import { LayoutGrid, List, Zap } from "lucide-react";
import { useState } from "react";

import { RiskNotice } from "@/components/common/disclaimer";
import { ExportButton } from "@/components/common/export-button";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { DataBlock, EmptyState } from "@/components/common/states";
import { Segmented, SymbolSelect } from "@/components/market/pickers";
import { GenerateSignalDialog } from "@/components/signals/generate-dialog";
import { SignalCard } from "@/components/signals/signal-card";
import { SignalTable } from "@/components/signals/signal-table";
import { usePaperTrade } from "@/components/signals/use-paper-trade";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/input";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { useApi } from "@/hooks/use-api";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { qs } from "@/lib/api";
import { titleCase } from "@/lib/format";

const STATUSES = ["", "ACTIVE", "TRIGGERED", "TP1_HIT", "TP2_HIT", "TP3_HIT", "STOPPED", "INVALIDATED", "EXPIRED", "NO_TRADE"];

export function SignalsView() {
  const [status, setStatus] = useState("");
  const [symbol, setSymbol] = useState("");
  const [direction, setDirection] = useState<"" | "LONG" | "SHORT" | "NO_TRADE">("");
  const [view, setView] = useLocalStorage<"cards" | "table">("nexus.signals.view", "cards");
  const stats = useApi<Record<string, number>>("/api/signals/stats", 30_000);
  const list = useApi<Signal[]>(`/api/signals${qs({ status, symbol, direction, limit: 200 })}`, 20_000);
  const { execute } = usePaperTrade();

  return (
    <PageContainer>
      <PageHeader
        title="AI Signals"
        description="Deterministic signals scored 0–100 (SIGNAL SCORE - not a probability), filtered, optionally reviewed by independent AI analysts and a critic, then vetted by the risk engine."
        actions={
          <>
            <ExportButton path="/api/signals/export.csv" filename="nexus-signals.csv" size="sm" variant="outline" />
            <GenerateSignalDialog />
          </>
        }
      />
      <div className="flex flex-wrap items-center gap-1.5">
        {Object.entries(stats.data ?? {})
          .sort((a, b) => b[1] - a[1])
          .map(([k, v]) => (
            <button key={k} type="button" onClick={() => setStatus(status === k ? "" : k)} className="cursor-pointer" aria-pressed={status === k}>
              <Badge tone={status === k ? "accent" : "neutral"} className="py-0.5">
                {titleCase(k)} <span className="num ml-1 text-fg">{v}</span>
              </Badge>
            </button>
          ))}
      </div>
      <Panel>
        <PanelHeader
          title="Signal feed"
          icon={<Zap />}
          subtitle={list.data ? `${list.data.length} signals` : undefined}
          actions={
            <div className="flex flex-wrap items-center gap-1.5">
              <Select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)} className="h-7 w-32 text-xs">
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s ? titleCase(s) : "All statuses"}
                  </option>
                ))}
              </Select>
              <SymbolSelect value={symbol} onChange={setSymbol} allowAll className="h-7 text-xs" />
              <Segmented
                label="Direction"
                value={direction}
                onChange={setDirection}
                options={[
                  { value: "", label: "All" },
                  { value: "LONG", label: "Long" },
                  { value: "SHORT", label: "Short" },
                  { value: "NO_TRADE", label: "No trade" },
                ]}
              />
              <Segmented
                label="View"
                value={view}
                onChange={setView}
                options={[
                  { value: "cards", label: "Cards" },
                  { value: "table", label: "Table" },
                ]}
              />
            </div>
          }
        />
        <DataBlock
          data={list.data}
          error={list.error}
          isLoading={list.isLoading}
          onRetry={() => list.mutate()}
          rows={8}
          isEmpty={(d) => !d.length}
          empty={<EmptyState icon={view === "cards" ? <LayoutGrid /> : <List />} title="No signals match these filters" description="Signals are generated automatically on each new bar, or on demand with Analyze now." />}
        >
          {(d) =>
            view === "table" ? (
              <SignalTable signals={d} />
            ) : (
              <div className="grid gap-3 p-3 md:grid-cols-2 2xl:grid-cols-3">
                {d.map((s) => (
                  <SignalCard key={s.id} signal={s} onPaper={execute} />
                ))}
              </div>
            )
          }
        </DataBlock>
      </Panel>
      <RiskNotice />
    </PageContainer>
  );
}
