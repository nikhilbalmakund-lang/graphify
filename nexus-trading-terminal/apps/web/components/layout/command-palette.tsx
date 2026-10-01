"use client";

import { Command } from "cmdk";
import { ArrowRight, BookOpen, Download, FileText, Keyboard, LineChart, Newspaper, PanelRight, Play, Radar, Search, Zap } from "lucide-react";
import { useRouter } from "next/navigation";
import { Dialog as DialogPrimitive } from "radix-ui";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { DirectionBadge, StatusBadge } from "@/components/market/badges";
import { useApi } from "@/hooks/use-api";
import { qs } from "@/lib/api";
import { DEFAULT_SYMBOLS, SYMBOL_NAMES } from "@/lib/constants";
import { downloadFrom } from "@/lib/download";

import { ALL_NAV } from "./nav";

interface SearchResults {
  assets: { symbol: string; name: string; asset_class: string }[];
  signals: { id: string; symbol: string; direction: string; status: string; score: number; created_at: string }[];
  strategies: { name: string; description?: string }[];
  journal: { id: string; symbol: string; direction: string; entry_type: string; result: string; entry_time: string }[];
  news: { id: string; headline: string; source: string; url: string | null }[];
}

const ALIASES: Record<string, string> = {
  XAUUSD: "gold xau",
  BTCUSD: "btc bitcoin crypto",
  ETHUSD: "eth ether ethereum crypto",
  USOIL: "oil wti crude",
  NAS100: "nasdaq ndx tech",
  SPX500: "s&p spx sp500",
  US30: "dow djia",
  EURUSD: "euro fiber",
  GBPUSD: "cable pound sterling",
  USDJPY: "yen jpy",
};

const itemCls =
  "flex cursor-pointer items-center gap-2.5 rounded-sm px-2.5 py-1.5 text-[0.8rem] text-fg data-[selected=true]:bg-elevated data-[selected=true]:text-fg-strong [&_svg]:size-3.5 [&_svg]:text-faint";
const groupCls = "[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-[0.6rem] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.12em] [&_[cmdk-group-heading]]:text-faint";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setV(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return v;
}

