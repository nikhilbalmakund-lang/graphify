import type { Metrics } from "@nexus/shared-types";

import { Stat } from "@/components/common/stat";
import { fmtMoney, fmtNum, fmtPct, fmtR } from "@/lib/format";

/** Every metric the spec requires, nothing hidden (losses and streaks included). */
export function MetricsGrid({ m }: { m: Metrics }) {
  const tone = (v: number | null | undefined) => (v === null || v === undefined ? undefined : v > 0 ? "up" : v < 0 ? "down" : undefined);
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4 xl:grid-cols-6">
      <Stat label="Total trades" value={m.total_trades} size="lg" sub={m.total_trades < 30 ? "small sample" : undefined} />
      <Stat label="Wins / losses" value={`${m.wins} / ${m.losses}`} sub={m.breakeven ? `${m.breakeven} breakeven` : undefined} />
      <Stat label="Win rate" value={m.win_rate === null ? "—" : `${fmtNum(m.win_rate * 100, 1)}%`} />
      <Stat label="Profit factor" value={fmtNum(m.profit_factor, 2)} tone={m.profit_factor === null ? undefined : m.profit_factor >= 1 ? "up" : "down"} />
      <Stat label="Expectancy" value={fmtMoney(m.expectancy, 2, true)} tone={tone(m.expectancy)} sub={`${fmtR(m.expectancy_r)} per trade`} />
      <Stat label="Average R" value={fmtR(m.average_r)} tone={tone(m.average_r)} />
      <Stat label="Net profit" value={fmtMoney(m.net_profit, 0, true)} tone={tone(m.net_profit)} sub={`${fmtPct(m.total_return_pct, 2)} return`} />
      <Stat label="Max drawdown" value={`${fmtNum(m.max_drawdown_pct, 2)}%`} tone="down" sub={fmtMoney(-Math.abs(m.max_drawdown_abs), 0)} />
      <Stat label="Sharpe" value={fmtNum(m.sharpe, 2)} hint="Annualised from per-bar equity returns" />
      <Stat label="Sortino" value={fmtNum(m.sortino, 2)} />
      <Stat label="CAGR" value={m.cagr_pct === null ? "—" : `${fmtNum(m.cagr_pct, 2)}%`} tone={tone(m.cagr_pct)} hint="Annualised; unreliable for short test periods" />
      <Stat label="Volatility" value={m.volatility_pct === null ? "—" : `${fmtNum(m.volatility_pct, 2)}%`} hint="Annualised volatility of equity returns" />
      <Stat label="Exposure" value={m.exposure_pct === null ? "—" : `${fmtNum(m.exposure_pct, 1)}%`} hint="Share of bars with an open position" />
      <Stat label="Largest win" value={fmtMoney(m.largest_win, 0)} tone="up" />
      <Stat label="Largest loss" value={fmtMoney(m.largest_loss, 0)} tone="down" />
      <Stat label="Longest losing streak" value={m.longest_losing_streak} tone={m.longest_losing_streak >= 5 ? "down" : undefined} sub={`win streak ${m.longest_winning_streak}`} />
      <Stat label="Avg win / loss" value={`${fmtMoney(m.avg_win, 0)} / ${fmtMoney(m.avg_loss, 0)}`} size="sm" />
      <Stat label="Avg bars held" value={fmtNum(m.avg_bars_held, 1)} />
    </div>
  );
}
