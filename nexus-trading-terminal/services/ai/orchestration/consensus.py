"""AI disagreement analysis. Agreement between models is reported, never forced,
and is not evidence that a conclusion is correct."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Agreement(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    CONFLICT = "CONFLICT"
    SINGLE = "SINGLE"
    UNAVAILABLE = "UNAVAILABLE"


class ConsensusResult(BaseModel):
    agreement: Agreement
    directions: dict[str, str] = Field(default_factory=dict)
    quant_direction: str
    ai_opposes_quant: bool = False
    ai_rejects_trade: bool = False
    shared_risks: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


class AIConsensusEngine:
    """Rules:
    * both analysts give the same direction -> HIGH (MEDIUM if either rates its own quality LOW)
    * one directional, the other NO_TRADE   -> LOW
    * LONG vs SHORT                          -> CONFLICT
    * only one valid analysis                -> SINGLE
    * none                                   -> UNAVAILABLE
    `ai_opposes_quant` is set when any valid analysis points the other way from
    the quant engine; `ai_rejects_trade` when every valid analysis says NO_TRADE.
    """

    def compare(self, analyses: dict[str, dict | None], quant_direction: str) -> ConsensusResult:
        valid = {k: v for k, v in analyses.items() if v}
        dirs = {k: v["direction"] for k, v in valid.items()}
        notes: list[str] = []
        if not valid:
            return ConsensusResult(
                agreement=Agreement.UNAVAILABLE,
                quant_direction=quant_direction,
                notes=["No AI analysis available; the deterministic engine decides alone"],
            )
        opposite = {"LONG": "SHORT", "SHORT": "LONG"}.get(quant_direction)
        opposes = any(d == opposite for d in dirs.values()) if opposite else False
        rejects = all(d == "NO_TRADE" for d in dirs.values())
        if len(valid) == 1:
            name, d = next(iter(dirs.items()))
            notes.append(f"Only {name} produced a valid analysis ({d})")
            return ConsensusResult(
                agreement=Agreement.SINGLE,
                directions=dirs,
                quant_direction=quant_direction,
                ai_opposes_quant=opposes,
                ai_rejects_trade=rejects,
                notes=notes,
            )
        values = list(dirs.values())
        if "LONG" in values and "SHORT" in values:
            agreement = Agreement.CONFLICT
            notes.append("Models reached opposite directions")
        elif len(set(values)) == 1:
            low_quality = any(v.get("analysis_quality") == "LOW" for v in valid.values())
            agreement = Agreement.MEDIUM if low_quality else Agreement.HIGH
            if low_quality:
                notes.append("Directions agree but at least one model rated its analysis quality LOW")
        else:
            agreement = Agreement.LOW
            notes.append("One model sees a trade, the other recommends NO_TRADE")
        risk_sets = [{_norm(r) for r in v.get("key_risks", [])} for v in valid.values()]
        shared = sorted(set.intersection(*risk_sets)) if risk_sets else []
        notes.append("Agreement between models does not demonstrate that a conclusion is correct")
        return ConsensusResult(
            agreement=agreement,
            directions=dirs,
            quant_direction=quant_direction,
            ai_opposes_quant=opposes,
            ai_rejects_trade=rejects,
            shared_risks=shared[:5],
            notes=notes,
        )
