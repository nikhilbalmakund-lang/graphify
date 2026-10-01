"use client";

import { ImageUp, ScanSearch, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ProviderLabel } from "@/components/ai/briefing-panel";
import { Callout } from "@/components/common/disclaimer";
import { BulletList } from "@/components/common/explained";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { KV } from "@/components/common/stat";
import { DataBadge, ModeBadge, RegimeBadge, TrendBadge } from "@/components/market/badges";
import { SymbolSelect } from "@/components/market/pickers";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { ApiError, errorMessage } from "@/lib/api";
import { fmtNum, fmtPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

interface ImageAnalysis {
  asset_visible: string | null;
  timeframe_visible: string | null;
  trend: string;
  structure: string;
  levels: { price: number | null; description: string }[];
  indicators_visible: string[];
  possible_setup: string;
  readability: string;
  caveats: string[];
}

interface ScanResult {
  label: string;
  available: boolean;
  provider: string | null;
  model: string | null;
  analysis: ImageAnalysis | null;
  errors: string[];
  precedence_note: string;
  image: { width: number; height: number; bytes: number };
  market_data: { symbol: string; price: number; is_demo: boolean; provider: string; trend_1h: string; regime_1h: string; supports: number[]; resistances: number[] } | null;
  data_precedence: string;
}

const MAX_MB = 8;

export function ChartScannerView() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [symbol, setSymbol] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [drag, setDrag] = useState(false);

  const previewUrl = useRef<string | null>(null);
  useEffect(
    () => () => {
      if (previewUrl.current) URL.revokeObjectURL(previewUrl.current);
    },
    [],
  );

  const pick = (f: File | undefined | null) => {
    setErr(null);
    setResult(null);
    if (!f) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(f.type)) {
      setErr("Upload a PNG, JPEG or WEBP image.");
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setErr(`Image larger than ${MAX_MB} MB.`);
      return;
    }
    setFile(f);
    if (previewUrl.current) URL.revokeObjectURL(previewUrl.current);
    previewUrl.current = URL.createObjectURL(f);
    setPreview(previewUrl.current);
  };

  const analyze = async () => {
    if (!file) return;
    setBusy(true);
    setErr(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (symbol) fd.append("symbol", symbol);
      const res = await fetch("/api/ai/chart-scan", { method: "POST", body: fd });
      const body = (await res.json()) as ScanResult & { error?: { code: string; message: string } };
      if (!res.ok) throw new ApiError(res.status, body.error?.code ?? "HTTP_ERROR", body.error?.message ?? "Analysis failed");
      setResult(body);
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const a = result?.analysis;
  return (
    <PageContainer>
      <PageHeader
        title="AI Chart Scanner"
        description="Upload a TradingView, broker or other chart screenshot. A vision model reads what is visible. Results are labelled IMAGE ANALYSIS and never treated as exchange or broker data."
        badges={<ModeBadge mode="IMAGE ANALYSIS" />}
      />
      <div className="grid gap-3 xl:grid-cols-2">
        <Panel>
          <PanelHeader title="Screenshot" icon={<ImageUp />} subtitle="PNG, JPEG or WEBP · max 8 MB · metadata is stripped server-side" />
          <PanelBody className="flex flex-col gap-3">
            <div
              role="button"
              tabIndex={0}
              aria-label="Choose or drop a chart screenshot"
              onClick={() => inputRef.current?.click()}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDrag(true);
              }}
              onDragLeave={() => setDrag(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDrag(false);
                pick(e.dataTransfer.files?.[0]);
              }}
              className={cn(
                "grid min-h-56 cursor-pointer place-items-center overflow-hidden rounded-sm border border-dashed border-line-strong bg-panel-2/60 transition-colors hover:border-accent/60",
                drag && "border-accent bg-accent/5",
              )}
            >
              {preview ? (
                // eslint-disable-next-line @next/next/no-img-element -- local object URL preview
                <img src={preview} alt="Uploaded chart preview" className="max-h-96 w-full object-contain" />
              ) : (
                <div className="flex flex-col items-center gap-2 p-6 text-center text-xs text-muted">
                  <Upload className="size-6 text-faint" />
                  <span>Drop a chart screenshot here, or click to choose a file</span>
                </div>
              )}
            </div>
            <input ref={inputRef} type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={(e) => pick(e.target.files?.[0])} aria-label="Chart screenshot file" />
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Compare with market data (optional)" htmlFor="cs-symbol">
                <SymbolSelect id="cs-symbol" value={symbol} onChange={setSymbol} allowAll />
              </Field>
              <Button variant="primary" size="md" onClick={analyze} disabled={!file || busy}>
                <ScanSearch /> {busy ? "Analysing image…" : "Analyse screenshot"}
              </Button>
            </div>
            {err ? <Callout tone="down">{err}</Callout> : null}
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="Image analysis" icon={<ScanSearch />} actions={result?.available && result.provider ? <ProviderLabel isAi provider={result.provider} model={result.model ?? ""} /> : null} />
          <PanelBody className="flex flex-col gap-3">
            {!result ? <p className="text-xs text-muted">Results appear here. Image analysis needs Claude or Gemini configured in Settings; there is no rule-based fallback for reading images.</p> : null}
            {result ? (
              <>
                <Callout tone="warn" title={result.label}>
                  {result.precedence_note}
                </Callout>
                {!result.available ? (
                  <Callout tone="info" title="Image analysis unavailable">
                    {result.errors.join(" · ")}
                  </Callout>
                ) : null}
                {a ? (
                  <div className="flex flex-col gap-3 text-xs">
                    <div className="flex flex-wrap gap-1.5">
                      <Badge tone="purple">Asset seen: {a.asset_visible ?? "not visible"}</Badge>
                      <Badge tone="purple">Timeframe seen: {a.timeframe_visible ?? "not visible"}</Badge>
                      <Badge tone={a.readability === "HIGH" ? "up" : a.readability === "LOW" ? "down" : "warn"}>Readability {a.readability}</Badge>
                    </div>
                    <KV k="Trend (from image)" v={a.trend} mono={false} />
                    <KV k="Structure (from image)" v={a.structure} mono={false} />
                    <div>
                      <p className="label mb-1">Levels read from pixels</p>
                      <BulletList items={a.levels.map((l) => `${l.price !== null ? fmtNum(l.price, 4) : "—"} · ${l.description}`)} empty="No levels read." />
                    </div>
                    <div>
                      <p className="label mb-1">Indicators visible</p>
                      <BulletList items={a.indicators_visible} empty="None identified." />
                    </div>
                    <div>
                      <p className="label mb-1">Possible setup (AI interpretation)</p>
                      <p className="text-fg">{a.possible_setup}</p>
                    </div>
                    <div>
                      <p className="label mb-1">Caveats</p>
                      <BulletList items={a.caveats} tone="warn" />
                    </div>
                  </div>
                ) : null}
                <p className="num text-[0.66rem] text-faint">
                  Image {result.image.width}×{result.image.height}px · {fmtNum(result.image.bytes / 1024, 0)} KB
                </p>
              </>
            ) : null}
          </PanelBody>
        </Panel>
      </div>

      {result?.market_data ? (
        <Panel>
          <PanelHeader title={`Actual market data · ${result.market_data.symbol}`} subtitle={result.data_precedence} actions={<DataBadge isDemo={result.market_data.is_demo} provider={result.market_data.provider} />} />
          <PanelBody className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-5">
            <KV k="Price" v={fmtPrice(result.market_data.price, result.market_data.symbol)} />
            <KV k="1H trend" v={<TrendBadge trend={result.market_data.trend_1h} />} />
            <KV k="1H regime" v={<RegimeBadge regime={result.market_data.regime_1h} />} />
            <KV k="Supports" v={result.market_data.supports.map((p) => fmtPrice(p, result.market_data!.symbol)).join(", ") || "—"} />
            <KV k="Resistances" v={result.market_data.resistances.map((p) => fmtPrice(p, result.market_data!.symbol)).join(", ") || "—"} />
          </PanelBody>
        </Panel>
      ) : null}
    </PageContainer>
  );
}
