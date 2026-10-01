"""Structured output schemas for every AI task.

Models must return JSON matching these schemas. Outputs are parsed with
Pydantic and then validated again against the input data (see
`ai.critic.validation`) - AI output is never trusted directly. None of these
schemas contains an order or execution field: AI cannot create orders.
"""

from __future__ import annotations

import copy
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AIDirection(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"


class Quality(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Sentiment(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNCERTAIN = "UNCERTAIN"


class CriticDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_MORE_DATA = "needs_more_data"


class SignalAnalysis(BaseModel):
    direction: AIDirection
    reasoning: list[str]
    supporting_factors: list[str]
    opposing_factors: list[str]
    key_risks: list[str]
    invalidation: str
    analysis_quality: Quality
    disagreements: list[str] = Field(
        description="Points where you disagree with the quantitative engine's assessment"
    )
    referenced_prices: list[float] = Field(
        description="Every price level you mention, copied from the input data"
    )


class CriticVerdict(BaseModel):
    verdict: CriticDecision
    reasons: list[str]
    unsupported_claims: list[str]
    missing_evidence: list[str]
    contradictions: list[str]
    overconfidence: list[str]
    risk_reward_issues: list[str]
    news_risk_issues: list[str]
    data_problems: list[str]


class MarketBriefing(BaseModel):
    theme: str
    strongest_trends: list[str]
    volatility: str
    major_risks: list[str]
    upcoming_events: list[str]
    assets_to_monitor: list[str]
    facts: list[str]
    interpretation: list[str]
    uncertainty: list[str]


class ImageLevel(BaseModel):
    price: float | None
    description: str


class ChartImageAnalysis(BaseModel):
    asset_visible: str | None
    timeframe_visible: str | None
    trend: str
    structure: str
    levels: list[ImageLevel]
    indicators_visible: list[str]
    possible_setup: str
    readability: Quality
    caveats: list[str]


class Scenario(BaseModel):
    name: str  # BULLISH | BEARISH | NO_TRADE
    trigger: str
    confirmation: str
    invalidation: str
    notes: str


class ResearchReport(BaseModel):
    market_overview: str
    technical_analysis: list[str]
    macro_context: list[str]
    risks: list[str]
    historical_evidence: list[str]
    scenarios: list[Scenario]
    uncertainty: list[str]


class SentimentItem(BaseModel):
    id: str
    sentiment: Sentiment
    rationale: str


class NewsSentimentBatch(BaseModel):
    items: list[SentimentItem]


class ChatAnswer(BaseModel):
    """Every analyst answer separates facts, calculations, interpretation and uncertainty."""

    summary: str
    facts: list[str]
    calculations: list[str]
    interpretation: list[str]
    uncertainty: list[str]


class Explanation(BaseModel):
    facts: list[str]
    calculations: list[str]
    interpretation: list[str]
    uncertainty: list[str]


_DROP_KEYS = {
    "title",
    "default",
    "examples",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "pattern",
    "format",
}


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic schema -> self-contained strict JSON schema for structured outputs.

    Inlines $defs, drops keywords providers may not support (Pydantic still
    enforces them after parsing), and marks every object property required
    with additionalProperties=false.
    """
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].split("/")[-1]
                return resolve(copy.deepcopy(defs[name]))
            out = {k: resolve(v) for k, v in node.items() if k not in _DROP_KEYS}
            if out.get("type") == "object" and "properties" in out:
                out["required"] = list(out["properties"].keys())
                out["additionalProperties"] = False
            return out
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(raw)
