"use client";

import type { SecretStatus, SettingsPayload } from "@nexus/shared-types";
import { Bell, Bot, Database, Download, Eye, EyeOff, KeyRound, LineChart, Palette, ShieldAlert, ShieldCheck, Sigma, Upload, Wallet } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { ConfirmDialog } from "@/components/common/confirm";
import { Callout } from "@/components/common/disclaimer";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { DataBlock } from "@/components/common/states";
import { useSettings } from "@/components/layout/use-system";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, errorMessage, post, put } from "@/lib/api";
import { DEFAULT_SYMBOLS, SYMBOL_NAMES } from "@/lib/constants";
import { downloadBlob } from "@/lib/download";
import { titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

type Values = Record<string, unknown>;

interface FieldMeta {
  label?: string;
  hint?: string;
  percent?: boolean;
  options?: string[];
  step?: number;
  min?: number;
  max?: number;
  nullable?: boolean;
}

const META: Record<string, Record<string, FieldMeta>> = {
  risk: {
    max_risk_per_trade: { label: "Max risk per trade", percent: true, hint: "Share of equity risked per trade (≤ 5%)" },
    max_daily_loss: { label: "Max daily loss", percent: true },
    max_weekly_loss: { label: "Max weekly loss", percent: true },
    max_drawdown: { label: "Max drawdown", percent: true, hint: "Trading halts beyond this drawdown" },
    max_open_positions: { step: 1 },
    max_correlated_positions: { step: 1 },
    correlation_threshold: { step: 0.05 },
    max_leverage: { step: 1 },
    max_position_lots: { step: 0.5 },
    min_rr: { label: "Minimum R:R", step: 0.1 },
    max_spread_atr: { label: "Max spread (× ATR)", step: 0.05 },
    max_slippage_bps: { label: "Max slippage (bps)" },
    news_filter: { hint: "Block new risk around high-impact events" },
    session_filter: { hint: "Block new risk when the market is closed" },
    sizing_method: { options: ["FIXED_PERCENT", "FIXED_AMOUNT", "VOLATILITY_ADJUSTED"] },
    fixed_risk_amount: { label: "Fixed risk amount ($)", hint: "Used when sizing method is FIXED_AMOUNT" },
  },
  signals: {
    min_score: { label: "Minimum signal score", hint: "0-100 quality score - not a probability" },
    min_score_margin: { label: "Min margin over opposite direction" },
    min_rr: { label: "Minimum R:R", step: 0.1 },
    max_spread_atr: { label: "Max spread (× ATR)", step: 0.05 },
    max_vol_percentile: { label: "Max volatility percentile" },
    news_blackout_before_min: { label: "News blackout before (min)", step: 5 },
    news_blackout_after_min: { label: "News blackout after (min)", step: 5 },
    min_historical_samples: { label: "Min similar historical setups", step: 1 },
    min_historical_expectancy: { label: "Min historical expectancy (R)", nullable: true, step: 0.05 },
    expiry_bars: { label: "Signal expiry (bars)", step: 1 },
  },
  ai: {
    enabled_in_pipeline: { label: "AI review in signal pipeline" },
    block_on_low_agreement: { label: "Downgrade on low agreement / conflict" },
    require_ai_review: { label: "Require AI review for ACTIVE signals", hint: "When on, signals stay NO_TRADE if no AI provider is available" },
    auto_briefings: { label: "Automatic session briefings" },
    ai_news_sentiment: { label: "AI news sentiment classification" },
    max_calls_per_day: { label: "Max AI calls per day", step: 10, hint: "Cost control hard cap" },
    cache_minutes: { label: "Response cache (minutes)", step: 5 },
  },
  paper: {
    auto_execute_signals: { label: "Auto-execute ACTIVE signals on paper", hint: "Still passes the risk engine; simulated only" },
    slippage_bps: { label: "Simulated slippage (bps)", step: 0.5 },
    move_stop_to_breakeven: { label: "Move stop to breakeven after TP1" },
    starting_balance: { label: "Starting balance ($)", step: 1000, hint: "Applies on account reset" },
    require_stop_loss: { label: "Require a stop loss on every order" },
  },
  data: {
    retention_days: { label: "Retention for resolved data (days)", nullable: true, step: 1, hint: "Blank = keep forever" },
    retain_no_trade_days: { label: "Retention for NO_TRADE signals (days)", nullable: true, step: 1, hint: "Blank = keep forever" },
  },
  notifications: {
    browser_enabled: { label: "Browser notifications", hint: "Shown when the tab is in the background" },
    new_signal: { label: "New signal" },
    signal_invalidated: { label: "Signal invalidated" },
    target_reached: { label: "Target reached" },
    stop_reached: { label: "Stop reached" },
    economic_event: { label: "Major economic event" },
    risk_limit: { label: "Risk limit" },
    data_disconnection: { label: "Data disconnection" },
  },
};

function equal(a: unknown, b: unknown) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function GenericForm({ category, values, onSaved, exclude = [] }: { category: string; values: Values; onSaved: () => void; exclude?: string[] }) {
  const [draft, setDraft] = useState<Values>(values);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const meta = META[category] ?? {};
  const changed = Object.keys(draft).filter((k) => !equal(draft[k], values[k]));
  const save = async () => {
    setBusy(true);
    setErr(null);
    try {
      const patchBody = Object.fromEntries(changed.map((k) => [k, draft[k]]));
      await put(`/api/settings/${category}`, patchBody);
      toast.success(`${titleCase(category)} settings saved`);
      onSaved();
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  const fields = Object.entries(draft).filter(([k, v]) => !exclude.includes(k) && (typeof v !== "object" || v === null));
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {fields.map(([k, v]) => {
          const m = meta[k] ?? {};
          const label = m.label ?? titleCase(k);
          if (typeof v === "boolean") {
            return (
              <label key={k} className="flex items-center justify-between gap-3 rounded-sm border border-line bg-panel-2 px-3 py-2">
                <span className="min-w-0">
                  <span className="block text-xs text-fg">{label}</span>
                  {m.hint ? <span className="block text-[0.68rem] text-faint">{m.hint}</span> : null}
                </span>
                <Switch checked={v} onCheckedChange={(nv) => setDraft({ ...draft, [k]: nv })} aria-label={label} />
              </label>
            );
          }
          if (m.options) {
            return (
              <Field key={k} label={label} htmlFor={`${category}-${k}`} hint={m.hint}>
                <Select id={`${category}-${k}`} value={String(v)} onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}>
                  {m.options.map((o) => (
                    <option key={o} value={o}>
                      {titleCase(o)}
                    </option>
                  ))}
                </Select>
              </Field>
            );
          }
          const isNum = typeof v === "number" || (v === null && m.nullable);
          const shown = v === null ? "" : m.percent ? String(Math.round((v as number) * 10000) / 100) : String(v);
          return (
            <Field key={k} label={m.percent ? `${label} (%)` : label} htmlFor={`${category}-${k}`} hint={m.hint}>
              <Input
                id={`${category}-${k}`}
                type={isNum ? "number" : "text"}
                step={m.percent ? 0.1 : (m.step ?? "any")}
                value={shown}
                onChange={(e) => {
                  const raw = e.target.value;
                  if (!isNum) return setDraft({ ...draft, [k]: raw });
                  if (raw === "") return setDraft({ ...draft, [k]: m.nullable ? null : 0 });
                  const n = Number(raw);
                  setDraft({ ...draft, [k]: m.percent ? n / 100 : n });
                }}
              />
            </Field>
          );
        })}
      </div>
      {err ? <Callout tone="down" title="Not saved">{err}</Callout> : null}
      <div className="flex items-center justify-end gap-2">
        {changed.length ? <span className="text-[0.7rem] text-warn">{changed.length} unsaved change(s)</span> : null}
        <Button variant="ghost" size="sm" onClick={() => setDraft(values)} disabled={!changed.length}>
          Revert
        </Button>
        <Button variant="primary" size="sm" onClick={save} disabled={busy || !changed.length}>
          Save
        </Button>
      </div>
    </div>
  );
}

function WeightsForm({ values, onSaved }: { values: Values; onSaved: () => void }) {
  const weights = values.weights as Record<string, number>;
  const [draft, setDraft] = useState(weights);
  const [plan, setPlan] = useState((values.exit_plan as number[]).join(", "));
  const [err, setErr] = useState<string | null>(null);
  const total = Object.values(draft).reduce((a, b) => a + b, 0);
  const save = async () => {
    setErr(null);
    try {
      await put("/api/settings/signals", { weights: draft, exit_plan: plan.split(",").map((x) => Number(x.trim())).filter((x) => !Number.isNaN(x)) });
      toast.success("Scoring weights saved");
      onSaved();
    } catch (e) {
      setErr(errorMessage(e));
    }
  };
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Object.entries(draft).map(([k, v]) => (
          <Field key={k} label={titleCase(k)} htmlFor={`w-${k}`}>
            <Input id={`w-${k}`} type="number" min={0} max={100} step={1} value={v} onChange={(e) => setDraft({ ...draft, [k]: Number(e.target.value) })} />
          </Field>
        ))}
      </div>
      <p className={cn("text-xs", Math.abs(total - 100) < 0.01 ? "text-muted" : "text-warn")}>
        Total {total}
        {Math.abs(total - 100) >= 0.01 && total > 0 ? ` - weights are normalised to a 100-point scale (e.g. trend counts ${((draft.trend / total) * 100).toFixed(1)} points)` : " / 100"}
      </p>
      <Field label="Exit plan (fractions at TP1, TP2, TP3)" htmlFor="w-plan" hint="Must sum to 1, e.g. 0.5, 0.3, 0.2">
        <Input id="w-plan" value={plan} onChange={(e) => setPlan(e.target.value)} />
      </Field>
      {err ? <Callout tone="down" title="Not saved">{err}</Callout> : null}
      <Button variant="primary" size="sm" className="self-end" onClick={save}>
        Save weights
      </Button>
    </div>
  );
}

