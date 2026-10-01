"use client";

import type { JournalEntry } from "@nexus/shared-types";
import { ChevronDown, ChevronRight, NotebookPen, Plus, Save } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Fragment, useState } from "react";
import { toast } from "sonner";

import { ExportButton } from "@/components/common/export-button";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { DataBlock, EmptyState } from "@/components/common/states";
import { DirectionBadge, ModeBadge, RegimeBadge, StatusBadge } from "@/components/market/badges";
import { Segmented, SymbolSelect } from "@/components/market/pickers";
import { Signed } from "@/components/market/price";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { ApiError, errorMessage, patch, post, qs } from "@/lib/api";
import { REGIME_LABEL } from "@/lib/constants";
import { fmtDateTime, fmtDuration, fmtMoney, fmtNum, fmtPrice, fmtR, titleCase } from "@/lib/format";

const RESULTS = ["", "OPEN", "WIN", "LOSS", "BREAKEVEN", "EXPIRED", "INVALIDATED", "CANCELLED"];

function EntryDetail({ e, onSaved }: { e: JournalEntry; onSaved: () => void }) {
  const [notes, setNotes] = useState(e.notes ?? "");
  const [tags, setTags] = useState(e.tags.join(", "));
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      await patch(`/api/journal/${e.id}`, { notes, tags: tags.split(",").map((t) => t.trim()).filter(Boolean).slice(0, 20) });
      toast.success("Journal entry saved");
      onSaved();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const ai = e.ai_reasoning;
  return (
    <div className="grid gap-4 bg-panel-2/60 px-4 py-3 text-xs lg:grid-cols-3">
      <div className="flex flex-col gap-1">
        <p className="label">Execution</p>
        <p>
          Stop <span className="num">{fmtPrice(e.stop, e.symbol)}</span> · Lots <span className="num">{fmtNum(e.lots, 2)}</span>
        </p>
        <p>
          Fees <span className="num">{fmtMoney(e.fees, 2)}</span> · Slippage <span className="num">{fmtPrice(e.slippage, e.symbol)}</span>
        </p>
        <p>
          Duration <span className="num">{fmtDuration(e.duration_seconds)}</span> · MFE <span className="num">{fmtR(e.mfe_r)}</span> · MAE <span className="num">{fmtR(e.mae_r)}</span>
        </p>
        <div className="mt-1 flex flex-wrap gap-2">
          {e.signal_id ? (
            <Link className="text-accent hover:underline" href={`/signals/${e.signal_id}`}>
              Open signal →
            </Link>
          ) : null}
          {e.is_demo ? <ModeBadge mode="DEMO" /> : null}
        </div>
      </div>
      <div className="flex flex-col gap-1">
        <p className="label">AI reasoning (recorded at entry)</p>
        {ai && Object.keys(ai).length ? (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
            {Object.entries(ai).map(([k, v]) => (
              <Fragment key={k}>
                <dt className="text-muted">{titleCase(k)}</dt>
                <dd className="break-words text-fg">{Array.isArray(v) ? v.join(" · ") : typeof v === "object" && v !== null ? JSON.stringify(v) : String(v)}</dd>
              </Fragment>
            ))}
          </dl>
        ) : (
          <p className="text-faint">None recorded.</p>
        )}
      </div>
      <div className="flex flex-col gap-2">
        <Field label="Notes" htmlFor={`n-${e.id}`}>
          <Textarea id={`n-${e.id}`} value={notes} maxLength={5000} onChange={(ev) => setNotes(ev.target.value)} placeholder="What did you learn from this trade?" />
        </Field>
        <Field label="Tags (comma separated)" htmlFor={`t-${e.id}`}>
          <Input id={`t-${e.id}`} value={tags} onChange={(ev) => setTags(ev.target.value)} />
        </Field>
        <Button size="xs" variant="primary" className="self-end" onClick={save} disabled={busy}>
          <Save /> Save
        </Button>
      </div>
    </div>
  );
}

