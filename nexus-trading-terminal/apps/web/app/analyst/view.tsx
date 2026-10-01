"use client";

import type { ChatResponse } from "@nexus/shared-types";
import { Bot, Check, CircleX, Eraser, Loader2, Send, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ProviderLabel } from "@/components/ai/briefing-panel";
import { Callout } from "@/components/common/disclaimer";
import { ExplainedSections } from "@/components/common/explained";
import { PageHeader } from "@/components/common/page-header";
import { ModeBadge } from "@/components/market/badges";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { errorMessage, post } from "@/lib/api";
import { cn } from "@/lib/utils";

import { componentStatus, useSystemStatus } from "@/components/layout/use-system";

type Msg = { role: "user"; content: string } | { role: "assistant"; content: string; response?: ChatResponse; error?: string };

const TOOL_LABEL: Record<string, string> = {
  get_market_data: "Retrieved market data",
  get_indicators: "Calculated indicators",
  get_structure: "Analysed market structure",
  get_news: "Retrieved news",
  get_calendar: "Checked economic calendar",
  get_historical_setups: "Compared historical setups",
  get_portfolio: "Read paper portfolio",
  get_risk_status: "Read risk status",
  calculate_signal: "Ran the signal engine",
  calculate_position_size: "Calculated position size",
};

const SUGGESTIONS = [
  "What is happening with Gold?",
  "Why is EURUSD moving?",
  "What are the strongest current trends?",
  "Explain the current XAUUSD 15m signal",
  "Compare current Gold conditions with historical setups",
  "What is my portfolio and risk status?",
];

function ToolTrace({ trace }: { trace: ChatResponse["tool_trace"] }) {
  if (!trace.length) return null;
  return (
    <ol className="flex flex-col gap-0.5 rounded-sm border border-line bg-panel-2/60 px-3 py-2 text-xs" aria-label="Tools used">
      {trace.map((t, i) => {
        const sym = typeof t.arguments.symbol === "string" ? ` · ${t.arguments.symbol}` : "";
        const tf = typeof t.arguments.timeframe === "string" ? ` ${t.arguments.timeframe}` : "";
        return (
          <li key={i} className="flex items-center gap-2">
            {t.ok ? <Check className="size-3 text-up" /> : <CircleX className="size-3 text-down" />}
            <span className="text-fg">
              {TOOL_LABEL[t.name] ?? t.name}
              <span className="text-muted">
                {sym}
                {tf}
              </span>
            </span>
            <span className="truncate text-faint">{t.summary}</span>
            <span className="num ml-auto shrink-0 text-faint">{t.duration_ms.toFixed(0)}ms</span>
          </li>
        );
      })}
    </ol>
  );
}

function AssistantMessage({ m }: { m: Extract<Msg, { role: "assistant" }> }) {
  const r = m.response;
  if (m.error) return <Callout tone="down">{m.error}</Callout>;
  if (!r) return null;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <ProviderLabel isAi={r.is_ai} provider={r.provider} model={r.model} />
        {r.is_demo_data ? <ModeBadge mode="DEMO" /> : null}
      </div>
      <ToolTrace trace={r.tool_trace} />
      <p className="text-sm leading-relaxed text-fg-strong">{r.answer.summary}</p>
      <ExplainedSections value={r.answer} interpretationLabel={r.is_ai ? "AI interpretation" : "Interpretation"} />
      {r.warnings.length ? (
        <Callout tone="warn" title="Validation warnings">
          {r.warnings.join(" · ")}
        </Callout>
      ) : null}
    </div>
  );
}

