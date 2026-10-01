"use client";

import type { AlertItem } from "@nexus/shared-types";
import { Bell, BellRing, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Callout } from "@/components/common/disclaimer";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { DataBlock, EmptyState } from "@/components/common/states";
import { SymbolSelect } from "@/components/market/pickers";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Switch } from "@/components/ui/switch";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { useNow } from "@/hooks/use-now";
import { del, errorMessage, patch, post } from "@/lib/api";
import { timeAgo, titleCase } from "@/lib/format";

const TYPES = [
  { value: "PRICE_LEVEL", label: "Price level", hint: "Fires when price crosses above / below a level" },
  { value: "SIGNAL_SCORE", label: "Signal score", hint: "Fires when a new signal reaches a minimum score" },
  { value: "REGIME_CHANGE", label: "Regime change", hint: "Fires when the detected market regime changes" },
  { value: "VOLATILITY_SPIKE", label: "Volatility spike", hint: "Fires when the volatility percentile exceeds a threshold" },
  { value: "BREAKOUT", label: "Breakout", hint: "Fires on a new structural breakout" },
  { value: "ECONOMIC_EVENT", label: "Economic event", hint: "Fires before a high-impact event" },
  { value: "NEWS_SENTIMENT_SHIFT", label: "News sentiment shift", hint: "Fires when average sentiment moves by more than a threshold" },
] as const;

function describe(a: AlertItem): string {
  const c = a.condition as Record<string, unknown>;
  switch (a.type) {
    case "PRICE_LEVEL":
      return `Price ${String(c.direction)} ${String(c.price)}`;
    case "SIGNAL_SCORE":
      return `Signal score ≥ ${String(c.min_score)}`;
    case "VOLATILITY_SPIKE":
      return `Volatility percentile ≥ ${String(c.min_percentile)}`;
    case "ECONOMIC_EVENT":
      return `${String(c.minutes_before)} min before high-impact${c.currency ? ` ${String(c.currency)}` : ""} events`;
    case "NEWS_SENTIMENT_SHIFT":
      return `Sentiment shift > ${String(c.threshold)}`;
    default:
      return titleCase(a.type);
  }
}

