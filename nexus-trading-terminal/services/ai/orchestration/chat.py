"""AI analyst chat.

With Claude or Gemini configured, the model drives a tool loop over the
read-only tools and returns an answer split into facts / calculations /
interpretation / uncertainty. Without a provider, a deterministic intent
router calls the same tools and assembles the facts and calculations itself,
with the interpretation section explicitly stating that no AI was used.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from ai.orchestration.tools import TOOL_NAMES, TOOLS
from ai.providers.base import AIProvider, AIProviderError, AIUsage, ToolExecutor, ToolTrace
from ai.providers.demo import LABEL
from ai.schemas.outputs import ChatAnswer

MAX_QUESTION = 2000


class ChatTurn(BaseModel):
    role: str  # user | assistant
    content: str


class ChatResponse(BaseModel):
    answer: ChatAnswer
    tool_trace: list[ToolTrace]
    provider: str
    model: str
    is_ai: bool
    usage: AIUsage | None = None
    warnings: list[str] = Field(default_factory=list)


class AIChatAgent:
    def __init__(
        self,
        providers: list[AIProvider],
        executor: ToolExecutor,
        resolve_symbol: Callable[[str], str | None],
        default_timeframe: str = "1H",
    ):
        self.providers = [p for p in providers if p.configured and not p.is_demo]
        self.executor = executor
        self.resolve_symbol = resolve_symbol
        self.default_tf = default_timeframe

    async def ask(self, question: str, history: list[ChatTurn] | None = None) -> ChatResponse:
        question = question.strip()[:MAX_QUESTION]
        warnings: list[str] = []
        for provider in self.providers:
            msgs = [{"role": t.role, "content": t.content} for t in (history or [])[-8:]]
            msgs.append({"role": "user", "content": question})
            try:
                res, trace = await provider.chat("analyst_chat", msgs, TOOLS, self._guarded, ChatAnswer)
            except AIProviderError as exc:
                warnings.append(f"{provider.label}: {exc.message}")
                continue
            return ChatResponse(
                answer=ChatAnswer.model_validate(res.data),
                tool_trace=trace,
                provider=provider.name,
                model=res.model,
                is_ai=True,
                usage=res.usage,
                warnings=warnings,
            )
        resp = await self._rule_based(question)
        resp.warnings = warnings + resp.warnings
        return resp

    async def _guarded(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name not in TOOL_NAMES:
            return {"error": f"Unknown or forbidden tool '{name}'", "summary": "Tool not available"}
        return await self.executor(name, args)

    # ------------------------------------------------------- rule-based
    def _symbols(self, q: str) -> list[str]:
        found: list[str] = []
        for token in re.findall(r"[A-Za-z0-9&/]+", q):
            s = self.resolve_symbol(token)
            if s and s not in found:
                found.append(s)
        return found

    def _timeframe(self, q: str) -> str:
        m = re.search(r"\b(1m|5m|15m|30m|1h|4h|1d)\b", q, re.I)
        if not m:
            return self.default_tf
        v = m.group(1)
        return v.upper() if v.lower().endswith(("h", "d")) else v.lower()

    async def _call(self, name: str, args: dict[str, Any], trace: list[ToolTrace]) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            out = await self._guarded(name, args)
            ok = "error" not in out
        except Exception as exc:
            out, ok = {"error": f"{type(exc).__name__}", "summary": "Tool failed"}, False
        trace.append(
            ToolTrace(
                name=name,
                arguments=args,
                ok=ok,
                summary=str(out.get("summary", "")),
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
        )
        return out

    async def _rule_based(self, q: str) -> ChatResponse:
        ql = q.lower()
        syms = self._symbols(q)
        tf = self._timeframe(q)
        trace: list[ToolTrace] = []
        facts: list[str] = []
        calcs: list[str] = []
        unc: list[str] = []
        plan: list[tuple[str, dict[str, Any]]] = []
        if any(w in ql for w in ("portfolio", "position", "pnl", "p&l", "account")):
            plan.append(("get_portfolio", {}))
        if "risk" in ql and not syms:
            plan.append(("get_risk_status", {}))
        if (
            any(w in ql for w in ("strongest", "trends", "overview", "market", "what is happening"))
            and not syms
        ):
            for s in ("XAUUSD", "EURUSD", "BTCUSD", "NAS100", "SPX500", "USOIL"):
                plan.append(("get_structure", {"symbol": s, "timeframe": tf}))
        for s in syms[:3]:
            plan.append(("get_market_data", {"symbol": s}))
            plan.append(("get_indicators", {"symbol": s, "timeframe": tf}))
            plan.append(("get_structure", {"symbol": s, "timeframe": tf}))
            if any(w in ql for w in ("signal", "setup", "trade", "explain")):
                plan.append(("calculate_signal", {"symbol": s, "timeframe": tf}))
            if any(w in ql for w in ("historical", "history", "similar", "last", "compare")):
                plan.append(("get_historical_setups", {"symbol": s, "timeframe": tf, "k": 50}))
            plan.append(("get_news", {"symbol": s, "limit": 5}))
        if any(w in ql for w in ("calendar", "event", "cpi", "nfp", "fomc", "why")) or syms:
            plan.append(("get_calendar", {"hours_ahead": 48}))
        if not plan:
            plan = [("get_risk_status", {}), ("get_calendar", {"hours_ahead": 24})]
            unc.append(
                "Question not recognised by the rule-based router; showing general status. Configure Claude or Gemini for free-form analysis."
            )
        for name, args in plan:
            out = await self._call(name, args, trace)
            if "error" in out:
                unc.append(f"{name} failed: {out['error']}")
                continue
            facts += out.get("facts", [])[:6]
            calcs += out.get("calculations", [])[:6]
        summary = (
            f"Rule-based answer for {', '.join(syms)}" if syms else "Rule-based answer"
        ) + " assembled from internal tools."
        unc += [
            "No AI provider is configured, so no interpretation is offered",
            "Scores are rules-based quality measures, not probabilities",
        ]
        answer = ChatAnswer(
            summary=summary,
            facts=facts or ["No data returned"],
            calculations=calcs or ["None"],
            interpretation=[LABEL],
            uncertainty=unc,
        )
        return ChatResponse(
            answer=answer, tool_trace=trace, provider="rule-based", model="rule-based-v1", is_ai=False
        )
