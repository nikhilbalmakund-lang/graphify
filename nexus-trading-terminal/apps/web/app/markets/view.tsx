"use client";

import type { Asset, MTFAnalysis, OverviewCard } from "@nexus/shared-types";
import { Activity, FileUp, Layers, Upload } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { Callout } from "@/components/common/disclaimer";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { KV } from "@/components/common/stat";
import { DataBlock, EmptyState } from "@/components/common/states";
import { ModeBadge, RegimeBadge, TrendBadge } from "@/components/market/badges";
import { MTFTable } from "@/components/market/mtf-table";
import { Segmented, SymbolSelect, TimeframeTabs } from "@/components/market/pickers";
import { Change, FlashPrice } from "@/components/market/price";
import { Sparkline } from "@/components/market/sparkline";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Table, TD, TH, THead, TR, useSort } from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { useLive } from "@/hooks/use-live";
import { ApiError, errorMessage, qs } from "@/lib/api";
import { ANALYSIS_TIMEFRAMES } from "@/lib/constants";
import { fmtDateTime, fmtNum, fmtPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Timeframe } from "@nexus/shared-types";

type ClassFilter = "ALL" | "FOREX" | "CRYPTO" | "INDICES" | "COMMODITIES";

interface ImportBatch {
  batch: string;
  symbol: string;
  timeframe: string;
  rows: number;
  start: string;
  end: string;
  data_source: string;
  filename?: string;
}

