"""AI provider abstraction.

Providers implement two primitives - one structured generation call and one
tool-use loop. The task methods required by the application
(analyze_market, analyze_signal, criticize_signal, summarize_market,
analyze_chart, research_asset) are built on top of them here, so adding a new
provider means implementing two methods.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from ai.orchestration.router import ModelRouter
from ai.orchestration.usage import estimate_cost
from ai.prompts.registry import PromptTemplate, get_prompt
from ai.schemas.outputs import (
    ChartImageAnalysis,
    CriticVerdict,
    MarketBriefing,
    NewsSentimentBatch,
    ResearchReport,
    SignalAnalysis,
)


class AIStatus(StrEnum):
    CONNECTED = "CONNECTED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONFIGURED_UNVERIFIED = "CONFIGURED_UNVERIFIED"
    ERROR = "ERROR"
    DEMO = "DEMO"


class AIProviderError(Exception):
    def __init__(self, code: str, message: str, provider: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.provider = provider


class AIUsage(BaseModel):
    provider: str
    model: str
    task: str
    prompt_name: str
    prompt_version: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float = 0.0
    cost_usd: float | None = None
    cached: bool = False
    success: bool = True
    error_code: str | None = None


class AIResult(BaseModel):
    provider: str
    model: str
    is_demo: bool = False
    data: dict[str, Any]
    usage: AIUsage
    settings: dict[str, Any] = Field(default_factory=dict)
    prompt: dict[str, str] = Field(default_factory=dict)


class ImageInput(BaseModel):
    data: bytes
    mime_type: str


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
    read_only: bool = True


class ToolTrace(BaseModel):
    name: str
    arguments: dict[str, Any]
    ok: bool
    summary: str
    duration_ms: float


ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class ProviderHealthInfo(BaseModel):
    provider: str
    status: AIStatus
    detail: str = ""
    models: dict[str, str] = Field(default_factory=dict)
    latency_ms: float | None = None


def render_input(payload: dict[str, Any]) -> str:
    """Compact, deterministic JSON so identical inputs hash and cache identically."""
    return "INPUT:\n" + json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


class AIProvider(ABC):
    name: str = "abstract"
    label: str = "Abstract"
    is_demo: bool = False

    def __init__(self, router: ModelRouter):
        self.router = router

    # ---------------------------------------------------------- primitives
    @property
    @abstractmethod
    def configured(self) -> bool: ...

    @abstractmethod
    async def validate(self) -> ProviderHealthInfo: ...

    @abstractmethod
    async def _generate(
        self,
        prompt: PromptTemplate,
        model: str,
        user_text: str,
        schema: type[BaseModel],
        images: list[ImageInput] | None,
    ) -> tuple[str, int | None, int | None, str]:
        """Return (json_text, input_tokens, output_tokens, served_model)."""

    @abstractmethod
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
        """Return (final_json_text, tool_trace, input_tokens, output_tokens, served_model)."""

    def settings_for(self, prompt: PromptTemplate) -> dict[str, Any]:
        return {"max_tokens": prompt.max_tokens, "temperature": prompt.temperature}

    # --------------------------------------------------------- structured
    async def generate(
        self,
        prompt_name: str,
        payload: dict[str, Any],
        schema: type[BaseModel],
        images: list[ImageInput] | None = None,
    ) -> AIResult:
        if not self.configured:
            raise AIProviderError("AI_PROVIDER_UNAVAILABLE", f"{self.label} is not configured", self.name)
        prompt = get_prompt(prompt_name)
        model = self.router.model_for(self.name, prompt.tier)
        started = time.perf_counter()
        try:
            text, tin, tout, served = await self._generate(
                prompt, model, render_input(payload), schema, images
            )
        except AIProviderError:
            raise
        except Exception as exc:  # provider SDK errors are normalised here
            raise AIProviderError(
                "AI_PROVIDER_UNAVAILABLE", f"{self.label} request failed: {type(exc).__name__}", self.name
            ) from exc
        latency = (time.perf_counter() - started) * 1000
        data = parse_structured(text, schema, self.name)
        usage = AIUsage(
            provider=self.name,
            model=served,
            task=prompt.task,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
            input_tokens=tin,
            output_tokens=tout,
            latency_ms=round(latency, 1),
            cost_usd=estimate_cost(self.name, served, tin, tout),
        )
        return AIResult(
            provider=self.name,
            model=served,
            is_demo=self.is_demo,
            data=data,
            usage=usage,
            settings=self.settings_for(prompt),
            prompt=prompt.meta(),
        )

    async def chat(
        self,
        prompt_name: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        executor: ToolExecutor,
        final_schema: type[BaseModel],
        max_turns: int = 8,
    ) -> tuple[AIResult, list[ToolTrace]]:
        if not self.configured:
            raise AIProviderError("AI_PROVIDER_UNAVAILABLE", f"{self.label} is not configured", self.name)
        bad = [t.name for t in tools if not t.read_only]
        if bad:
            raise AIProviderError(
                "AI_TOOL_FORBIDDEN", f"Only read-only tools may be exposed to AI: {bad}", self.name
            )
        prompt = get_prompt(prompt_name)
        model = self.router.model_for(self.name, prompt.tier)
        started = time.perf_counter()
        try:
            text, trace, tin, tout, served = await self._tool_loop(
                prompt, model, messages, tools, executor, final_schema, max_turns
            )
        except AIProviderError:
            raise
        except Exception as exc:
            raise AIProviderError(
                "AI_PROVIDER_UNAVAILABLE", f"{self.label} request failed: {type(exc).__name__}", self.name
            ) from exc
        data = parse_structured(text, final_schema, self.name)
        usage = AIUsage(
            provider=self.name,
            model=served,
            task=prompt.task,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
            input_tokens=tin,
            output_tokens=tout,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            cost_usd=estimate_cost(self.name, served, tin, tout),
        )
        return AIResult(
            provider=self.name,
            model=served,
            is_demo=self.is_demo,
            data=data,
            usage=usage,
            settings=self.settings_for(prompt),
            prompt=prompt.meta(),
        ), trace

    # ------------------------------------------------------- task methods
    async def analyze_market(self, payload: dict[str, Any]) -> AIResult:
        return await self.generate("market_briefing", payload, MarketBriefing)

    async def summarize_market(self, payload: dict[str, Any]) -> AIResult:
        return await self.generate("market_briefing", payload, MarketBriefing)

    async def analyze_signal(self, payload: dict[str, Any]) -> AIResult:
        return await self.generate("signal_analysis", payload, SignalAnalysis)

    async def criticize_signal(self, payload: dict[str, Any]) -> AIResult:
        return await self.generate("signal_critic", payload, CriticVerdict)

    async def analyze_chart(self, image: ImageInput, context: dict[str, Any]) -> AIResult:
        return await self.generate("chart_image_analysis", context, ChartImageAnalysis, images=[image])

    async def research_asset(self, payload: dict[str, Any]) -> AIResult:
        return await self.generate("asset_research", payload, ResearchReport)

    async def classify_news(self, payload: dict[str, Any]) -> AIResult:
        return await self.generate("news_sentiment", payload, NewsSentimentBatch)


def parse_structured(text: str, schema: type[BaseModel], provider: str) -> dict[str, Any]:
    """Parse and schema-validate model output. Raises AI_INVALID_OUTPUT on any mismatch."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned[cleaned.find("{") :]
    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AIProviderError("AI_INVALID_OUTPUT", "Model output was not valid JSON", provider) from exc
    try:
        return schema.model_validate(raw).model_dump(mode="json")
    except ValidationError as exc:
        raise AIProviderError(
            "AI_INVALID_OUTPUT",
            f"Model output failed schema validation ({exc.error_count()} errors)",
            provider,
        ) from exc
