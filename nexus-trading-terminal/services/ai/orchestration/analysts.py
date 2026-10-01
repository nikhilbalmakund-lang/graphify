"""ClaudeAnalyst, GeminiAnalyst and the AI review stage of the signal pipeline.

Both analysts receive the SAME structured payload and run concurrently, so
neither sees the other's conclusion (independent analysis). Each output is
schema-validated, then validated against the input data, then compared by the
consensus engine and reviewed by the critic.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from ai.critic.critic import AICritic, CriticResult
from ai.critic.validation import ValidationReport, validate_signal_analysis
from ai.orchestration.consensus import AIConsensusEngine, ConsensusResult
from ai.providers.base import AIProvider, AIProviderError, AIUsage


class AnalystOutcome(BaseModel):
    analyst: str
    provider: str
    status: str  # OK | NOT_CONFIGURED | ERROR | INVALID_OUTPUT
    model: str | None = None
    analysis: dict[str, Any] | None = None
    validation: ValidationReport | None = None
    error: str | None = None
    error_code: str | None = None
    usage: AIUsage | None = None
    prompt: dict[str, str] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)


class Analyst:
    analyst_name = "Analyst"

    def __init__(self, provider: AIProvider):
        self.provider = provider

    async def analyze(self, payload: dict[str, Any], min_rr: float) -> AnalystOutcome:
        base = {"analyst": self.analyst_name, "provider": self.provider.name}
        if not self.provider.configured or self.provider.is_demo:
            return AnalystOutcome(
                **base, status="NOT_CONFIGURED", error=f"{self.provider.label} not configured"
            )
        try:
            res = await self.provider.analyze_signal(payload)
        except AIProviderError as exc:
            status = "INVALID_OUTPUT" if exc.code == "AI_INVALID_OUTPUT" else "ERROR"
            return AnalystOutcome(**base, status=status, error=exc.message, error_code=exc.code)
        validation = validate_signal_analysis(res.data, payload, min_rr)
        return AnalystOutcome(
            **base,
            status="OK",
            model=res.model,
            analysis=res.data,
            validation=validation,
            usage=res.usage,
            prompt=res.prompt,
            settings=res.settings,
        )


class ClaudeAnalyst(Analyst):
    analyst_name = "ClaudeAnalyst"


class GeminiAnalyst(Analyst):
    analyst_name = "GeminiAnalyst"


class AIReview(BaseModel):
    claude: AnalystOutcome
    gemini: AnalystOutcome
    consensus: ConsensusResult
    critic: CriticResult
    ai_available: bool
    downgrade_to_no_trade: bool
    reasons: list[str] = Field(default_factory=list)

    def usages(self) -> list[AIUsage]:
        out = [o.usage for o in (self.claude, self.gemini) if o.usage]
        if self.critic.usage:
            out.append(self.critic.usage)
        return out


class AIReviewOrchestrator:
    """Runs the AI stage. AI can only DOWNGRADE a quant signal to NO_TRADE, never create one."""

    def __init__(
        self,
        claude: AIProvider,
        gemini: AIProvider,
        block_on_low_agreement: bool = True,
        require_ai_review: bool = False,
    ):
        self.claude = ClaudeAnalyst(claude)
        self.gemini = GeminiAnalyst(gemini)
        self.critic = AICritic([claude, gemini])
        self.consensus = AIConsensusEngine()
        self.block_on_low_agreement = block_on_low_agreement
        self.require_ai_review = require_ai_review

    async def review(self, payload: dict[str, Any], quant_direction: str, min_rr: float) -> AIReview:
        c, g = await asyncio.gather(
            self.claude.analyze(payload, min_rr), self.gemini.analyze(payload, min_rr)
        )
        analyses = {
            "claude": c.analysis if c.status == "OK" else None,
            "gemini": g.analysis if g.status == "OK" else None,
        }
        validations = {k: o.validation for k, o in (("claude", c), ("gemini", g)) if o.validation is not None}
        consensus = self.consensus.compare(analyses, quant_direction)
        critic = await self.critic.review(payload, analyses, validations, consensus)
        reasons: list[str] = []
        available = any(analyses.values())
        if quant_direction in ("LONG", "SHORT"):
            if consensus.agreement.value == "CONFLICT":
                reasons.append("AI models conflict (LONG vs SHORT)")
            if consensus.ai_opposes_quant:
                reasons.append("An AI analysis opposes the quantitative direction")
            if available and consensus.ai_rejects_trade:
                reasons.append("All AI analyses concluded NO_TRADE")
            if self.block_on_low_agreement and consensus.agreement.value == "LOW":
                reasons.append("Low agreement between AI models")
            if critic.verdict is not None and critic.verdict.value != "approved":
                reasons.append(f"AI critic verdict: {critic.verdict.value}")
            if self.require_ai_review and not available:
                reasons.append("AI review required by settings but no AI analysis was available")
        return AIReview(
            claude=c,
            gemini=g,
            consensus=consensus,
            critic=critic,
            ai_available=available,
            downgrade_to_no_trade=bool(reasons),
            reasons=reasons,
        )
