"""Rule-based DEMO fallback used when no AI provider is configured.

This is NOT artificial intelligence and never pretends to be. It produces
deterministic summaries strictly from the structured input (briefings,
explanations, research scaffolds and headline tone), each labelled
"rule-based - no AI model was called". It refuses tasks that genuinely need
a model (independent signal analysis, critique, image analysis), which are
reported as NOT CONFIGURED instead of being faked.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ai.orchestration.router import ModelRouter
from ai.prompts.registry import PromptTemplate
from ai.providers.base import (
    AIProvider,
    AIProviderError,
    AIStatus,
    ImageInput,
    ProviderHealthInfo,
    ToolExecutor,
    ToolSpec,
    ToolTrace,
)

LABEL = "Rule-based summary - no AI model was called (DEMO fallback)"
UNSUPPORTED = {"signal_analysis", "critic", "chart_analysis"}


class DemoRuleBasedProvider(AIProvider):
    name = "rule-based"
    label = "Rule-based demo fallback"
    is_demo = True

    def __init__(self, router: ModelRouter | None = None):
        super().__init__(
            router or ModelRouter(models={"rule-based": {"fast": "rule-based-v1", "strong": "rule-based-v1"}})
        )

    @property
    def configured(self) -> bool:
        return True

    async def validate(self) -> ProviderHealthInfo:
        return ProviderHealthInfo(provider=self.name, status=AIStatus.DEMO, detail=LABEL)

    def settings_for(self, prompt: PromptTemplate) -> dict[str, Any]:
        return {"deterministic": True}

    async def _generate(
        self,
        prompt: PromptTemplate,
        model: str,
        user_text: str,
        schema: type[BaseModel],
        images: list[ImageInput] | None,
    ) -> tuple[str, int | None, int | None, str]:
        raise AIProviderError("AI_PROVIDER_UNAVAILABLE", "Use the typed rule-based builders", self.name)

    async def _tool_loop(
        self,
        prompt: PromptTemplate,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        executor: ToolExecutor,
        final_schema: type[BaseModel],
        max_turns: int,
    ) -> tuple[str, list[ToolTrace], int | None, int | None, str]:
        raise AIProviderError("AI_PROVIDER_UNAVAILABLE", "No AI provider configured for tool use", self.name)

    async def generate(
        self,
        prompt_name: str,
        payload: dict[str, Any],
        schema: type[BaseModel],
        images: list[ImageInput] | None = None,
    ):  # type: ignore[override]
        from ai.prompts.registry import get_prompt
        from ai.providers.base import AIResult, AIUsage

        prompt = get_prompt(prompt_name)
        if prompt.task in UNSUPPORTED:
            raise AIProviderError(
                "AI_PROVIDER_UNAVAILABLE",
                f"{prompt.task} requires Claude or Gemini; no AI provider is configured",
                self.name,
            )
        builder = {
            "briefing": briefing,
            "research": research,
            "news_sentiment": news_sentiment,
            "explain": explain,
        }[prompt.task]
        data = schema.model_validate(builder(payload)).model_dump(mode="json")
        usage = AIUsage(
            provider=self.name,
            model="rule-based-v1",
            task=prompt.task,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
        )
        return AIResult(
            provider=self.name,
            model="rule-based-v1",
            is_demo=True,
            data=data,
            usage=usage,
            settings=self.settings_for(prompt),
            prompt=prompt.meta(),
        )


def briefing(p: dict[str, Any]) -> dict[str, Any]:
    assets = p.get("assets", [])
    events = p.get("events", [])
    demo = " [DEMO data]" if p.get("is_demo") else ""
    ranked = sorted(assets, key=lambda a: abs(a.get("trend_score") or 0), reverse=True)
    strongest = [
        f"{a['symbol']}: {a.get('trend', 'NEUTRAL').lower()} (trend score {a.get('trend_score', 0):.0f}, "
        f"24h {a.get('change_pct', 0):+.2f}%)"
        for a in ranked[:4]
        if abs(a.get("trend_score") or 0) >= 20
    ]
    vols = [a["vol_percentile"] for a in assets if a.get("vol_percentile") is not None]
    avg_vol = sum(vols) / len(vols) if vols else None
    hot = [a["symbol"] for a in assets if (a.get("vol_percentile") or 0) >= 90]
    vol_text = (
        "Volatility unavailable"
        if avg_vol is None
        else f"Average volatility percentile {avg_vol:.0f}"
        + (f"; elevated in {', '.join(hot)}" if hot else "")
    )
    risks = [
        f"High-impact: {e['event']} ({e['currency']}) at {e['time']}"
        for e in events
        if e.get("impact") == "HIGH"
    ][:4]
    risks += [f"{s}: extreme volatility" for s in hot]
    monitor = [
        f"{a['symbol']} ({a['signal']} score {a.get('score', 0):.0f})"
        for a in assets
        if a.get("signal") in ("LONG", "SHORT")
    ]
    ups = sum(1 for a in assets if (a.get("change_pct") or 0) > 0)
    theme = (
        (f"{ups} of {len(assets)} tracked instruments are up over 24h" + demo)
        if assets
        else "No market data available"
    )
    facts = [
        f"{a['symbol']} {a['price']} ({a.get('change_pct', 0):+.2f}% 24h), regime {a.get('regime')}"
        for a in assets[:10]
    ]
    return {
        "theme": theme,
        "strongest_trends": strongest or ["No instrument shows a strong trend score (|score| >= 20)"],
        "volatility": vol_text,
        "major_risks": risks or ["No high-impact events or extreme volatility in the input"],
        "upcoming_events": [f"{e['time']} {e['currency']} {e['event']} ({e['impact']})" for e in events[:6]]
        or ["No upcoming events in the input"],
        "assets_to_monitor": monitor or ["No instrument currently has a qualifying signal"],
        "facts": facts,
        "interpretation": [LABEL],
        "uncertainty": ["No model interpretation available without an AI provider"]
        + (["All figures are DEMO data"] if p.get("is_demo") else []),
    }


def research(p: dict[str, Any]) -> dict[str, Any]:
    f = p.get("features", {})
    st = p.get("structure", {})
    ev = p.get("historical_evidence") or {}
    scen = p.get("scenarios", {}).get("scenarios", [])
    sym = p.get("symbol", "?")
    tech = [
        f"Trend score {f.get('trend_score')}, momentum score {f.get('momentum_score')}, RSI {f.get('rsi14')}, ADX {f.get('adx')}",
        f"Structure {st.get('trend')}; regime {p.get('regime', {}).get('regime')}",
        f"ATR {f.get('atr14')} ({f.get('atr_pct')}% of price), volatility percentile {f.get('vol_percentile')}",
    ]
    macro = [
        *p.get("macro", {}).get("notes_for_long", []),
        *p.get("macro", {}).get("notes_for_short", []),
    ] or ["No macro context available in the input"]
    hist = [
        f"{ev.get('sample_size', 0)} similar historical setups ({ev.get('sample_label', 'NONE')}), "
        f"average R {ev.get('avg_r')}",
        *ev.get("notes", []),
    ]
    return {
        "market_overview": f"{sym} at {p.get('price')} on {p.get('timeframe')}. {LABEL}."
        + (" DEMO data." if p.get("is_demo") else ""),
        "technical_analysis": tech,
        "macro_context": macro,
        "risks": [e for e in p.get("risks", [])] or ["See the economic calendar and news panels"],
        "historical_evidence": hist,
        "scenarios": [
            {
                "name": s["name"],
                "trigger": s["trigger"],
                "confirmation": s["confirmation"],
                "invalidation": s["invalidation"],
                "notes": s.get("notes", ""),
            }
            for s in scen
        ],
        "uncertainty": ["Scenarios are conditional descriptions, not forecasts", LABEL],
    }


def news_sentiment(p: dict[str, Any]) -> dict[str, Any]:
    out = []
    for item in p.get("items", []):
        chg = item.get("data_change_pct")
        if chg is None:
            s, why = "UNCERTAIN", "No measurable price change attached to this item (rule-based)"
        elif chg > 0.3:
            s, why = "BULLISH", f"Referenced price change {chg:+.2f}% (rule-based threshold +0.30%)"
        elif chg < -0.3:
            s, why = "BEARISH", f"Referenced price change {chg:+.2f}% (rule-based threshold -0.30%)"
        else:
            s, why = "NEUTRAL", f"Referenced price change {chg:+.2f}% within +/-0.30%"
        out.append({"id": str(item.get("id")), "sentiment": s, "rationale": why})
    return {"items": out}


def explain(p: dict[str, Any]) -> dict[str, Any]:
    sig = p.get("signal", {})
    lv = sig.get("levels") or {}
    comps = sig.get("components", [])
    facts = [f"{sig.get('symbol')} {sig.get('timeframe')} at {sig.get('price')}; regime {sig.get('regime')}"]
    facts += sig.get("supporting_factors", [])[:5]
    calcs = [f"Signal score {sig.get('score')}/100 (rules-based quality score, not a probability)"]
    calcs += [f"{c['name']}: {c['points']:.1f}/{c['weight']:.0f}" for c in comps]
    if lv:
        calcs.append(
            f"Entry {lv.get('entry_price')}, stop {lv.get('stop')}, planned R:R {lv.get('effective_rr')}"
        )
    unc = sig.get("opposing_factors", [])[:5] + sig.get("no_trade_reasons", [])[:5]
    return {
        "facts": facts,
        "calculations": calcs,
        "interpretation": [LABEL],
        "uncertainty": unc or ["None recorded"],
    }