export function AnalystView() {
  const [messages, setMessages] = useLocalStorage<Msg[]>("nexus.analyst.chat", []);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const { data: status } = useSystemStatus();
  const aiOn = ["Claude", "Gemini"].some((n) => ["CONNECTED", "CONFIGURED_UNVERIFIED", "OK"].includes(componentStatus(status, n)));

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, busy]);

  const ask = async (q: string) => {
    const question = q.trim();
    if (!question || busy) return;
    const history = messages.slice(-10).map((m) => ({ role: m.role, content: m.role === "assistant" ? (m.response?.answer.summary ?? m.error ?? "") : m.content }));
    setMessages((prev) => [...prev, { role: "user" as const, content: question }].slice(-40));
    setInput("");
    setBusy(true);
    try {
      const res = await post<ChatResponse>("/api/ai/chat", { question, history });
      setMessages((prev) => [...prev, { role: "assistant" as const, content: res.answer.summary, response: res }].slice(-40));
    } catch (e) {
      setMessages((prev) => [...prev, { role: "assistant" as const, content: "", error: errorMessage(e) }].slice(-40));
    } finally {
      setBusy(false);
    }
  };

  const lastQ = [...messages].reverse().find((m) => m.role === "user")?.content ?? "";

  return (
    <div className="mx-auto flex h-full w-full max-w-5xl flex-col gap-3 p-3 sm:p-4">
      <PageHeader
        title="AI Analyst"
        description="Ask about markets, signals, history or your paper portfolio. The analyst calls read-only internal tools for data instead of guessing, and every answer separates facts, calculations, interpretation and uncertainty."
        actions={
          messages.length ? (
            <Button size="sm" variant="ghost" onClick={() => setMessages([])}>
              <Eraser /> Clear
            </Button>
          ) : null
        }
      />
      {!aiOn ? (
        <Callout tone="info" title="No AI provider configured">
          Answers come from a rule-based router over the same internal tools and are labelled non-AI. Add a Claude or Gemini key in Settings for free-form analysis.
        </Callout>
      ) : null}
      <div className="flex min-h-[320px] flex-1 flex-col gap-4 overflow-y-auto rounded-md border border-line bg-panel/60 p-3 sm:p-4" aria-live="polite">
        {!messages.length ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 py-8 text-center">
            <Bot className="size-8 text-accent" />
            <p className="text-sm text-muted">Try one of these:</p>
            <div className="flex max-w-2xl flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <Button key={s} size="sm" variant="outline" onClick={() => ask(s)}>
                  {s}
                </Button>
              ))}
            </div>
          </div>
        ) : null}
        {messages.map((m, i) => (
          <div key={i} className={cn("flex gap-3", m.role === "user" && "justify-end")}>
            {m.role === "assistant" ? (
              <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-sm border border-accent-2/40 bg-accent-2/10 text-accent-2">
                <Bot className="size-3.5" />
              </span>
            ) : null}
            <div className={cn("min-w-0", m.role === "user" ? "max-w-[80%] rounded-md bg-elevated px-3 py-2 text-sm text-fg-strong" : "flex-1")}>
              {m.role === "user" ? m.content : <AssistantMessage m={m} />}
            </div>
            {m.role === "user" ? (
              <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-sm border border-line bg-panel-2 text-muted">
                <User className="size-3.5" />
              </span>
            ) : null}
          </div>
        ))}
        {busy ? (
          <div className="flex items-start gap-3">
            <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-sm border border-accent-2/40 bg-accent-2/10 text-accent-2">
              <Loader2 className="size-3.5 animate-spin" />
            </span>
            <div className="flex flex-col gap-1 text-xs text-muted">
              <span className="text-fg">Analyzing{lastQ ? ` “${lastQ.slice(0, 80)}”` : ""}…</span>
              <span>Calling internal tools for market data, indicators, structure, calendar, news and history.</span>
            </div>
          </div>
        ) : null}
        <div ref={endRef} />
      </div>
      <form
        className="flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void ask(input);
        }}
      >
        <Textarea
          aria-label="Ask the AI analyst"
          value={input}
          maxLength={2000}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void ask(input);
            }
          }}
          placeholder="Ask about an asset, a signal, history or your portfolio… (Enter to send, Shift+Enter for a new line)"
          className="min-h-11 flex-1 resize-none"
          rows={2}
        />
        <Button type="submit" variant="primary" size="lg" disabled={busy || !input.trim()} aria-label="Send">
          <Send />
        </Button>
      </form>
      <p className="text-[0.66rem] text-faint">The analyst cannot place trades, change settings or bypass the risk engine. API keys are never sent to the browser.</p>
    </div>
  );
}