export function CommandPalette({ open, onOpenChange, onShowShortcuts, onToggleRight }: { open: boolean; onOpenChange: (v: boolean) => void; onShowShortcuts: () => void; onToggleRight: () => void }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const q = useDebounced(query.trim(), 200);
  const { data: results } = useApi<SearchResults>(open && q.length >= 2 ? `/api/search${qs({ q })}` : null);

  const run = (fn: () => void) => {
    onOpenChange(false);
    setQuery("");
    fn();
  };
  const go = (href: string) => run(() => router.push(href));
  const exportCsv = (path: string, name: string) =>
    run(() => {
      downloadFrom(path, name).then(
        () => toast.success(`Exported ${name}`),
        (e: unknown) => toast.error(e instanceof Error ? e.message : "Export failed"),
      );
    });

  const hasResults = results && (results.signals.length || results.journal.length || results.news.length || results.strategies.length);

  return (
    <DialogPrimitive.Root
      open={open}
      onOpenChange={(v) => {
        onOpenChange(v);
        if (!v) setQuery("");
      }}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[60] bg-black/60" />
        <DialogPrimitive.Content className="fixed left-1/2 top-[10vh] z-[70] w-[min(94vw,640px)] -translate-x-1/2 overflow-hidden rounded-md border border-line-strong bg-panel shadow-2xl focus:outline-none">
          <DialogPrimitive.Title className="sr-only">Command palette</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">Search assets, signals, journal entries and news, or run a command.</DialogPrimitive.Description>
          <Command label="Command palette" loop className="flex flex-col">
            <div className="flex items-center gap-2 border-b border-line px-3">
              <Search className="size-4 shrink-0 text-faint" />
              <Command.Input
                value={query}
                onValueChange={setQuery}
                placeholder="Type a command or search… (try “gold”, “backtest”, “settings”)"
                className="h-11 w-full bg-transparent text-sm text-fg placeholder:text-faint focus:outline-none"
              />
              <kbd className="rounded-xs border border-line px-1 font-mono text-[0.6rem] text-faint">ESC</kbd>
            </div>
            <Command.List className="max-h-[min(60vh,460px)] overflow-y-auto p-1.5">
              <Command.Empty className="px-3 py-8 text-center text-xs text-muted">No matching commands.</Command.Empty>

              {hasResults ? (
                <Command.Group heading="Search results" className={groupCls}>
                  {results.signals.map((s) => (
                    <Command.Item key={s.id} value={`signal ${s.id} ${s.symbol}`} keywords={[q]} onSelect={() => go(`/signals/${s.id}`)} className={itemCls}>
                      <Zap />
                      <span className="font-medium">{s.symbol}</span>
                      <DirectionBadge direction={s.direction} />
                      <StatusBadge status={s.status} />
                      <span className="num ml-auto text-xs text-muted">Score {s.score.toFixed(0)}/100</span>
                    </Command.Item>
                  ))}
                  {results.journal.map((j) => (
                    <Command.Item key={j.id} value={`journal ${j.id} ${j.symbol}`} keywords={[q]} onSelect={() => go(`/journal?symbol=${j.symbol}`)} className={itemCls}>
                      <BookOpen />
                      <span>Journal · {j.symbol}</span>
                      <DirectionBadge direction={j.direction} />
                      <span className="ml-auto text-xs text-muted">{j.result}</span>
                    </Command.Item>
                  ))}
                  {results.strategies.map((s) => (
                    <Command.Item key={s.name} value={`strategy ${s.name}`} keywords={[q]} onSelect={() => go(`/strategy-lab`)} className={itemCls}>
                      <FileText />
                      <span>Strategy · {s.name}</span>
                    </Command.Item>
                  ))}
                  {results.news.map((n) => (
                    <Command.Item key={n.id} value={`news ${n.id}`} keywords={[q]} onSelect={() => go(`/news`)} className={itemCls}>
                      <Newspaper />
                      <span className="truncate">{n.headline}</span>
                      <span className="ml-auto shrink-0 text-xs text-muted">{n.source}</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              ) : null}

              <Command.Group heading="Assets" className={groupCls}>
                {DEFAULT_SYMBOLS.map((s) => (
                  <Command.Item key={s} value={`go to ${SYMBOL_NAMES[s]} ${s}`} keywords={[s, ALIASES[s] ?? ""]} onSelect={() => go(`/chart?symbol=${s}`)} className={itemCls}>
                    <LineChart />
                    <span>
                      Go to {SYMBOL_NAMES[s]} <span className="text-muted">· {s}</span>
                    </span>
                    <ArrowRight className="ml-auto" />
                  </Command.Item>
                ))}
              </Command.Group>

              <Command.Group heading="Actions" className={groupCls}>
                <Command.Item value="open scanner" keywords={["scan", "opportunities"]} onSelect={() => go("/scanner")} className={itemCls}>
                  <Radar /> Open scanner
                </Command.Item>
                <Command.Item value="run backtest" keywords={["test", "strategy"]} onSelect={() => go("/backtesting?new=1")} className={itemCls}>
                  <Play /> Run backtest
                </Command.Item>
                <Command.Item value="open ai analyst" keywords={["chat", "ask", "ai"]} onSelect={() => go("/analyst")} className={itemCls}>
                  <Zap /> Open AI analyst
                </Command.Item>
                <Command.Item value="open settings" keywords={["preferences", "api keys", "config"]} onSelect={() => go("/settings")} className={itemCls}>
                  <FileText /> Open settings
                </Command.Item>
                <Command.Item value="export signals csv" onSelect={() => exportCsv("/api/signals/export.csv", "nexus-signals.csv")} className={itemCls}>
                  <Download /> Export signals CSV
                </Command.Item>
                <Command.Item value="export journal csv" onSelect={() => exportCsv("/api/journal/export.csv", "nexus-journal.csv")} className={itemCls}>
                  <Download /> Export journal CSV
                </Command.Item>
                <Command.Item value="export paper trades csv" onSelect={() => exportCsv("/api/paper-trading/export.csv", "nexus-paper-trades.csv")} className={itemCls}>
                  <Download /> Export paper trades CSV
                </Command.Item>
                <Command.Item value="toggle intelligence panel" onSelect={() => run(onToggleRight)} className={itemCls}>
                  <PanelRight /> Toggle intelligence panel
                </Command.Item>
                <Command.Item value="keyboard shortcuts help" onSelect={() => run(onShowShortcuts)} className={itemCls}>
                  <Keyboard /> Keyboard shortcuts
                </Command.Item>
              </Command.Group>

              <Command.Group heading="Navigate" className={groupCls}>
                {ALL_NAV.map((n) => {
                  const Icon = n.icon;
                  return (
                    <Command.Item key={n.href} value={`page ${n.label}`} keywords={[n.keywords ?? ""]} onSelect={() => go(n.href)} className={itemCls}>
                      <Icon />
                      {n.label}
                      {n.shortcut ? <kbd className="ml-auto rounded-xs border border-line px-1 font-mono text-[0.6rem] text-faint">{n.shortcut}</kbd> : null}
                    </Command.Item>
                  );
                })}
              </Command.Group>
            </Command.List>
          </Command>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
