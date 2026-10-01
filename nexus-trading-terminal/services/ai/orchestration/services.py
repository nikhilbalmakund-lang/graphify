"""AIExplainer, AIResearcher, AIChartAnalyzer and the market briefing writer.

Each uses the first configured AI provider (Claude preferred, then Gemini)
and falls back to the rule-based DEMO builder where a deterministic answer is
possible. Image analysis has no deterministic fallback.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ai.providers.base import AIProvider, AIProviderError, AIResult, ImageInput
from ai.providers.demo import DemoRuleBasedProvider
from ai.schemas.outputs import Explanation

IMAGE_LABEL = "IMAGE ANALYSIS - derived from screenshot pixels; not exchange or broker data"


class _Chain:
    def __init__(self, providers: list[AIProvider], allow_demo: bool = True):
        self.providers = [p for p in providers if p.configured and not p.is_demo]
        self.demo = DemoRuleBasedProvider() if allow_demo else None

    async def _run(self, call: Any) -> tuple[AIResult, list[str]]:
        errors: list[str] = []
        for p in self.providers:
            try:
                return await call(p), errors
            except AIProviderError as exc:
                errors.append(f"{p.label}: {exc.message}")
        if self.demo is None:
            raise AIProviderError("AI_PROVIDER_UNAVAILABLE", "; ".join(errors) or "No AI provider configured")
        return await call(self.demo), errors


class AIExplainer(_Chain):
    async def explain(self, signal: dict[str, Any]) -> tuple[AIResult, list[str]]:
        return await self._run(lambda p: p.generate("signal_explainer", {"signal": signal}, Explanation))


class AIResearcher(_Chain):
    async def research(self, payload: dict[str, Any]) -> tuple[AIResult, list[str]]:
        return await self._run(lambda p: p.research_asset(payload))


class BriefingWriter(_Chain):
    async def write(self, payload: dict[str, Any]) -> tuple[AIResult, list[str]]:
        return await self._run(lambda p: p.summarize_market(payload))


class NewsClassifier(_Chain):
    async def classify(self, payload: dict[str, Any]) -> tuple[AIResult, list[str]]:
        return await self._run(lambda p: p.classify_news(payload))


class ChartScanResult(BaseModel):
    label: str = IMAGE_LABEL
    available: bool
    provider: str | None = None
    model: str | None = None
    analysis: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)
    precedence_note: str = "When live or demo market data exists for the same instrument, that data takes precedence over image-derived values."


class AIChartAnalyzer(_Chain):
    def __init__(self, providers: list[AIProvider]):
        super().__init__(providers, allow_demo=False)

    async def analyze(
        self, image: ImageInput, context: dict[str, Any]
    ) -> tuple[ChartScanResult, AIResult | None]:
        if not self.providers:
            return ChartScanResult(
                available=False,
                errors=["Image analysis requires Claude or Gemini; no AI provider is configured"],
            ), None
        try:
            res, errors = await self._run(lambda p: p.analyze_chart(image, context))
        except AIProviderError as exc:
            return ChartScanResult(available=False, errors=[exc.message]), None
        return ChartScanResult(
            available=True, provider=res.provider, model=res.model, analysis=res.data, errors=errors
        ), res
