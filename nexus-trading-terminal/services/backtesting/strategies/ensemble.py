"""Strategy ensemble. Votes are combined by predefined rules, not averaged blindly.

Rules
-----
1. Only *applicable* strategies (current regime is in the strategy's regime
   list) vote at full weight; others count at 30%.
2. Weight = strength x regime factor x performance factor, where the
   performance factor comes from measured per-regime statistics (>= 30
   trades): 1.2 if expectancy > 0, 0.6 if expectancy < 0, else 1.0.
3. No active votes -> NO_TRADE.
4. Votes in both directions with agreement < 66% -> NO_TRADE (conflict).
5. Otherwise the majority direction, with the agreement ratio reported.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backtesting.strategies.base import BarView, Strategy, StrategyVote
from quant.signals.models import Direction

CONFLICT_AGREEMENT = 0.66


class StrategyPerf(BaseModel):
    trades: int = 0
    expectancy_r: float | None = None


class EnsembleResult(BaseModel):
    votes: list[StrategyVote]
    net_direction: Direction
    agreement: float
    conflict: bool
    long_weight: float
    short_weight: float
    supporting: list[str] = Field(default_factory=list)
    opposing: list[str] = Field(default_factory=list)
    summary: str = ""

    def as_context(self) -> dict:
        return {
            "net_direction": self.net_direction.value,
            "agreement": self.agreement,
            "conflict": self.conflict,
            "supporting": self.supporting,
            "opposing": self.opposing,
        }


def combine_votes(
    votes: list[StrategyVote], regime: str, perf: dict[tuple[str, str], StrategyPerf] | None = None
) -> EnsembleResult:
    lw = sw = 0.0
    longs, shorts = [], []
    for vt in votes:
        if vt.direction == Direction.NO_TRADE:
            continue
        w = vt.strength * (1.0 if vt.applicable else 0.3)
        p = (perf or {}).get((vt.strategy, regime))
        if p and p.trades >= 30 and p.expectancy_r is not None:
            w *= 1.2 if p.expectancy_r > 0 else 0.6
        if vt.direction == Direction.LONG:
            lw += w
            longs.append(vt.strategy)
        else:
            sw += w
            shorts.append(vt.strategy)
    total = lw + sw
    if total <= 0:
        return EnsembleResult(
            votes=votes,
            net_direction=Direction.NO_TRADE,
            agreement=0.0,
            conflict=False,
            long_weight=0.0,
            short_weight=0.0,
            summary="No strategy triggered",
        )
    agreement = max(lw, sw) / total
    conflict = bool(longs and shorts)
    majority = Direction.LONG if lw >= sw else Direction.SHORT
    if conflict and agreement < CONFLICT_AGREEMENT:
        net = Direction.NO_TRADE
        summary = f"Conflict: LONG ({', '.join(longs)}) vs SHORT ({', '.join(shorts)})"
    else:
        net = majority
        summary = f"{majority.value} by {', '.join(longs if majority == Direction.LONG else shorts)} (agreement {agreement:.0%})"
    supporting = longs if majority == Direction.LONG else shorts
    opposing = shorts if majority == Direction.LONG else longs
    return EnsembleResult(
        votes=votes,
        net_direction=net,
        agreement=round(agreement, 3),
        conflict=conflict,
        long_weight=round(lw, 3),
        short_weight=round(sw, 3),
        supporting=supporting,
        opposing=opposing,
        summary=summary,
    )


def run_ensemble(
    strategies: list[Strategy], view: BarView, perf: dict[tuple[str, str], StrategyPerf] | None = None
) -> EnsembleResult:
    return combine_votes([s.vote(view) for s in strategies], view.regime, perf)