export function AlertsView() {
  const { data, error, isLoading, mutate } = useApi<AlertItem[]>("/api/alerts", 30_000);
  const now = useNow();
  const [type, setType] = useState<(typeof TYPES)[number]["value"]>("PRICE_LEVEL");
  const [symbol, setSymbol] = useState("XAUUSD");
  const [direction, setDirection] = useState("above");
  const [price, setPrice] = useState("");
  const [minScore, setMinScore] = useState("75");
  const [minPct, setMinPct] = useState("90");
  const [minutes, setMinutes] = useState("30");
  const [currency, setCurrency] = useState("");
  const [threshold, setThreshold] = useState("0.5");
  const [cooldown, setCooldown] = useState("60");
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const condition = (): Record<string, unknown> => {
    switch (type) {
      case "PRICE_LEVEL":
        return { direction, price: Number(price) };
      case "SIGNAL_SCORE":
        return { min_score: Number(minScore) };
      case "VOLATILITY_SPIKE":
        return { min_percentile: Number(minPct) };
      case "ECONOMIC_EVENT":
        return { minutes_before: Math.round(Number(minutes)), ...(currency ? { currency } : {}) };
      case "NEWS_SENTIMENT_SHIFT":
        return { threshold: Number(threshold) };
      default:
        return {};
    }
  };

  const create = async () => {
    setErr(null);
    try {
      await post("/api/alerts", { type, symbol: type === "ECONOMIC_EVENT" ? null : symbol, condition: condition(), note: note || null, cooldown_minutes: Number(cooldown) || 60 });
      toast.success("Alert created");
      setNote("");
      void mutate();
    } catch (e) {
      setErr(errorMessage(e));
    }
  };
  const toggle = async (a: AlertItem, enabled: boolean) => {
    try {
      await patch(`/api/alerts/${a.id}`, { enabled });
      void mutate();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  const remove = async (a: AlertItem) => {
    try {
      await del(`/api/alerts/${a.id}`);
      void mutate();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  const hint = TYPES.find((t) => t.value === type)?.hint;

  return (
    <PageContainer>
      <PageHeader title="Market Alerts" description="Configurable alerts evaluated in the background. Triggered alerts appear in notifications (and as browser notifications if enabled in Settings)." />
      <div className="grid gap-3 xl:grid-cols-[380px_1fr]">
        <Panel>
          <PanelHeader title="New alert" icon={<Plus />} />
          <PanelBody className="flex flex-col gap-3">
            <Field label="Type" htmlFor="al-type" hint={hint}>
              <Select id="al-type" value={type} onChange={(e) => setType(e.target.value as typeof type)}>
                {TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </Field>
            {type !== "ECONOMIC_EVENT" ? (
              <Field label="Asset" htmlFor="al-sym">
                <SymbolSelect id="al-sym" value={symbol} onChange={setSymbol} className="w-full" />
              </Field>
            ) : null}
            {type === "PRICE_LEVEL" ? (
              <div className="grid grid-cols-2 gap-2">
                <Field label="Direction" htmlFor="al-dir">
                  <Select id="al-dir" value={direction} onChange={(e) => setDirection(e.target.value)}>
                    <option value="above">Crosses above</option>
                    <option value="below">Crosses below</option>
                  </Select>
                </Field>
                <Field label="Price" htmlFor="al-price">
                  <Input id="al-price" type="number" step="any" value={price} onChange={(e) => setPrice(e.target.value)} />
                </Field>
              </div>
            ) : null}
            {type === "SIGNAL_SCORE" ? (
              <Field label="Minimum signal score (0-100)" htmlFor="al-score">
                <Input id="al-score" type="number" min={0} max={100} value={minScore} onChange={(e) => setMinScore(e.target.value)} />
              </Field>
            ) : null}
            {type === "VOLATILITY_SPIKE" ? (
              <Field label="Minimum volatility percentile" htmlFor="al-pct">
                <Input id="al-pct" type="number" min={50} max={100} value={minPct} onChange={(e) => setMinPct(e.target.value)} />
              </Field>
            ) : null}
            {type === "ECONOMIC_EVENT" ? (
              <div className="grid grid-cols-2 gap-2">
                <Field label="Minutes before" htmlFor="al-min">
                  <Input id="al-min" type="number" min={1} max={1440} value={minutes} onChange={(e) => setMinutes(e.target.value)} />
                </Field>
                <Field label="Currency (optional)" htmlFor="al-ccy">
                  <Input id="al-ccy" maxLength={3} value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase())} placeholder="USD" />
                </Field>
              </div>
            ) : null}
            {type === "NEWS_SENTIMENT_SHIFT" ? (
              <Field label="Shift threshold (0-1)" htmlFor="al-th">
                <Input id="al-th" type="number" min={0.05} max={1} step={0.05} value={threshold} onChange={(e) => setThreshold(e.target.value)} />
              </Field>
            ) : null}
            <div className="grid grid-cols-2 gap-2">
              <Field label="Cooldown (minutes)" htmlFor="al-cd">
                <Input id="al-cd" type="number" min={1} max={10080} value={cooldown} onChange={(e) => setCooldown(e.target.value)} />
              </Field>
              <Field label="Note" htmlFor="al-note">
                <Input id="al-note" maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} />
              </Field>
            </div>
            {err ? <Callout tone="down">{err}</Callout> : null}
            <Button variant="primary" onClick={create} disabled={type === "PRICE_LEVEL" && !price}>
              <BellRing /> Create alert
            </Button>
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Alerts" icon={<Bell />} subtitle={data ? `${data.filter((a) => a.enabled).length} enabled of ${data.length}` : undefined} />
          <DataBlock data={data} error={error} isLoading={isLoading} onRetry={() => mutate()} isEmpty={(d) => !d.length} empty={<EmptyState icon={<Bell />} title="No alerts yet" description="Create one on the left." />}>
            {(rows) => (
              <Table>
                <THead>
                  <tr>
                    <TH>Enabled</TH>
                    <TH>Type</TH>
                    <TH>Asset</TH>
                    <TH>Condition</TH>
                    <TH>Cooldown</TH>
                    <TH>Last triggered</TH>
                    <TH>Note</TH>
                    <TH />
                  </tr>
                </THead>
                <tbody>
                  {rows.map((a) => (
                    <TR key={a.id}>
                      <TD>
                        <Switch checked={a.enabled} onCheckedChange={(v) => toggle(a, v)} aria-label={`Enable ${a.type} alert`} />
                      </TD>
                      <TD className="text-xs">{titleCase(a.type)}</TD>
                      <TD className="font-semibold">{a.symbol ?? "All"}</TD>
                      <TD className="text-xs">{describe(a)}</TD>
                      <TD className="num text-muted">{a.cooldown_minutes}m</TD>
                      <TD className="num text-muted">{a.last_triggered_at ? (now ? timeAgo(a.last_triggered_at, now) : "") : "never"}</TD>
                      <TD className="max-w-48 truncate text-xs text-muted">{a.note ?? ""}</TD>
                      <TD>
                        <Button size="icon" variant="ghost" aria-label="Delete alert" onClick={() => remove(a)}>
                          <Trash2 />
                        </Button>
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            )}
          </DataBlock>
        </Panel>
      </div>
    </PageContainer>
  );
}
