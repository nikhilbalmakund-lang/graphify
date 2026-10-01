"use client";

import type { RiskStatus } from "@nexus/shared-types";

import { Stat } from "@/components/common/stat";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { fmtFrac, fmtMoney, fmtNum } from "@/lib/format";

export function RiskSummary({ risk }: { risk: RiskStatus }) {
  const lim = risk.limits as Record<string, number>;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="label">Risk engine</span>
        <Badge tone={risk.state === "NORMAL" ? "up" : risk.state === "HALTED" ? "solidDown" : "warn"}>{risk.state}</Badge>
        {risk.kill_switch ? <Badge tone="solidDown">Kill switch active</Badge> : null}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="mb-1 flex items-baseline justify-between text-xs">
            <span className="text-muted">Daily risk used</span>
            <span className="num text-fg">{fmtFrac(risk.daily_loss_used, 0)}</span>
          </div>
          <Progress value={risk.daily_loss_used * 100} tone={risk.daily_loss_used > 0.8 ? "down" : risk.daily_loss_used > 0.5 ? "warn" : "accent"} label="Daily loss limit used" />
          <p className="num mt-1 text-[0.62rem] text-faint">limit {fmtFrac(lim.max_daily_loss, 1)} of equity</p>
        </div>
        <div>
          <div className="mb-1 flex items-baseline justify-between text-xs">
            <span className="text-muted">Weekly risk used</span>
            <span className="num text-fg">{fmtFrac(risk.weekly_loss_used, 0)}</span>
          </div>
          <Progress value={risk.weekly_loss_used * 100} tone={risk.weekly_loss_used > 0.8 ? "down" : "accent"} label="Weekly loss limit used" />
          <p className="num mt-1 text-[0.62rem] text-faint">limit {fmtFrac(lim.max_weekly_loss, 1)}</p>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Drawdown" value={fmtFrac(risk.drawdown, 2)} tone={risk.drawdown > 0.05 ? "down" : undefined} size="sm" sub={`max ${fmtFrac(lim.max_drawdown, 0)}`} />
        <Stat label="Open exposure" value={fmtMoney(risk.gross_exposure, 0)} size="sm" sub={`${fmtNum(risk.leverage, 2)}× leverage`} />
        <Stat label="Open risk" value={fmtMoney(risk.open_risk_usd, 0)} size="sm" sub={`${risk.open_positions}/${lim.max_open_positions} positions`} />
      </div>
      {risk.messages.length ? <ul className="list-disc pl-4 text-[0.7rem] text-warn">{risk.messages.map((m, i) => <li key={i}>{m}</li>)}</ul> : null}
    </div>
  );
}
