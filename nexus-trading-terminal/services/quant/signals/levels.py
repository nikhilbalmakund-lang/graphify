"""Entry / stop / target construction.

Rules (LONG shown; SHORT mirrors):

* Invalidation = the nearest *structural* level below the entry (last swing
  low first, then mapped supports) that sits at least `min_stop_atr` ATR away
  once the `stop_buffer_atr` buffer is applied. If no structural level
  qualifies there is NO stop and therefore NO trade - stops are never invented.
* Entry: MARKET after a fresh breakout/sweep in the trade direction or when
  the stop is already close; otherwise a ZONE entry at a pull-back level
  (EMA20 / broken level / support) between the stop and price.
* Targets: structural levels (resistances, equal highs, prior-day high, last
  swing high) at >= 1R. Where no structural level exists in range an explicit
  R-multiple target is used and labelled as such.
* effective R:R weights each target's R:R by the configured exit plan.
"""

from __future__ import annotations

from quant.signals.models import EntryType, LevelPlan, SignalConfig, SignalContext, TargetLevel


def _fmt(x: float, prec: int) -> str:
    return f"{x:.{prec}f}"


def build_levels(ctx: SignalContext, d: int, cfg: SignalConfig) -> tuple[LevelPlan | None, str]:
    f, st = ctx.features, ctx.structure
    prec = ctx.price_precision
    atr = f.atr14
    if atr is None or atr <= 0:
        return None, "ATR unavailable: cannot size invalidation objectively"
    entry_mkt = ctx.ask if d > 0 else ctx.bid
    buffer = cfg.stop_buffer_atr * atr

    # ---- invalidation / stop
    candidates: list[tuple[float, str]] = []
    if d > 0:
        if st.last_swing_low and st.last_swing_low.price < entry_mkt:
            candidates.append(
                (st.last_swing_low.price, f"last swing low ({st.last_swing_low.label or 'swing'})")
            )
        candidates += [
            (lv.price, f"support ({lv.touches} touches)") for lv in st.supports if lv.price < entry_mkt
        ]
        candidates.sort(key=lambda c: -c[0])
    else:
        if st.last_swing_high and st.last_swing_high.price > entry_mkt:
            candidates.append(
                (st.last_swing_high.price, f"last swing high ({st.last_swing_high.label or 'swing'})")
            )
        candidates += [
            (lv.price, f"resistance ({lv.touches} touches)") for lv in st.resistances if lv.price > entry_mkt
        ]
        candidates.sort(key=lambda c: c[0])

    chosen: tuple[float, str] | None = None
    for level, basis in candidates:
        stop = level - buffer if d > 0 else level + buffer
        if abs(entry_mkt - stop) >= cfg.min_stop_atr * atr:
            chosen = (level, basis)
            break
    if chosen is None:
        return None, "No structural invalidation level at a valid distance"
    inval_level, inval_basis = chosen
    stop = inval_level - buffer if d > 0 else inval_level + buffer

    # ---- entry
    entry_type = EntryType.MARKET
    entry = entry_mkt
    zone_low = zone_high = None
    fresh_trigger = False
    if st.breakout and not st.breakout.failed and st.breakout.bars_ago <= 3:
        fresh_trigger = (st.breakout.direction == "BULLISH") == (d > 0)
    if st.sweep and st.sweep.bars_ago <= 3:
        fresh_trigger = fresh_trigger or ((st.sweep.direction == "BULLISH") == (d > 0))
    if not fresh_trigger and abs(entry_mkt - stop) > 2.0 * atr:
        pullbacks: list[tuple[float, str]] = []
        if f.ema20 is not None:
            pullbacks.append((f.ema20, "EMA20 pull-back"))
        if st.breakout and not st.breakout.failed and (st.breakout.direction == "BULLISH") == (d > 0):
            pullbacks.append((st.breakout.level, "retest of broken level"))
        levels = st.supports if d > 0 else st.resistances
        pullbacks += [(lv.price, "retest of support" if d > 0 else "retest of resistance") for lv in levels]
        valid = [
            (p, why)
            for p, why in pullbacks
            if (d > 0 and stop + 0.6 * atr <= p < entry_mkt - 0.2 * atr)
            or (d < 0 and entry_mkt + 0.2 * atr < p <= stop - 0.6 * atr)
        ]
        if valid:
            p, _why = max(valid, key=lambda x: x[0]) if d > 0 else min(valid, key=lambda x: x[0])
            entry_type = EntryType.ZONE
            entry = p
            zone_low, zone_high = p - 0.15 * atr, p + 0.15 * atr

    risk = abs(entry - stop)
    if risk <= 0:
        return None, "Degenerate risk distance"

    # ---- targets
    if d > 0:
        structural = [(lv.price, f"resistance {_fmt(lv.price, prec)}") for lv in st.resistances]
        structural += [
            (
                z.price,
                f"{z.kind.replace('_', ' ').lower()} {_fmt(z.price, prec)}"
                + (" (heuristic)" if z.heuristic else ""),
            )
            for z in st.liquidity_zones
            if z.kind in ("EQUAL_HIGHS", "PRIOR_DAY_HIGH")
        ]
        if st.last_swing_high:
            structural.append(
                (st.last_swing_high.price, f"last swing high {_fmt(st.last_swing_high.price, prec)}")
            )
        structural = sorted({round(p, prec + 2): (p, why) for p, why in structural if p > entry}.values())
    else:
        structural = [(lv.price, f"support {_fmt(lv.price, prec)}") for lv in st.supports]
        structural += [
            (
                z.price,
                f"{z.kind.replace('_', ' ').lower()} {_fmt(z.price, prec)}"
                + (" (heuristic)" if z.heuristic else ""),
            )
            for z in st.liquidity_zones
            if z.kind in ("EQUAL_LOWS", "PRIOR_DAY_LOW")
        ]
        if st.last_swing_low:
            structural.append(
                (st.last_swing_low.price, f"last swing low {_fmt(st.last_swing_low.price, prec)}")
            )
        structural = sorted(
            {round(p, prec + 2): (p, why) for p, why in structural if p < entry}.values(), reverse=True
        )

    def rr_of(p: float) -> float:
        return abs(p - entry) / risk

    targets: list[TargetLevel] = []
    fallbacks = [1.5, 2.5, 4.0]
    caps = [6.0, 8.0, 10.0]
    used: set[float] = set()
    for i in range(3):
        floor = 1.0 if i == 0 else targets[-1].rr + 0.5
        pick = next(
            ((p, why) for p, why in structural if p not in used and floor <= rr_of(p) <= caps[i]), None
        )
        if pick:
            price, basis = pick[0], f"STRUCTURE: {pick[1]}"
            used.add(pick[0])
        else:
            r = max(fallbacks[i], floor)
            price = entry + d * r * risk
            basis = f"R-MULTIPLE: {r:.1f}R (no structural level in range)"
        targets.append(
            TargetLevel(
                label=f"TP{i + 1}",
                price=round(price, prec),
                rr=round(rr_of(price), 2),
                basis=basis,
                allocation=cfg.exit_plan[i],
            )
        )

    eff = sum(t.rr * t.allocation for t in targets)
    side_word = "below" if d > 0 else "above"
    plan = LevelPlan(
        entry_type=entry_type,
        entry_price=round(entry, prec),
        entry_zone_low=round(zone_low, prec) if zone_low is not None else None,
        entry_zone_high=round(zone_high, prec) if zone_high is not None else None,
        stop=round(stop, prec),
        invalidation_level=round(inval_level, prec),
        invalidation_text=f"A {ctx.timeframe} close {side_word} {_fmt(inval_level, prec)} ({inval_basis}) invalidates the setup.",
        stop_basis=f"{inval_basis} {_fmt(inval_level, prec)} with a {cfg.stop_buffer_atr:.2f} ATR buffer",
        targets=targets,
        risk_distance=round(risk, prec + 2),
        reward_distance=round(abs(targets[-1].price - entry), prec + 2),
        rr=round(targets[-1].rr, 2),
        effective_rr=round(eff, 2),
        risk_atr=round(risk / atr, 2),
    )
    return plan, ""
