"""Deterministic validation of AI output against the data the model was given.

AI output is never trusted directly. After schema validation we check:
* every price the model cites is grounded in the input (within tolerance),
* no certainty / guaranteed-profit language,
* trades are not recommended against the risk/reward minimum,
* event risk in the input is acknowledged,
* claimed quality is not overstated for demo or degraded data.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, Field

CERTAINTY = re.compile(
    r"\b(guarantee[ds]?|certain(ly)?|risk[- ]free|100%|will definitely|cannot lose|sure thing|no risk)\b",
    re.I,
)
NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d{2,7})(?![\w.])")
PRICE_KEYS = {
    "price",
    "bid",
    "ask",
    "close",
    "open",
    "high",
    "low",
    "entry",
    "entry_price",
    "stop",
    "target",
    "level",
    "invalidation_level",
    "entry_zone_low",
    "entry_zone_high",
    "vwap",
    "ema20",
    "ema50",
    "ema200",
    "ema9",
    "sma20",
    "sma50",
    "bb_upper",
    "bb_lower",
    "bb_mid",
    "prior_high20",
    "prior_low20",
    "nearest_support",
    "nearest_resistance",
    "trigger_level",
    "risk_distance",
    "reward_distance",
}


class ValidationIssue(BaseModel):
    code: str
    severity: str  # SEVERE | MODERATE
    detail: str


class ValidationReport(BaseModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    grounded_prices: list[float] = Field(default_factory=list)
    unsupported_prices: list[float] = Field(default_factory=list)

    @property
    def severe(self) -> bool:
        return any(i.severity == "SEVERE" for i in self.issues)


def collect_prices(payload: Any, out: set[float] | None = None, key: str | None = None) -> set[float]:
    out = set() if out is None else out
    if isinstance(payload, dict):
        for k, v in payload.items():
            collect_prices(v, out, k)
    elif isinstance(payload, list):
        for v in payload:
            collect_prices(v, out, key)
    elif (
        isinstance(payload, (int, float))
        and not isinstance(payload, bool)
        and key is not None
        and (key in PRICE_KEYS or key.endswith(("_price", "_level")))
    ):
        out.add(float(payload))
    return out


def _grounded(x: float, known: Iterable[float], tol: float) -> bool:
    return any(abs(x - k) <= tol for k in known)


def _tolerance(payload: dict[str, Any]) -> tuple[float, float]:
    price = float(payload.get("price") or 0.0)
    atr = float((payload.get("features") or {}).get("atr14") or 0.0)
    return price, max(0.15 * atr, 0.0005 * price)


def _text_numbers(texts: Iterable[str], price: float) -> list[float]:
    found = []
    for t in texts:
        for m in NUMBER.findall(t or ""):
            try:
                v = float(m.replace(",", ""))
            except ValueError:
                continue
            if price > 0 and 0.7 * price <= v <= 1.3 * price:
                found.append(v)
    return found


def validate_signal_analysis(
    analysis: dict[str, Any], payload: dict[str, Any], min_rr: float
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    known = collect_prices(payload)
    price, tol = _tolerance(payload)
    texts = [
        *analysis.get("reasoning", []),
        *analysis.get("supporting_factors", []),
        *analysis.get("opposing_factors", []),
        *analysis.get("key_risks", []),
        analysis.get("invalidation", ""),
        *analysis.get("disagreements", []),
    ]
    cited = list(analysis.get("referenced_prices", [])) + _text_numbers(texts, price)
    grounded = sorted({round(x, 8) for x in cited if _grounded(x, known, tol)})
    unsupported = sorted({round(x, 8) for x in cited if not _grounded(x, known, tol)})
    if unsupported:
        issues.append(
            ValidationIssue(
                code="UNSUPPORTED_PRICE",
                severity="SEVERE",
                detail=f"Prices not present in the input data: {unsupported[:6]}",
            )
        )
    if not analysis.get("reasoning"):
        issues.append(
            ValidationIssue(code="MISSING_REASONING", severity="SEVERE", detail="No reasoning provided")
        )
    if not (analysis.get("invalidation") or "").strip():
        issues.append(
            ValidationIssue(
                code="MISSING_INVALIDATION", severity="MODERATE", detail="No invalidation condition"
            )
        )
    if any(CERTAINTY.search(t or "") for t in texts):
        issues.append(
            ValidationIssue(
                code="OVERCONFIDENCE", severity="SEVERE", detail="Certainty or guaranteed-outcome language"
            )
        )
    direction = analysis.get("direction")
    rr = ((payload.get("quant") or {}).get("levels") or {}).get("effective_rr")
    if direction in ("LONG", "SHORT") and rr is not None and rr < min_rr:
        issues.append(
            ValidationIssue(
                code="BAD_RISK_REWARD",
                severity="SEVERE",
                detail=f"Recommends {direction} although planned R:R {rr} < minimum {min_rr}",
            )
        )
    events = payload.get("events") or {}
    mins = events.get("next_high_impact_minutes")
    if direction in ("LONG", "SHORT") and mins is not None and 0 <= mins <= 120:
        risk_text = " ".join(analysis.get("key_risks", []) + analysis.get("opposing_factors", [])).lower()
        if not any(
            w in risk_text
            for w in (
                "event",
                "release",
                "announcement",
                "news",
                "cpi",
                "nfp",
                "fomc",
                "calendar",
                "decision",
                "report",
            )
        ):
            issues.append(
                ValidationIssue(
                    code="NEWS_RISK_IGNORED",
                    severity="MODERATE",
                    detail=f"High-impact event in {int(mins)} min not acknowledged in risks",
                )
            )
    quality = analysis.get("analysis_quality")
    dq = (payload.get("data_quality") or {}).get("quality_score", 1.0)
    if quality == "HIGH" and (payload.get("is_demo") or (dq is not None and dq < 0.8)):
        issues.append(
            ValidationIssue(
                code="QUALITY_OVERSTATED",
                severity="MODERATE",
                detail="HIGH analysis quality claimed on demo or degraded data",
            )
        )
    return ValidationReport(
        valid=not any(i.severity == "SEVERE" for i in issues),
        issues=issues,
        grounded_prices=grounded,
        unsupported_prices=unsupported,
    )