function ImportPanel() {
  const { data: batches, mutate } = useApi<ImportBatch[]>("/api/market/imports");
  const { mutate: globalMutate } = useSWRConfig();
  const fileRef = useRef<HTMLInputElement>(null);
  const [symbol, setSymbol] = useState("XAUUSD");
  const [tf, setTf] = useState("1H");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ImportBatch | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const upload = async () => {
    const f = fileRef.current?.files?.[0];
    if (!f) {
      toast.error("Choose a CSV file first");
      return;
    }
    setBusy(true);
    setErr(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("symbol", symbol);
      fd.append("timeframe", tf);
      const res = await fetch("/api/market/import", { method: "POST", body: fd });
      const body = (await res.json()) as ImportBatch & { error?: { message: string; code: string } };
      if (!res.ok) throw new ApiError(res.status, body.error?.code ?? "HTTP_ERROR", body.error?.message ?? "Import failed");
      setResult(body);
      toast.success(`Imported ${body.rows} bars for ${body.symbol} ${body.timeframe}`);
      void mutate();
      void globalMutate((k) => typeof k === "string" && k.startsWith("/api/market/imports"));
      if (fileRef.current) fileRef.current.value = "";
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel>
      <PanelHeader title="Import historical OHLCV" subtitle="CSV with columns: timestamp, open, high, low, close, volume" icon={<FileUp />} />
      <PanelBody className="flex flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto_auto] sm:items-end">
          <Field label="CSV file" htmlFor="csv-file">
            <Input id="csv-file" ref={fileRef} type="file" accept=".csv,text/csv" className="h-auto py-1 file:mr-2 file:rounded-xs file:border-0 file:bg-elevated file:px-2 file:py-0.5 file:text-xs file:text-fg" />
          </Field>
          <Field label="Asset" htmlFor="imp-sym">
            <SymbolSelect id="imp-sym" value={symbol} onChange={setSymbol} />
          </Field>
          <Field label="Timeframe" htmlFor="imp-tf">
            <Select id="imp-tf" value={tf} onChange={(e) => setTf(e.target.value)} className="w-24">
              {ANALYSIS_TIMEFRAMES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </Select>
          </Field>
          <Button variant="primary" size="md" onClick={upload} disabled={busy}>
            <Upload /> {busy ? "Validating…" : "Import"}
          </Button>
        </div>
        <p className="text-[0.7rem] text-faint">
          Every row is validated (timestamps, OHLC consistency, no negatives, no duplicates, no future bars). Invalid files are rejected - nothing is silently repaired. Imported data is labelled IMPORTED and can be used in Backtesting.
        </p>
        {err ? <Callout tone="down" title="Import rejected">{err}</Callout> : null}
        {result ? (
          <Callout tone="accent" title="Import accepted">
            {result.rows} bars · {fmtDateTime(result.start)} → {fmtDateTime(result.end)} · data source <code className="num">{result.data_source}</code>
          </Callout>
        ) : null}
        {batches?.length ? (
          <Table>
            <THead>
              <tr>
                <TH>Batch</TH>
                <TH>Asset</TH>
                <TH>TF</TH>
                <TH align="right">Bars</TH>
                <TH>From</TH>
                <TH>To</TH>
                <TH />
              </tr>
            </THead>
            <tbody>
              {batches.map((b) => (
                <TR key={b.batch}>
                  <TD className="num text-muted">{b.batch}</TD>
                  <TD className="font-semibold">{b.symbol}</TD>
                  <TD className="num">{b.timeframe}</TD>
                  <TD align="right" className="num">
                    {b.rows}
                  </TD>
                  <TD className="num text-muted">{fmtDateTime(b.start)}</TD>
                  <TD className="num text-muted">{fmtDateTime(b.end)}</TD>
                  <TD>
                    <Button asChild size="xs" variant="ghost">
                      <Link href={`/backtesting?source=${encodeURIComponent(b.data_source)}&symbol=${b.symbol}&timeframe=${b.timeframe}`}>Backtest</Link>
                    </Button>
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
        ) : (
          <p className="text-xs text-faint">No imported datasets yet.</p>
        )}
      </PanelBody>
    </Panel>
  );
}

export function MarketsView() {
  const [tf, setTf] = useState<Timeframe>("1H");
  const [cls, setCls] = useState<ClassFilter>("ALL");
  const [selected, setSelected] = useState("XAUUSD");
  const overview = useApi<{ mode: string; is_demo: boolean; provider: string; cards: OverviewCard[] }>(`/api/market/overview${qs({ timeframe: tf })}`, 30_000);
  const assets = useApi<Asset[]>("/api/market/assets", 60_000);
  const mtf = useApi<MTFAnalysis>(`/api/market/mtf${qs({ symbol: selected, timeframe: "15m" })}`, 60_000);
  const { quotes } = useLive();

  const rows = (overview.data?.cards ?? [])
    .filter((c) => cls === "ALL" || c.asset_class === cls)
    .map((c) => {
      const q = quotes[c.symbol];
      return { ...c, price: q?.price ?? c.price, change_pct_24h: q?.change_pct_24h ?? c.change_pct_24h, bid: q?.bid ?? c.bid, ask: q?.ask ?? c.ask, spread: q ? q.ask - q.bid : (c.ask ?? 0) - (c.bid ?? 0) };
    });
  const { sorted, sort, onSort } = useSort(rows, { key: "symbol", dir: "asc" });
  const spec = assets.data?.find((a) => a.symbol === selected);

  return (
    <PageContainer>
      <PageHeader
        title="Markets"
        description="Live board of tracked instruments with trend, momentum, volatility and regime. Select a row for multi-timeframe analysis and instrument specs."
        badges={overview.data ? <ModeBadge mode={overview.data.is_demo ? "DEMO" : "LIVE"} title={`Provider: ${overview.data.provider}`} /> : null}
        actions={
          <>
            <Segmented
              label="Asset class"
              value={cls}
              onChange={setCls}
              options={[
                { value: "ALL", label: "All" },
                { value: "FOREX", label: "Forex" },
                { value: "CRYPTO", label: "Crypto" },
                { value: "INDICES", label: "Indices" },
                { value: "COMMODITIES", label: "Commodities" },
              ]}
            />
            <TimeframeTabs value={tf} onChange={setTf} options={ANALYSIS_TIMEFRAMES} />
          </>
        }
      />
      <Panel>
        <PanelHeader title="Market board" icon={<Activity />} subtitle={`Analytics on ${tf} bars · prices stream live`} />
        <DataBlock data={overview.data} error={overview.error} isLoading={overview.isLoading} onRetry={() => overview.mutate()} rows={8}>
          {() => (
            <Table>
              <THead>
                <tr>
                  <TH sortKey="symbol" sort={sort} onSort={onSort}>
                    Asset
                  </TH>
                  <TH align="right">Bid</TH>
                  <TH align="right">Ask</TH>
                  <TH sortKey="price" sort={sort} onSort={onSort} align="right">
                    Price
                  </TH>
                  <TH sortKey="change_pct_24h" sort={sort} onSort={onSort} align="right">
                    24H
                  </TH>
                  <TH>Trend</TH>
                  <TH sortKey="trend_score" sort={sort} onSort={onSort} align="right">
                    Trend score
                  </TH>
                  <TH sortKey="momentum_score" sort={sort} onSort={onSort} align="right">
                    Momentum
                  </TH>
                  <TH sortKey="atr_pct" sort={sort} onSort={onSort} align="right">
                    ATR %
                  </TH>
                  <TH sortKey="vol_percentile" sort={sort} onSort={onSort} align="right">
                    Vol pct
                  </TH>
                  <TH>Regime</TH>
                  <TH>Session</TH>
                  <TH>{tf} trend</TH>
                </tr>
              </THead>
              <tbody>
                {sorted.map((c) => (
                  <TR key={c.symbol} onClick={() => setSelected(c.symbol)} className={cn("cursor-pointer", selected === c.symbol && "bg-elevated/60")} aria-selected={selected === c.symbol}>
                    <TD>
                      <div className="flex flex-col">
                        <Link href={`/chart?symbol=${c.symbol}`} className="font-semibold text-fg hover:text-accent" onClick={(e) => e.stopPropagation()}>
                          {c.symbol}
                        </Link>
                        <span className="text-[0.66rem] text-muted">{c.name}</span>
                      </div>
                    </TD>
                    <TD align="right" className="num text-muted">
                      {fmtPrice(c.bid, c.price_precision)}
                    </TD>
                    <TD align="right" className="num text-muted">
                      {fmtPrice(c.ask, c.price_precision)}
                    </TD>
                    <TD align="right">
                      <FlashPrice value={c.price} digits={c.price_precision} className="font-semibold text-fg-strong" />
                    </TD>
                    <TD align="right">
                      <Change pct={c.change_pct_24h} />
                    </TD>
                    <TD>
                      <TrendBadge trend={c.trend} />
                    </TD>
                    <TD align="right" className={cn("num", (c.trend_score ?? 0) > 0 ? "text-up" : "text-down")}>
                      {fmtNum(c.trend_score, 0)}
                    </TD>
                    <TD align="right" className={cn("num", (c.momentum_score ?? 0) > 0 ? "text-up" : "text-down")}>
                      {fmtNum(c.momentum_score, 0)}
                    </TD>
                    <TD align="right" className="num">
                      {fmtNum(c.atr_pct, 2)}
                    </TD>
                    <TD align="right" className={cn("num", (c.vol_percentile ?? 0) >= 85 && "text-warn")}>
                      {fmtNum(c.vol_percentile, 0)}
                    </TD>
                    <TD>
                      <RegimeBadge regime={c.regime} />
                    </TD>
                    <TD className={cn("text-xs", c.market_open ? "text-up" : "text-faint")}>{c.market_open ? "Open" : "Closed"}</TD>
                    <TD>
                      <Sparkline data={c.sparkline} width={90} height={24} />
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          )}
        </DataBlock>
        {rows.length === 0 && overview.data ? <EmptyState title="No instruments in this class" /> : null}
      </Panel>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel className="xl:col-span-2">
          <PanelHeader title={`Multi-timeframe analysis · ${selected}`} subtitle="Trend, momentum, structure, volatility, VWAP relationship and key levels per timeframe" icon={<Layers />} actions={<SymbolSelect value={selected} onChange={setSelected} className="h-7 text-xs" />} />
          <PanelBody>
            <DataBlock data={mtf.data} error={mtf.error} isLoading={mtf.isLoading} onRetry={() => mtf.mutate()} rows={7}>
              {(m) => <MTFTable mtf={m} symbol={selected} />}
            </DataBlock>
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title={`Instrument · ${selected}`} subtitle={spec?.name} />
          <PanelBody>
            {spec ? (
              <div className="flex flex-col">
                <KV k="Asset class" v={spec.asset_class} mono={false} />
                <KV k="Session" v={spec.session} mono={false} />
                <KV k="Status" v={spec.market_status} mono={false} />
                <KV k="Price precision" v={spec.price_precision} />
                <KV k="Pip size" v={spec.pip_size} />
                <KV k="Contract size" v={fmtNum(spec.contract_size, 0)} />
                <KV k="Min lot / step" v={`${spec.min_lot} / ${spec.lot_step}`} />
                <KV k="Max leverage" v={`${spec.max_leverage}×`} />
                <KV k="Typical spread" v={spec.typical_spread} />
                <KV k="Currencies" v={spec.currencies.join(", ")} />
                <Button asChild size="sm" variant="outline" className="mt-3">
                  <Link href={`/chart?symbol=${selected}`}>Open chart</Link>
                </Button>
              </div>
            ) : (
              <DataBlock data={assets.data} error={assets.error} isLoading={assets.isLoading}>
                {() => <p className="text-xs text-faint">Unknown instrument.</p>}
              </DataBlock>
            )}
          </PanelBody>
        </Panel>
      </div>
      <ImportPanel />
    </PageContainer>
  );
}
