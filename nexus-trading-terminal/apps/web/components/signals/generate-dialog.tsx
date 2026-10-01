"use client";

import type { SignalDetail, Timeframe } from "@nexus/shared-types";
import { Zap } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { SymbolSelect, TimeframeTabs } from "@/components/market/pickers";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Field } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { errorMessage, post } from "@/lib/api";
import { ANALYSIS_TIMEFRAMES } from "@/lib/constants";

export function GenerateSignalDialog({ defaultSymbol = "XAUUSD", defaultTf = "15m", trigger }: { defaultSymbol?: string; defaultTf?: Timeframe; trigger?: React.ReactNode }) {
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const [open, setOpen] = useState(false);
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [tf, setTf] = useState<Timeframe>(defaultTf);
  const [useAi, setUseAi] = useState(true);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      const s = await post<SignalDetail>("/api/signals/generate", { symbol, timeframe: tf, use_ai: useAi, force: true });
      toast.success(`${s.symbol} ${s.timeframe}: ${s.direction === "NO_TRADE" ? "NO TRADE" : s.direction} · score ${s.score.toFixed(0)}/100`);
      void mutate((k) => typeof k === "string" && (k.startsWith("/api/signals") || k.startsWith("/api/scanner")));
      setOpen(false);
      router.push(`/signals/${s.id}`);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="primary" size="sm">
            <Zap /> Analyze now
          </Button>
        )}
      </DialogTrigger>
      <DialogContent title="Run the signal pipeline" description="Market data → validation → quant → regime → signal engine → AI review (optional) → critic → historical matching → risk engine.">
        <div className="flex flex-col gap-4">
          <Field label="Asset" htmlFor="gen-symbol">
            <SymbolSelect id="gen-symbol" value={symbol} onChange={setSymbol} className="w-full" />
          </Field>
          <Field label="Timeframe">
            <TimeframeTabs value={tf} onChange={setTf} options={ANALYSIS_TIMEFRAMES} />
          </Field>
          <label className="flex items-center justify-between gap-3 rounded-sm border border-line bg-panel-2 px-3 py-2">
            <span>
              <span className="block text-xs font-medium text-fg">Independent AI review</span>
              <span className="block text-[0.7rem] text-muted">Claude and Gemini analyse separately; AI can only downgrade a setup to NO TRADE. Skipped automatically if no AI provider is configured.</span>
            </span>
            <Switch checked={useAi} onCheckedChange={setUseAi} aria-label="Use AI review" />
          </label>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={run} disabled={busy}>
              {busy ? "Running pipeline…" : "Run analysis"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
