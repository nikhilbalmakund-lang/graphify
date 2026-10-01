"""AICritic: a third, adversarial review stage.

The final verdict is the MOST RESTRICTIVE of:
* the deterministic critic (validation issues, conflicts, data problems), and
* the AI critic (Claude preferred, Gemini otherwise), when configured.
The critic may only approve, reject or ask for more data - it cannot create
or modify a trade, and the deterministic risk engine still has the final veto.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ai.critic.validation import ValidationReport
from ai.orchestration.consensus import Agreement, ConsensusResult
from ai.providers.base import AIProvider, AIProviderError, AIUsage
from ai.schemas.outputs import CriticDecision

RANK = {CriticDecision.APPROVED: 0, CriticDecision.NEEDS_MORE_DATA: 1, CriticDecision.REJECTED: 2}


class CriticResult(BaseModel):
    verdict: CriticDecision | None
    status: str  # REVIEWED | SKIPPED
    source: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    details: dict[str, list[str]] = Field(default_factory=dict)
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_error: str | None = None
    usage: AIUsage | None = None
    prompt: dict[str, str] = Field(default_factory=dict)


def deterministic_review(
    validations: dict[str, ValidationReport], consensus: ConsensusResult, payload: dict[str, Any]
) -> tuple[CriticDecision, list[str], dict[str, list[str]]]:
    details: dict[str, list[str]] = {
        "unsupported_claims": [],
        "contradictions": [],
        "overconfidence": [],
        "risk_reward_issues": [],
        "news_risk_issues": [],
        "data_problems": [],
    }
    decision = CriticDecision.APPROVED
    code_map = {
        "UNSUPPORTED_PRICE": "unsupported_claims",
        "MISSING_REASONING": "unsupported_claims",
        "OVERCONFIDENCE": "overconfidence",
        "QUALITY_OVERSTATED": "overconfidence",
        "BAD_RISK_REWARD": "risk_reward_issues",
        "NEWS_RISK_IGNORED": "news_risk_issues",
        "MISSING_INVALIDATION": "unsupported_claims",
    }
    for name, rep in validations.items():
        for issue in rep.issues:
            details[code_map.get(issue.code, "data_problems")].append(f"{name}: {issue.detail}")
            if issue.severity == "SEVERE":
                decision = CriticDecision.REJECTED
            elif decision == CriticDecision.APPROVED:
                decision = CriticDecision.NEEDS_MORE_DATA
    if consensus.agreement == Agreement.CONFLICT:
        details["contradictions"].append("Claude and Gemini reached opposite directions")
        decision = CriticDecision.REJECTED
    if consensus.ai_opposes_quant:
        details["contradictions"].append("An AI analysis points opposite to the quantitative engine")
        decision = CriticDecision.REJECTED
    dq = payload.get("data_quality") or {}
    if dq and not dq.get("usable", True):
        details["data_problems"].append("Market data failed quality checks")
        decision = CriticDecision.REJECTED
    ev = payload.get("historical_evidence") or {}
    if ev.get("sample_label") in ("NONE", "INSUFFICIENT"):
        details["data_problems"].append(
            f"Historical sample {ev.get('sample_label')} (n={ev.get('sample_size', 0)})"
        )
        if decision == CriticDecision.APPROVED:
            decision = CriticDecision.NEEDS_MORE_DATA
    reasons = [item for items in details.values() for item in items]
    return decision, reasons, details


class AICritic:
    def __init__(self, providers: list[AIProvider]):
        self.providers = [p for p in providers if p.configured and not p.is_demo]

    async def review(
        self,
        payload: dict[str, Any],
        analyses: dict[str, dict | None],
        validations: dict[str, ValidationReport],
        consensus: ConsensusResult,
    ) -> CriticResult:
        if not any(analyses.values()):
            return CriticResult(verdict=None, status="SKIPPED", reasons=["No AI analyses to critique"])
        det, det_reasons, details = deterministic_review(validations, consensus, payload)
        result = CriticResult(
            verdict=det, status="REVIEWED", source=["deterministic"], reasons=det_reasons, details=details
        )
        critic_payload = {
            **payload,
            "ai_analyses": {k: v for k, v in analyses.items() if v},
            "deterministic_findings": details,
        }
        for provider in self.providers:
            try:
                ai = await provider.criticize_signal(critic_payload)
            except AIProviderError as exc:
                result.ai_error = f"{provider.label}: {exc.message}"
                continue
            v = CriticDecision(ai.data["verdict"])
            result.ai_provider, result.ai_model, result.usage, result.prompt = (
                provider.name,
                ai.model,
                ai.usage,
                ai.prompt,
            )
            result.source.append(provider.name)
            for key in (
                "unsupported_claims",
                "missing_evidence",
                "contradictions",
                "overconfidence",
                "risk_reward_issues",
                "news_risk_issues",
                "data_problems",
            ):
                result.details.setdefault(key, []).extend(
                    f"{provider.name}: {x}" for x in ai.data.get(key, [])
                )
            result.reasons += [f"{provider.name}: {r}" for r in ai.data.get("reasons", [])]
            if RANK[v] > RANK[result.verdict or CriticDecision.APPROVED]:
                result.verdict = v
            break
        return result
