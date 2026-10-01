"use client";

import type { Order, PaperOverview, Position, RiskDecision } from "@nexus/shared-types";
import { Gauge, OctagonAlert, Plus, RotateCcw, Send, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { ConfirmDialog } from "@/components/common/confirm";
import { Callout } from "@/components/common/disclaimer";
import { ExportButton } from "@/components/common/export-button";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { Stat } from "@/components/common/stat";
import { DataBlock, EmptyState } from "@/components/common/states";
import { ModeBadge, StatusBadge } from "@/components/market/badges";
import { Segmented, SymbolSelect } from "@/components/market/pickers";
import { FlashPrice, Signed } from "@/components/market/price";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApi } from "@/hooks/use-api";
import { useLiveQuote } from "@/hooks/use-live";
import { ApiError, del, errorMessage, post, qs } from "@/lib/api";
import { fmtDateTime, fmtMoney, fmtNum, fmtPrice, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

type Side = "BUY" | "SELL";
type OType = "MARKET" | "LIMIT" | "STOP";

function OrderTicket({ onDone }: { onDone: () => void }) {
  const [symbol, setSymbol] = useState("XAUUSD");
  const [side, setSide] = useState<Side>("BUY");
  const [type, setType] = useState<OType>("MARKET");
  const [lots, setLots] = useState("0.10");
  const [price, setPrice] = useState("");
  const [stop, setStop] = useState("");
  const [tps, setTps] = useState<{ price: string; fraction: string }[]>([{ price: "", fraction: "1" }]);
  const [busy, setBusy] = useState(false);
  const [reject, setReject] = useState<{ message: string; reasons: string[] } | null>(null);
  const q = useLiveQuote(symbol);
  const ref = type === "MARKET" ? (side === "BUY" ? q?.ask : q?.bid) : price ? Number(price) : undefined;
  const risk = ref && stop ? Math.abs(ref - Number(stop)) : null;
  const tp1 = tps[0]?.price ? Number(tps[0].price) : null;
  const rr = risk && tp1 ? Math.abs(tp1 - (ref ?? 0)) / risk : null;

  const submit = async () => {
    setBusy(true);
    setReject(null);
    try {
      const body = {
        symbol,
        side,
        type,
        lots: Number(lots),
        price: type === "MARKET" ? null : Number(price),
        stop_loss: stop ? Number(stop) : null,
        take_profits: tps.filter((t) => t.price).map((t, i) => ({ price: Number(t.price), fraction: Number(t.fraction) || 1, label: `TP${i + 1}` })),
        source: "manual",
      };
      const res = await post<{ order: Order; risk: RiskDecision }>("/api/paper-trading/orders", body);
      if (res.order.status === "REJECTED") toast.error(`Rejected: ${res.order.reject_reason}`);
      else toast.success(`SIMULATED ${type} ${side} ${res.order.lots} ${symbol} · ${titleCase(res.order.status)}`, { description: "Paper trading only - no real order was sent." });
      onDone();
    } catch (e) {
      const reasons = e instanceof ApiError && Array.isArray(e.details?.reasons) ? (e.details?.reasons as string[]) : [];
      setReject({ message: errorMessage(e), reasons });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel>
      <PanelHeader title="Order ticket" icon={<Send />} subtitle="SIMULATED · every order passes the risk engine" />
      <PanelBody className="flex flex-col gap-3">
        <div className="flex items-end gap-2">
          <Field label="Asset" htmlFor="ot-symbol" className="flex-1">
            <SymbolSelect id="ot-symbol" value={symbol} onChange={setSymbol} className="w-full" />
          </Field>
          <div className="pb-1.5 text-right text-xs">
            <p className="label">Bid / Ask</p>
            <p className="num">
              <FlashPrice value={q?.bid} symbol={symbol} /> / <FlashPrice value={q?.ask} symbol={symbol} />
            </p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-1">
          {(["BUY", "SELL"] as const).map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={side === s}
              onClick={() => setSide(s)}
              className={cn(
                "h-9 cursor-pointer rounded-sm border text-sm font-bold tracking-wider transition-colors",
                side === s ? (s === "BUY" ? "border-up bg-up/90 text-bg" : "border-down bg-down/90 text-white") : "border-line bg-panel-2 text-muted hover:text-fg",
              )}
            >
              {s}
            </button>
          ))}
        </div>
        <Segmented
          label="Order type"
          value={type}
          onChange={setType}
          options={[
            { value: "MARKET", label: "Market" },
            { value: "LIMIT", label: "Limit" },
            { value: "STOP", label: "Stop" },
          ]}
          className="self-start"
        />
        <div className="grid grid-cols-2 gap-2">
          <Field label="Lots" htmlFor="ot-lots">
            <Input id="ot-lots" type="number" min={0.01} step={0.01} value={lots} onChange={(e) => setLots(e.target.value)} />
          </Field>
          <Field label={type === "MARKET" ? "Price (market)" : `${titleCase(type)} price`} htmlFor="ot-price">
            <Input id="ot-price" type="number" step="any" disabled={type === "MARKET"} placeholder={type === "MARKET" ? fmtPrice(ref, symbol) : "required"} value={price} onChange={(e) => setPrice(e.target.value)} />
          </Field>
          <Field label="Stop loss" htmlFor="ot-stop" hint="Required by risk policy">
            <Input id="ot-stop" type="number" step="any" value={stop} onChange={(e) => setStop(e.target.value)} />
          </Field>
          <div className="flex flex-col justify-end gap-0.5 pb-5 text-xs">
            <span className="text-muted">
              Risk distance <span className="num text-fg">{risk ? fmtPrice(risk, symbol) : "—"}</span>
            </span>
            <span className="text-muted">
              R:R to TP1 <span className="num text-fg">{rr ? rr.toFixed(2) : "—"}</span>
            </span>
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <p className="label">Take profits</p>
          {tps.map((t, i) => (
            <div key={i} className="grid grid-cols-[1fr_88px_auto] gap-1.5">
              <Input aria-label={`TP${i + 1} price`} type="number" step="any" placeholder={`TP${i + 1} price`} value={t.price} onChange={(e) => setTps(tps.map((x, j) => (j === i ? { ...x, price: e.target.value } : x)))} />
              <Input aria-label={`TP${i + 1} fraction`} type="number" min={0.05} max={1} step={0.05} value={t.fraction} onChange={(e) => setTps(tps.map((x, j) => (j === i ? { ...x, fraction: e.target.value } : x)))} />
              <Button variant="ghost" size="icon" aria-label={`Remove TP${i + 1}`} onClick={() => setTps(tps.filter((_, j) => j !== i))} disabled={tps.length === 1}>
                <X />
              </Button>
            </div>
          ))}
          {tps.length < 3 ? (
            <Button size="xs" variant="ghost" className="self-start" onClick={() => setTps([...tps, { price: "", fraction: "0.5" }])}>
              <Plus /> Add target
            </Button>
          ) : null}
        </div>
        {reject ? (
          <Callout tone="down" title={reject.message}>
            {reject.reasons.length ? (
              <ul className="list-disc pl-4">
                {reject.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            ) : null}
          </Callout>
        ) : null}
        <Button variant={side === "BUY" ? "success" : "danger"} size="lg" onClick={submit} disabled={busy || !Number(lots) || (type !== "MARKET" && !price)}>
          {busy ? "Checking risk…" : `Place SIMULATED ${type.toLowerCase()} ${side.toLowerCase()}`}
        </Button>
      </PanelBody>
    </Panel>
  );
}

function PositionsTable({ positions, onChanged }: { positions: Position[]; onChanged: () => void }) {
  const close = async (p: Position, lots?: number) => {
    try {
      await post(`/api/paper-trading/positions/${p.id}/close${qs({ lots })}`);
      toast.success(`Closed ${lots ? `${lots} lots of ` : ""}${p.symbol} (simulated)`);
      onChanged();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  if (!positions.length) return <EmptyState title="No open positions" description="Place an order or send an active signal to the paper broker." />;
  return (
    <Table>
      <THead>
        <tr>
          <TH>Asset</TH>
          <TH>Side</TH>
          <TH align="right">Lots</TH>
          <TH align="right">Entry</TH>
          <TH align="right">Current</TH>
          <TH align="right">Stop</TH>
          <TH>Targets</TH>
          <TH align="right">Unrealised</TH>
          <TH>Opened</TH>
          <TH>Source</TH>
          <TH />
        </tr>
      </THead>
      <tbody>
        {positions.map((p) => (
          <TR key={p.id}>
            <TD className="font-semibold">{p.symbol}</TD>
            <TD className={p.direction > 0 ? "font-semibold text-up" : "font-semibold text-down"}>{p.direction > 0 ? "LONG" : "SHORT"}</TD>
            <TD align="right" className="num">
              {fmtNum(p.lots, 2)}
              {p.lots !== p.initial_lots ? <span className="text-faint"> /{fmtNum(p.initial_lots, 2)}</span> : null}
            </TD>
            <TD align="right" className="num">
              {fmtPrice(p.entry_price, p.symbol)}
            </TD>
            <TD align="right">
              <FlashPrice value={p.current_price} symbol={p.symbol} />
            </TD>
            <TD align="right" className="num text-down">
              {fmtPrice(p.stop_loss, p.symbol)}
            </TD>
            <TD className="num text-xs text-up">{p.take_profits.map((t) => fmtPrice(t.price, p.symbol)).join(" · ") || "—"}</TD>
            <TD align="right">
              <Signed value={p.unrealized_pnl}>{fmtMoney(p.unrealized_pnl, 2, true)}</Signed>
            </TD>
            <TD className="num text-muted">{fmtDateTime(p.opened_at)}</TD>
            <TD className="text-xs">
              {p.signal_id ? (
                <Link href={`/signals/${p.signal_id}`} className="text-accent hover:underline">
                  signal
                </Link>
              ) : (
                titleCase(p.source)
              )}
            </TD>
            <TD>
              <div className="flex gap-1">
                {p.lots >= 0.02 ? (
                  <Button size="xs" variant="ghost" onClick={() => close(p, Math.round((p.lots / 2) * 100) / 100)}>
                    Close ½
                  </Button>
                ) : null}
                <Button size="xs" variant="outline" onClick={() => close(p)}>
                  Close
                </Button>
              </div>
            </TD>
          </TR>
        ))}
      </tbody>
    </Table>
  );
}

export function PaperTradingView() {
  const { data, error, isLoading, mutate } = useApi<PaperOverview>("/api/paper-trading", 5000);
  const { mutate: globalMutate } = useSWRConfig();
  const [confirmKill, setConfirmKill] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const refresh = () => {
    void mutate();
    void globalMutate((k) => typeof k === "string" && (k.startsWith("/api/risk") || k.startsWith("/api/portfolio") || k.startsWith("/api/journal")));
  };
  const cancel = async (o: Order) => {
    try {
      await del(`/api/paper-trading/orders/${o.id}`);
      toast.success("Order cancelled");
      refresh();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  const setKill = async (active: boolean) => {
    await post("/api/paper-trading/kill-switch", { active });
    refresh();
  };
  const killed = data?.account.kill_switch;
  const pending = data?.orders.filter((o) => o.status === "PENDING") ?? [];

  return (
    <PageContainer>
      <div className="flex items-center justify-center gap-2 rounded-sm border border-info/40 bg-info/10 px-3 py-2 text-center text-sm font-bold tracking-[0.2em] text-info" role="status">
        <Gauge className="size-4" /> PAPER TRADING · SIMULATED · NO REAL MONEY
      </div>
      <PageHeader
        title="Paper Trading"
        description="A virtual broker with realistic fills (spread, slippage, gaps, stop-first resolution). Live execution is disabled; nothing here reaches a real broker."
        badges={
          <>
            <ModeBadge mode="PAPER" />
            {data?.is_demo_prices ? <ModeBadge mode="DEMO" title="Paper fills use DEMO prices" /> : null}
          </>
        }
        actions={
          <>
            <ExportButton path="/api/paper-trading/export.csv" filename="nexus-paper-trades.csv" size="sm" variant="outline" />
            <Button size="sm" variant="ghost" onClick={() => setConfirmReset(true)}>
              <RotateCcw /> Reset account
            </Button>
            {killed ? (
              <Button size="sm" variant="outline" onClick={() => setKill(false).then(() => toast.success("Kill switch released"))}>
                Release kill switch
              </Button>
            ) : (
              <Button size="sm" variant="danger" onClick={() => setConfirmKill(true)}>
                <OctagonAlert /> Emergency kill switch
              </Button>
            )}
          </>
        }
      />
      {killed ? (
        <Callout tone="down" title="Emergency kill switch is ACTIVE">
          All pending paper orders were cancelled and new orders are blocked until you release it. Open positions remain and can be closed manually.
        </Callout>
      ) : null}

      <DataBlock data={data} error={error} isLoading={isLoading} onRetry={() => mutate()} rows={6}>
        {(d) => (
          <>
            <Panel>
              <PanelBody className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
                <Stat label="Balance" value={fmtMoney(d.account.balance)} size="lg" />
                <Stat label="Equity" value={fmtMoney(d.account.equity)} size="lg" />
                <Stat label="Unrealised P&L" value={<Signed value={d.account.unrealized_pnl}>{fmtMoney(d.account.unrealized_pnl, 2, true)}</Signed>} size="lg" />
                <Stat label="Margin used" value={fmtMoney(d.account.margin_used)} />
                <Stat label="Free margin" value={fmtMoney(d.account.free_margin)} />
                <Stat label="Risk engine" value={<Badge tone={d.risk.state === "NORMAL" ? "up" : d.risk.state === "HALTED" ? "solidDown" : "warn"}>{d.risk.state}</Badge>} sub={`${d.risk.open_positions} open · max lev ${d.account.max_leverage}×`} />
              </PanelBody>
            </Panel>
            <div className="grid gap-3 xl:grid-cols-[360px_1fr]">
              <OrderTicket onDone={refresh} />
              <Panel>
                <Tabs defaultValue="positions">
                  <div className="px-3 pt-1">
                    <TabsList>
                      <TabsTrigger value="positions">Open positions ({d.positions.length})</TabsTrigger>
                      <TabsTrigger value="orders">Orders ({pending.length} pending)</TabsTrigger>
                      <TabsTrigger value="history">History ({d.closed_positions.length})</TabsTrigger>
                      <TabsTrigger value="fills">Fills ({d.fills.length})</TabsTrigger>
                    </TabsList>
                  </div>
                  <TabsContent value="positions" className="pt-0">
                    <PositionsTable positions={d.positions} onChanged={refresh} />
                  </TabsContent>
                  <TabsContent value="orders" className="pt-0">
                    {d.orders.length ? (
                      <Table>
                        <THead>
                          <tr>
                            <TH>Created</TH>
                            <TH>Asset</TH>
                            <TH>Side</TH>
                            <TH>Type</TH>
                            <TH align="right">Lots</TH>
                            <TH align="right">Price</TH>
                            <TH align="right">Fill</TH>
                            <TH>Status</TH>
                            <TH />
                          </tr>
                        </THead>
                        <tbody>
                          {d.orders.map((o) => (
                            <TR key={o.id}>
                              <TD className="num text-muted">{fmtDateTime(o.created_at)}</TD>
                              <TD className="font-semibold">{o.symbol}</TD>
                              <TD className={o.side === "BUY" ? "text-up" : "text-down"}>{o.side}</TD>
                              <TD className="text-xs">{o.type}</TD>
                              <TD align="right" className="num">
                                {fmtNum(o.lots, 2)}
                              </TD>
                              <TD align="right" className="num">
                                {fmtPrice(o.price, o.symbol)}
                              </TD>
                              <TD align="right" className="num">
                                {fmtPrice(o.fill_price, o.symbol)}
                              </TD>
                              <TD>
                                <StatusBadge status={o.status} />
                                {o.reject_reason ? <span className="ml-1 text-[0.66rem] text-down">{o.reject_reason}</span> : null}
                              </TD>
                              <TD>
                                {o.status === "PENDING" ? (
                                  <Button size="xs" variant="ghost" onClick={() => cancel(o)}>
                                    <Trash2 /> Cancel
                                  </Button>
                                ) : null}
                              </TD>
                            </TR>
                          ))}
                        </tbody>
                      </Table>
                    ) : (
                      <EmptyState title="No orders yet" />
                    )}
                  </TabsContent>
                  <TabsContent value="history" className="pt-0">
                    {d.closed_positions.length ? (
                      <Table>
                        <THead>
                          <tr>
                            <TH>Closed</TH>
                            <TH>Asset</TH>
                            <TH>Side</TH>
                            <TH align="right">Lots</TH>
                            <TH align="right">Entry</TH>
                            <TH align="right">Exit</TH>
                            <TH>Reason</TH>
                            <TH align="right">Fees</TH>
                            <TH align="right">Realised</TH>
                          </tr>
                        </THead>
                        <tbody>
                          {d.closed_positions.map((p) => (
                            <TR key={p.id}>
                              <TD className="num text-muted">{fmtDateTime(p.closed_at)}</TD>
                              <TD className="font-semibold">{p.symbol}</TD>
                              <TD className={p.direction > 0 ? "text-up" : "text-down"}>{p.direction > 0 ? "LONG" : "SHORT"}</TD>
                              <TD align="right" className="num">
                                {fmtNum(p.initial_lots, 2)}
                              </TD>
                              <TD align="right" className="num">
                                {fmtPrice(p.entry_price, p.symbol)}
                              </TD>
                              <TD align="right" className="num">
                                {fmtPrice(p.exit_price, p.symbol)}
                              </TD>
                              <TD className="text-xs">{titleCase(p.exit_reason)}</TD>
                              <TD align="right" className="num text-muted">
                                {fmtMoney(p.fees, 2)}
                              </TD>
                              <TD align="right">
                                <Signed value={p.realized_pnl}>{fmtMoney(p.realized_pnl, 2, true)}</Signed>
                              </TD>
                            </TR>
                          ))}
                        </tbody>
                      </Table>
                    ) : (
                      <EmptyState title="No closed trades yet" />
                    )}
                  </TabsContent>
                  <TabsContent value="fills" className="pt-0">
                    {d.fills.length ? (
                      <Table>
                        <THead>
                          <tr>
                            <TH>Time</TH>
                            <TH>Asset</TH>
                            <TH>Side</TH>
                            <TH align="right">Lots</TH>
                            <TH align="right">Price</TH>
                            <TH align="right">Slippage</TH>
                            <TH align="right">Fee</TH>
                            <TH>Reason</TH>
                            <TH align="right">P&L</TH>
                          </tr>
                        </THead>
                        <tbody>
                          {d.fills.map((f) => (
                            <TR key={f.id}>
                              <TD className="num text-muted">{fmtDateTime(f.timestamp)}</TD>
                              <TD className="font-semibold">{f.symbol}</TD>
                              <TD className={f.side === "BUY" ? "text-up" : "text-down"}>{f.side}</TD>
                              <TD align="right" className="num">
                                {fmtNum(f.lots, 2)}
                              </TD>
                              <TD align="right" className="num">
                                {fmtPrice(f.price, f.symbol)}
                              </TD>
                              <TD align="right" className="num text-muted">
                                {fmtPrice(f.slippage, f.symbol)}
                              </TD>
                              <TD align="right" className="num text-muted">
                                {fmtMoney(f.fee, 2)}
                              </TD>
                              <TD className="text-xs">{titleCase(f.reason)}</TD>
                              <TD align="right">
                                <Signed value={f.realized_pnl}>{f.realized_pnl ? fmtMoney(f.realized_pnl, 2, true) : "—"}</Signed>
                              </TD>
                            </TR>
                          ))}
                        </tbody>
                      </Table>
                    ) : (
                      <EmptyState title="No fills yet" />
                    )}
                  </TabsContent>
                </Tabs>
              </Panel>
            </div>
          </>
        )}
      </DataBlock>

      <ConfirmDialog
        open={confirmKill}
        onOpenChange={setConfirmKill}
        title="Activate emergency kill switch?"
        description="Cancels every pending paper order and blocks new orders (manual and signal-driven) until released."
        confirmLabel="Activate kill switch"
        onConfirm={async () => {
          await setKill(true);
        }}
      />
      <ConfirmDialog
        open={confirmReset}
        onOpenChange={setConfirmReset}
        title="Reset the paper account?"
        description="Deletes all simulated positions, orders and fills and restores the starting balance from Settings. Journal entries are kept."
        confirmLabel="Reset account"
        onConfirm={async () => {
          await post("/api/paper-trading/reset");
          toast.success("Paper account reset");
          refresh();
        }}
      />
    </PageContainer>
  );
}