function ManualTradeDialog({ open, onOpenChange, onSaved }: { open: boolean; onOpenChange: (v: boolean) => void; onSaved: () => void }) {
  const [f, setF] = useState({ symbol: "XAUUSD", direction: "LONG", entry_time: "", exit_time: "", entry_price: "", exit_price: "", stop: "", lots: "", fees: "0", strategy: "", regime: "", notes: "", tags: "" });
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (ev: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: ev.target.value });
  const num = (v: string) => (v === "" ? null : Number(v));
  const submit = async () => {
    setErr(null);
    try {
      await post("/api/journal", {
        symbol: f.symbol,
        direction: f.direction,
        entry_time: f.entry_time ? new Date(`${f.entry_time}Z`).toISOString() : null,
        exit_time: f.exit_time ? new Date(`${f.exit_time}Z`).toISOString() : null,
        entry_price: num(f.entry_price),
        exit_price: num(f.exit_price),
        stop: num(f.stop),
        lots: num(f.lots),
        fees: Number(f.fees) || 0,
        strategy: f.strategy || null,
        regime: f.regime || null,
        notes: f.notes || null,
        tags: f.tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
      toast.success("Manual trade recorded");
      onOpenChange(false);
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : errorMessage(e));
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Record a manual trade" description="For trades taken outside NEXUS. P&L and R are computed from your prices; times are UTC.">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Asset" htmlFor="m-sym">
            <SymbolSelect id="m-sym" value={f.symbol} onChange={(v) => setF({ ...f, symbol: v })} className="w-full" />
          </Field>
          <Field label="Direction" htmlFor="m-dir">
            <Select id="m-dir" value={f.direction} onChange={set("direction")}>
              <option>LONG</option>
              <option>SHORT</option>
            </Select>
          </Field>
          <Field label="Entry time (UTC)" htmlFor="m-et">
            <Input id="m-et" type="datetime-local" value={f.entry_time} onChange={set("entry_time")} />
          </Field>
          <Field label="Exit time (UTC)" htmlFor="m-xt">
            <Input id="m-xt" type="datetime-local" value={f.exit_time} onChange={set("exit_time")} />
          </Field>
          <Field label="Entry price" htmlFor="m-ep">
            <Input id="m-ep" type="number" step="any" value={f.entry_price} onChange={set("entry_price")} />
          </Field>
          <Field label="Exit price" htmlFor="m-xp">
            <Input id="m-xp" type="number" step="any" value={f.exit_price} onChange={set("exit_price")} />
          </Field>
          <Field label="Stop" htmlFor="m-st">
            <Input id="m-st" type="number" step="any" value={f.stop} onChange={set("stop")} />
          </Field>
          <Field label="Lots" htmlFor="m-lots">
            <Input id="m-lots" type="number" step="0.01" value={f.lots} onChange={set("lots")} />
          </Field>
          <Field label="Fees ($)" htmlFor="m-fees">
            <Input id="m-fees" type="number" step="any" min={0} value={f.fees} onChange={set("fees")} />
          </Field>
          <Field label="Strategy" htmlFor="m-strat">
            <Input id="m-strat" value={f.strategy} maxLength={60} onChange={set("strategy")} placeholder="Manual" />
          </Field>
          <Field label="Regime" htmlFor="m-reg">
            <Select id="m-reg" value={f.regime} onChange={set("regime")}>
              <option value="">—</option>
              {Object.entries(REGIME_LABEL).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Tags" htmlFor="m-tags">
            <Input id="m-tags" value={f.tags} onChange={set("tags")} placeholder="breakout, london" />
          </Field>
          <Field label="Notes" htmlFor="m-notes" className="col-span-2">
            <Textarea id="m-notes" value={f.notes} maxLength={5000} onChange={set("notes")} />
          </Field>
        </div>
        {err ? <p className="mt-2 text-xs text-down">{err}</p> : null}
        <div className="mt-3 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} disabled={!f.entry_time || !f.entry_price}>
            Save trade
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function JournalView() {
  const params = useSearchParams();
  const [symbol, setSymbol] = useState(params.get("symbol") ?? "");
  const [type, setType] = useState<"" | "SIGNAL" | "PAPER_TRADE" | "MANUAL_TRADE">("");
  const [result, setResult] = useState("");
  const [regime, setRegime] = useState("");
  const [strategy, setStrategy] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [manual, setManual] = useState(false);
  const { data, error, isLoading, mutate } = useApi<JournalEntry[]>(
    `/api/journal${qs({ symbol, entry_type: type, result, regime, strategy, start: start ? `${start}T00:00:00Z` : undefined, end: end ? `${end}T23:59:59Z` : undefined, limit: 1000 })}`,
    30_000,
  );
  const strategies = [...new Set((data ?? []).map((e) => e.strategy).filter(Boolean))] as string[];

  return (
    <PageContainer>
      <PageHeader
        title="Trade Journal"
        description="Every signal, paper trade and manual trade is recorded automatically with entry, exit, fees, slippage, P&L, R multiple, duration, strategy, regime and the AI reasoning at the time."
        actions={
          <>
            <ExportButton path="/api/journal/export.csv" filename="nexus-journal.csv" size="sm" variant="outline" />
            <Button size="sm" variant="primary" onClick={() => setManual(true)}>
              <Plus /> Manual trade
            </Button>
          </>
        }
      />
      <div className="flex flex-wrap items-center gap-2">
        <SymbolSelect value={symbol} onChange={setSymbol} allowAll className="h-7 text-xs" />
        <Segmented
          label="Entry type"
          value={type}
          onChange={setType}
          options={[
            { value: "", label: "All" },
            { value: "SIGNAL", label: "Signals" },
            { value: "PAPER_TRADE", label: "Paper" },
            { value: "MANUAL_TRADE", label: "Manual" },
          ]}
        />
        <Select aria-label="Result" value={result} onChange={(e) => setResult(e.target.value)} className="h-7 w-32 text-xs">
          {RESULTS.map((r) => (
            <option key={r} value={r}>
              {r ? titleCase(r) : "Any result"}
            </option>
          ))}
        </Select>
        <Select aria-label="Regime" value={regime} onChange={(e) => setRegime(e.target.value)} className="h-7 w-40 text-xs">
          <option value="">Any regime</option>
          {Object.entries(REGIME_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </Select>
        <Select aria-label="Strategy" value={strategy} onChange={(e) => setStrategy(e.target.value)} className="h-7 w-40 text-xs">
          <option value="">Any strategy</option>
          {strategies.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </Select>
        <Input aria-label="From date" type="date" value={start} onChange={(e) => setStart(e.target.value)} className="h-7 w-36 text-xs" />
        <Input aria-label="To date" type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="h-7 w-36 text-xs" />
      </div>
      <Panel>
        <PanelHeader title="Entries" icon={<NotebookPen />} subtitle={data ? `${data.length} entries` : undefined} />
        <DataBlock data={data} error={error} isLoading={isLoading} onRetry={() => mutate()} rows={10} isEmpty={(d) => !d.length} empty={<EmptyState title="No journal entries match" />}>
          {(rows) => (
            <Table>
              <THead>
                <tr>
                  <TH />
                  <TH>Date (UTC)</TH>
                  <TH>Type</TH>
                  <TH>Asset</TH>
                  <TH>Direction</TH>
                  <TH>Strategy</TH>
                  <TH align="right">Entry</TH>
                  <TH align="right">Exit</TH>
                  <TH align="right">R</TH>
                  <TH align="right">P&L</TH>
                  <TH>Regime</TH>
                  <TH align="right">Signal score</TH>
                  <TH>Result</TH>
                </tr>
              </THead>
              <tbody>
                {rows.map((e) => (
                  <Fragment key={e.id}>
                    <TR className="cursor-pointer" onClick={() => setOpen(open === e.id ? null : e.id)} aria-expanded={open === e.id}>
                      <TD className="w-6 text-muted">{open === e.id ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}</TD>
                      <TD className="num text-muted">{fmtDateTime(e.entry_time).replace(" UTC", "")}</TD>
                      <TD>
                        <Badge tone={e.entry_type === "SIGNAL" ? "accent" : e.entry_type === "PAPER_TRADE" ? "info" : "purple"}>{titleCase(e.entry_type)}</Badge>
                      </TD>
                      <TD className="font-semibold">
                        {e.symbol}
                        {e.timeframe ? <span className="ml-1 text-[0.66rem] font-normal text-faint">{e.timeframe}</span> : null}
                      </TD>
                      <TD>
                        <DirectionBadge direction={e.direction} />
                      </TD>
                      <TD className="text-xs">{e.strategy ?? "—"}</TD>
                      <TD align="right" className="num">
                        {fmtPrice(e.entry_price, e.symbol)}
                      </TD>
                      <TD align="right" className="num">
                        {fmtPrice(e.exit_price, e.symbol)}
                      </TD>
                      <TD align="right">
                        <Signed value={e.r_multiple}>{fmtR(e.r_multiple)}</Signed>
                      </TD>
                      <TD align="right">
                        <Signed value={e.pnl}>{e.pnl === null ? "—" : fmtMoney(e.pnl, 2, true)}</Signed>
                      </TD>
                      <TD>
                        <RegimeBadge regime={e.regime} />
                      </TD>
                      <TD align="right" className="num">
                        {e.signal_score === null ? "—" : `${e.signal_score.toFixed(0)}/100`}
                      </TD>
                      <TD>
                        <StatusBadge status={e.result} />
                      </TD>
                    </TR>
                    {open === e.id ? (
                      <tr>
                        <td colSpan={13} className="p-0">
                          <EntryDetail e={e} onSaved={() => mutate()} />
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                ))}
              </tbody>
            </Table>
          )}
        </DataBlock>
      </Panel>
      <ManualTradeDialog open={manual} onOpenChange={setManual} onSaved={() => mutate()} />
    </PageContainer>
  );
}