function MarketsForm({ values, onSaved }: { values: Values; onSaved: () => void }) {
  const [assets, setAssets] = useState<string[]>(values.default_assets as string[]);
  const [tf, setTf] = useState(String(values.default_timeframe));
  const [autoScan, setAutoScan] = useState(Boolean(values.auto_scan));
  const save = async () => {
    try {
      await put("/api/settings/markets", { default_assets: assets, default_timeframe: tf, auto_scan: autoScan });
      toast.success("Market settings saved");
      onSaved();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  return (
    <div className="flex flex-col gap-3">
      <p className="label">Default assets (scanned and shown across the app)</p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {DEFAULT_SYMBOLS.map((s) => (
          <label key={s} className={cn("flex cursor-pointer items-center gap-2 rounded-sm border px-2 py-1.5 text-xs", assets.includes(s) ? "border-accent/50 bg-accent/10 text-fg" : "border-line bg-panel-2 text-muted")}>
            <input type="checkbox" className="accent-[var(--color-accent)]" checked={assets.includes(s)} onChange={(e) => setAssets(e.target.checked ? [...assets, s] : assets.filter((x) => x !== s))} />
            <span className="font-semibold">{s}</span>
            <span className="truncate text-faint">{SYMBOL_NAMES[s]}</span>
          </label>
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Default timeframe" htmlFor="m-tf">
          <Select id="m-tf" value={tf} onChange={(e) => setTf(e.target.value)}>
            {["1m", "5m", "15m", "30m", "1H", "4H", "1D"].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </Select>
        </Field>
        <label className="flex items-center justify-between gap-3 self-end rounded-sm border border-line bg-panel-2 px-3 py-2 text-xs">
          Automatic background scanning on each new bar
          <Switch checked={autoScan} onCheckedChange={setAutoScan} aria-label="Automatic scanning" />
        </label>
      </div>
      <Button variant="primary" size="sm" className="self-end" onClick={save} disabled={!assets.length}>
        Save
      </Button>
    </div>
  );
}

const PROVIDER_OPTIONS: Record<string, string[]> = {
  MARKET_DATA_PROVIDER: ["demo", "twelvedata"],
  NEWS_PROVIDER: ["demo", "finnhub"],
  ECONOMIC_CALENDAR_PROVIDER: ["demo", "fmp"],
};

const SECRET_INFO: Record<string, string> = {
  ANTHROPIC_API_KEY: "Claude (Anthropic) - analyst, critic, explanations, chat, briefings, chart scanner",
  GEMINI_API_KEY: "Gemini (Google) - independent second analyst and chart scanner",
  MARKET_DATA_API_KEY: "Market data provider key (Twelve Data)",
  NEWS_API_KEY: "News provider key (Finnhub)",
  ECONOMIC_CALENDAR_API_KEY: "Economic calendar key (Financial Modeling Prep)",
  BROKER_API_KEY: "Live broker key - live execution adapters are not implemented; stored for future use",
  BROKER_API_SECRET: "Live broker secret",
};

function SecretRow({ s, onSave }: { s: SecretStatus; onSave: (key: string, value: string | null) => Promise<void> }) {
  const [value, setValue] = useState("");
  const [show, setShow] = useState(false);
  return (
    <div className="grid gap-2 border-b border-line/60 py-2.5 last:border-0 md:grid-cols-[260px_1fr_auto] md:items-center">
      <div className="min-w-0">
        <p className="num text-xs font-semibold text-fg">{s.key}</p>
        <p className="text-[0.68rem] text-faint">{SECRET_INFO[s.key]}</p>
      </div>
      <div className="flex items-center gap-2">
        {s.configured ? <Badge tone="up">Configured {s.hint ?? ""}</Badge> : <Badge>Not set</Badge>}
        <div className="relative flex-1">
          <Input
            type={show ? "text" : "password"}
            autoComplete="off"
            spellCheck={false}
            aria-label={`New value for ${s.key}`}
            placeholder={s.configured ? "Enter a new value to replace" : "Paste key"}
            value={value}
            onChange={(e) => setValue(e.target.value.trim())}
            className="pr-8"
          />
          <button type="button" className="absolute right-1.5 top-1/2 -translate-y-1/2 text-faint hover:text-fg" onClick={() => setShow((v) => !v)} aria-label={show ? "Hide value" : "Show value"}>
            {show ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
          </button>
        </div>
      </div>
      <div className="flex gap-1.5">
        <Button
          size="sm"
          variant="primary"
          aria-label={`Save ${s.key}`}
          disabled={!value}
          onClick={async () => {
            await onSave(s.key, value);
            setValue("");
            setShow(false);
          }}
        >
          Save
        </Button>
        {s.configured ? (
          <Button size="sm" variant="ghost" aria-label={`Clear ${s.key}`} onClick={() => onSave(s.key, null)}>
            Clear
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function ProvidersPanel({ data, onSaved }: { data: SettingsPayload; onSaved: () => void }) {
  const [prov, setProv] = useState(data.providers);
  const saveSecret = async (key: string, value: string | null) => {
    try {
      await put("/api/settings-secrets", { values: { [key]: value } });
      toast.success(value ? `${key} saved (server-side; never shown again)` : `${key} cleared`);
      onSaved();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  const saveProviders = async () => {
    const changed = Object.fromEntries(Object.entries(prov).filter(([k, v]) => data.providers[k] !== v));
    if (!Object.keys(changed).length) return;
    try {
      await put("/api/settings-secrets", { values: changed });
      toast.success("Providers updated - services reloaded");
      onSaved();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  return (
    <div className="flex flex-col gap-3">
      <Callout tone="accent" title="How keys are handled">
        Keys are sent once to the local NEXUS server, stored in a git-ignored <code>.secrets.env</code> file (owner-only permissions) and loaded into the backend environment. They are never returned to the browser - only “configured” and the last four characters are shown. You can also set them in <code>.env</code> instead.
      </Callout>
      <Panel>
        <PanelHeader title="API keys" icon={<KeyRound />} />
        <PanelBody className="py-0">
          {data.secrets.map((s) => (
            <SecretRow key={s.key} s={s} onSave={saveSecret} />
          ))}
        </PanelBody>
      </Panel>
      <Panel>
        <PanelHeader title="Providers & models" icon={<Database />} subtitle="Without a key, each provider stays in clearly labelled DEMO mode" />
        <PanelBody className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {Object.entries(prov).map(([k, v]) => (
              <Field key={k} label={titleCase(k)} htmlFor={`prov-${k}`}>
                {PROVIDER_OPTIONS[k] ? (
                  <Select id={`prov-${k}`} value={v} onChange={(e) => setProv({ ...prov, [k]: e.target.value })}>
                    {PROVIDER_OPTIONS[k].map((o) => (
                      <option key={o}>{o}</option>
                    ))}
                  </Select>
                ) : (
                  <Input id={`prov-${k}`} value={v} onChange={(e) => setProv({ ...prov, [k]: e.target.value.trim() })} />
                )}
              </Field>
            ))}
          </div>
          <Button size="sm" variant="primary" className="self-end" onClick={saveProviders} disabled={equal(prov, data.providers)}>
            Save providers
          </Button>
        </PanelBody>
      </Panel>
    </div>
  );
}

function LiveTradingPanel({ data, onSaved }: { data: SettingsPayload; onSaved: () => void }) {
  const lt = data.live_trading;
  const [confirm, setConfirm] = useState(false);
  const setSwitch = async (on: boolean) => {
    await post("/api/settings/live-trading-switch", { on });
    toast[on ? "warning" : "success"](`Live-trading UI safety switch ${on ? "ON" : "OFF"}`);
    onSaved();
  };
  return (
    <div className="flex flex-col gap-3">
      <Callout tone="down" title="Live execution is disabled by default">
        Real orders require all three gates: <b>LIVE_TRADING_ENABLED=true</b> in the server environment, this UI safety switch ON, and a configured live broker adapter. No live broker adapter (MT5, IBKR, Alpaca) is implemented in this build, so live execution cannot be armed. Paper mode never sends a real order.
      </Callout>
      <Panel>
        <PanelHeader title="Broker & live-trading gate" icon={<ShieldAlert />} />
        <PanelBody className="flex flex-col gap-3 text-xs">
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="rounded-sm border border-line bg-panel-2 p-2.5">
              <p className="label">Server env LIVE_TRADING_ENABLED</p>
              <p className={cn("mt-1 font-semibold", lt.env_enabled ? "text-warn" : "text-up")}>{lt.env_enabled ? "true" : "false"}</p>
            </div>
            <div className="rounded-sm border border-line bg-panel-2 p-2.5">
              <p className="label">Broker</p>
              <p className="mt-1 font-semibold text-fg">{lt.broker}</p>
            </div>
            <div className="rounded-sm border border-line bg-panel-2 p-2.5">
              <p className="label">Live execution</p>
              <p className={cn("mt-1 font-semibold", lt.allowed ? "text-down" : "text-up")}>{lt.allowed ? "ARMED" : "DISABLED"}</p>
            </div>
          </div>
          <label className="flex items-center justify-between gap-3 rounded-sm border border-down/40 bg-down/5 px-3 py-2.5">
            <span>
              <span className="block font-semibold text-fg">UI live-trading safety switch</span>
              <span className="block text-[0.7rem] text-muted">Second of three gates. Turning it on alone does not enable live trading.</span>
            </span>
            <Switch checked={lt.ui_switch_on} onCheckedChange={(on) => (on ? setConfirm(true) : void setSwitch(false))} aria-label="Live-trading UI safety switch" />
          </label>
          <ul className="list-disc pl-4 text-muted">
            {lt.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </PanelBody>
      </Panel>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="Turn the live-trading safety switch ON?"
        description="This is one of three required gates. Live execution additionally needs LIVE_TRADING_ENABLED=true on the server and an implemented live broker adapter. The emergency kill switch always overrides."
        confirmLabel="Turn switch ON"
        onConfirm={() => setSwitch(true)}
      />
    </div>
  );
}

function AppearancePanel({ values, onSaved }: { values: Values; onSaved: () => void }) {
  const save = async (patchBody: Values) => {
    try {
      await put("/api/settings/appearance", patchBody);
      onSaved();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  const accents: Record<string, string> = { cyan: "#22d3ee", purple: "#a78bfa", emerald: "#34d399", amber: "#fbbf24" };
  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="label mb-2">Accent colour</p>
        <div className="flex gap-2">
          {Object.entries(accents).map(([k, c]) => (
            <button
              key={k}
              type="button"
              onClick={() => save({ accent: k })}
              aria-pressed={values.accent === k}
              aria-label={`${k} accent`}
              className={cn("flex items-center gap-2 rounded-sm border px-3 py-1.5 text-xs capitalize", values.accent === k ? "border-fg text-fg" : "border-line text-muted hover:text-fg")}
            >
              <span className="size-3 rounded-full" style={{ background: c }} /> {k}
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="flex items-center justify-between gap-3 rounded-sm border border-line bg-panel-2 px-3 py-2 text-xs">
          Comfortable density
          <Switch checked={values.density === "comfortable"} onCheckedChange={(v) => save({ density: v ? "comfortable" : "compact" })} aria-label="Comfortable density" />
        </label>
        <label className="flex items-center justify-between gap-3 rounded-sm border border-line bg-panel-2 px-3 py-2 text-xs">
          Reduce motion
          <Switch checked={Boolean(values.reduce_motion)} onCheckedChange={(v) => save({ reduce_motion: v })} aria-label="Reduce motion" />
        </label>
        <label className="flex items-center justify-between gap-3 rounded-sm border border-line bg-panel-2 px-3 py-2 text-xs">
          Show intelligence panel by default
          <Switch checked={Boolean(values.show_right_panel)} onCheckedChange={(v) => save({ show_right_panel: v })} aria-label="Show intelligence panel" />
        </label>
      </div>
    </div>
  );
}

function ConfigTransfer({ onSaved }: { onSaved: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const exportJson = async () => {
    try {
      const data = await api<unknown>("/api/settings/export");
      downloadBlob(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }), "nexus-config.json");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  const importJson = async (f: File | undefined) => {
    if (!f) return;
    try {
      const parsed = JSON.parse(await f.text()) as unknown;
      const res = await post<{ imported: string[] }>("/api/settings/import", parsed);
      toast.success(`Imported: ${res.imported.join(", ") || "nothing changed"}`);
      onSaved();
    } catch (e) {
      toast.error(e instanceof SyntaxError ? "File is not valid JSON" : errorMessage(e));
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  };
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button size="sm" variant="outline" onClick={exportJson}>
        <Download /> Export JSON configuration
      </Button>
      <Button size="sm" variant="outline" onClick={() => fileRef.current?.click()}>
        <Upload /> Import JSON configuration
      </Button>
      <input ref={fileRef} type="file" accept="application/json,.json" className="sr-only" aria-label="Configuration JSON file" onChange={(e) => importJson(e.target.files?.[0])} />
      <span className="text-[0.7rem] text-faint">Exports contain settings only - never API keys. Imports are validated; the live-trading switch is never imported.</span>
    </div>
  );
}

export function SettingsView() {
  const { data, error, isLoading, mutate } = useSettings();
  const { mutate: globalMutate } = useSWRConfig();
  const refresh = () => {
    void mutate();
    void globalMutate((k) => typeof k === "string" && (k.startsWith("/api/system") || k.startsWith("/api/risk") || k.startsWith("/api/ai")));
  };
  const requestBrowserNotifications = async () => {
    if (typeof Notification === "undefined") {
      toast.error("This browser does not support notifications");
      return;
    }
    const p = await Notification.requestPermission();
    if (p === "granted") {
      await put("/api/settings/notifications", { browser_enabled: true });
      refresh();
      toast.success("Browser notifications enabled");
    } else toast.error("Permission was not granted");
  };
  return (
    <PageContainer>
      <PageHeader title="Settings" description="Data providers, API keys, AI, risk, signals, paper trading, appearance, notifications and data retention. Every change is validated server-side and written to the audit log." actions={<ConfigTransfer onSaved={refresh} />} />
      <DataBlock data={data} error={error} isLoading={isLoading} onRetry={() => mutate()} rows={10}>
        {(d) => (
          <Tabs defaultValue="providers">
            <TabsList>
              <TabsTrigger value="providers">Data & API keys</TabsTrigger>
              <TabsTrigger value="ai">AI</TabsTrigger>
              <TabsTrigger value="risk">Risk</TabsTrigger>
              <TabsTrigger value="signals">Signals</TabsTrigger>
              <TabsTrigger value="markets">Markets</TabsTrigger>
              <TabsTrigger value="paper">Paper trading</TabsTrigger>
              <TabsTrigger value="broker">Broker & live trading</TabsTrigger>
              <TabsTrigger value="appearance">Appearance</TabsTrigger>
              <TabsTrigger value="notifications">Notifications</TabsTrigger>
              <TabsTrigger value="data">Data retention</TabsTrigger>
            </TabsList>
            <TabsContent value="providers">
              <ProvidersPanel key={JSON.stringify(d.providers)} data={d} onSaved={refresh} />
            </TabsContent>
            <TabsContent value="ai">
              <Panel>
                <PanelHeader title="AI settings" icon={<Bot />} subtitle="Model names are set under Data & API keys. AI can only downgrade signals; it never places trades." />
                <PanelBody>
                  <GenericForm key={JSON.stringify(d.settings.ai)} category="ai" values={d.settings.ai} onSaved={refresh} />
                </PanelBody>
              </Panel>
            </TabsContent>
            <TabsContent value="risk">
              <Panel>
                <PanelHeader title="Risk engine" icon={<ShieldCheck />} subtitle="Deterministic limits with final veto over every order" />
                <PanelBody>
                  <GenericForm key={JSON.stringify(d.settings.risk)} category="risk" values={d.settings.risk} onSaved={refresh} />
                </PanelBody>
              </Panel>
            </TabsContent>
            <TabsContent value="signals">
              <div className="flex flex-col gap-3">
                <Panel>
                  <PanelHeader title="Signal filters" icon={<Sigma />} />
                  <PanelBody>
                    <GenericForm key={JSON.stringify(d.settings.signals)} category="signals" values={d.settings.signals} onSaved={refresh} />
                  </PanelBody>
                </Panel>
                <Panel>
                  <PanelHeader title="Scoring weights" subtitle="Each component contributes up to its share of a 100-point score" />
                  <PanelBody>
                    <WeightsForm key={JSON.stringify(d.settings.signals)} values={d.settings.signals} onSaved={refresh} />
                  </PanelBody>
                </Panel>
              </div>
            </TabsContent>
            <TabsContent value="markets">
              <Panel>
                <PanelHeader title="Default assets & timeframe" icon={<LineChart />} />
                <PanelBody>
                  <MarketsForm key={JSON.stringify(d.settings.markets)} values={d.settings.markets} onSaved={refresh} />
                </PanelBody>
              </Panel>
            </TabsContent>
            <TabsContent value="paper">
              <Panel>
                <PanelHeader title="Paper trading" icon={<Wallet />} subtitle="Simulated execution settings" />
                <PanelBody>
                  <GenericForm key={JSON.stringify(d.settings.paper)} category="paper" values={d.settings.paper} onSaved={refresh} />
                </PanelBody>
              </Panel>
            </TabsContent>
            <TabsContent value="broker">
              <LiveTradingPanel data={d} onSaved={refresh} />
            </TabsContent>
            <TabsContent value="appearance">
              <Panel>
                <PanelHeader title="Appearance" icon={<Palette />} />
                <PanelBody>
                  <AppearancePanel values={d.settings.appearance} onSaved={refresh} />
                </PanelBody>
              </Panel>
            </TabsContent>
            <TabsContent value="notifications">
              <Panel>
                <PanelHeader
                  title="Notifications"
                  icon={<Bell />}
                  actions={
                    <Button size="xs" variant="outline" onClick={requestBrowserNotifications}>
                      Allow browser notifications
                    </Button>
                  }
                />
                <PanelBody>
                  <GenericForm key={JSON.stringify(d.settings.notifications)} category="notifications" values={d.settings.notifications} onSaved={refresh} />
                </PanelBody>
              </Panel>
            </TabsContent>
            <TabsContent value="data">
              <Panel>
                <PanelHeader title="Data retention" icon={<Database />} subtitle="Background job deletes resolved records older than these limits" />
                <PanelBody>
                  <GenericForm key={JSON.stringify(d.settings.data)} category="data" values={d.settings.data} onSaved={refresh} />
                </PanelBody>
              </Panel>
            </TabsContent>
          </Tabs>
        )}
      </DataBlock>
    </PageContainer>
  );
}
