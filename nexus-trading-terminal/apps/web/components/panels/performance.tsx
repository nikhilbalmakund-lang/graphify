"use client";

import type { GroupStats, PerformanceReport } from "@nexus/shared-types";

import { CountBars, SignedBars } from "@/components/charts/recharts-kit";
import { Stat } from "@/components/common/stat";
import { EmptyState } from "@/components/common/states";
import { RegimeBadge } from "@/components/market/badges";
import { Segmented } from "@/components/market/pickers";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { fmtMoney, fmtNum, fmtR } from "@/lib/format";
import { rDistribution } from "@/lib/series";
import { cn } from "@/lib/utils";
import { useState } from "react";

function GroupTable({ rows, label, isRegime, unit }: { rows: GroupStats[]; label: string; isRegime?: boolean; unit: "usd" | "r" }) {
  if (!rows.length) return <p className="px-3 py-4 text-xs text-faint">No data yet.</p>;
  return (
    <Table>
      <THead>
        <tr>
          <TH>{label}</TH>
          <TH align="right">Trades</TH>
          <TH align="right">Win rate</TH>
          <TH align="right">Expectancy</TH>
          <TH align="right">{unit === "usd" ? "P&L" : "Total R"}</TH>
        </tr>
      </THead>
      <tbody>
        {rows.map((r) => (
          <TR key={r.key}>
            <TD>{isRegime ? <RegimeBadge regime={r.key} /> : <span className="font-medium">{r.key}</span>}</TD>
            <TD align="right" className="num">
              {r.trades}
            </TD>
            <TD align="right" className="num">
              {r.win_rate === null ? "—" : `${fmtNum(r.win_rate * 100, 0)}%`}
            </TD>
            <TD align="right" className={cn("num", (r.expectancy_r ?? 0) >= 0 ? "text-up" : "text-down")}>
              {fmtR(r.expectancy_r)}
            </TD>
            <TD align="right" className={cn("num", r.pnl >= 0 ? "text-up" : "text-down")}>
              {unit === "usd" ? fmtMoney(r.pnl, 0, true) : fmtR(r.pnl)}
            </TD>
          </TR>
        ))}
      </tbody>
    </Table>
  );
}

/** Daily/weekly/monthly P&L, strategy/asset/regime breakdowns and R distribution for a PerformanceReport. */
export function PerformanceSection({ report, unit, title }: { report: PerformanceReport; unit: "usd" | "r"; title: string }) {
  const [period, setPeriod] = useState<"daily" | "weekly" | "monthly">("daily");
  if (!report.trades) {
    return (
      <Panel>
        <PanelHeader title={title} />
        <EmptyState title="No closed trades yet" description={report.sample_note} />
      </Panel>
    );
  }
  const fmt = (v: number) => (unit === "usd" ? fmtMoney(v, 0) : `${v.toFixed(2)}R`);
  return (
    <div className="flex flex-col gap-3">
      <Panel>
        <PanelHeader title={title} subtitle={report.sample_note} />
        <PanelBody className="grid grid-cols-2 gap-4 sm:grid-cols-5">
          <Stat label="Closed trades" value={report.trades} size="lg" />
          <Stat label="Win rate" value={report.win_rate === null ? "—" : `${fmtNum(report.win_rate * 100, 1)}%`} />
          <Stat label="Expectancy" value={unit === "usd" ? fmtMoney(report.expectancy, 2, true) : fmtR(report.expectancy_r)} sub={unit === "usd" ? `${fmtR(report.expectancy_r)} per trade` : undefined} tone={(report.expectancy_r ?? 0) >= 0 ? "up" : "down"} />
          <Stat label={unit === "usd" ? "Total P&L" : "Total R"} value={unit === "usd" ? fmtMoney(report.total_pnl, 2, true) : fmtR(report.total_pnl)} tone={report.total_pnl >= 0 ? "up" : "down"} />
          <Stat label="Max drawdown" value={unit === "usd" ? fmtMoney(-Math.abs(report.max_drawdown), 0) : `${fmtNum(-Math.abs(report.max_drawdown), 2)}R`} tone="down" />
        </PanelBody>
      </Panel>
      <div className="grid gap-3 xl:grid-cols-2">
        <Panel>
          <PanelHeader
            title="P&L by period"
            actions={
              <Segmented
                label="Period"
                value={period}
                onChange={setPeriod}
                options={[
                  { value: "daily", label: "Daily" },
                  { value: "weekly", label: "Weekly" },
                  { value: "monthly", label: "Monthly" },
                ]}
              />
            }
          />
          <PanelBody>
            <SignedBars data={report[period].map((p) => ({ label: p.period, value: p.pnl }))} valueLabel={unit === "usd" ? "P&L" : "R"} format={fmt} />
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="R-multiple distribution" />
          <PanelBody>
            <CountBars data={rDistribution(report.r_distribution)} height={200} />
          </PanelBody>
        </Panel>
      </div>
      <div className="grid gap-3 xl:grid-cols-3">
        <Panel>
          <PanelHeader title="By strategy" />
          <GroupTable rows={report.by_strategy} label="Strategy" unit={unit} />
        </Panel>
        <Panel>
          <PanelHeader title="By asset" />
          <GroupTable rows={report.by_asset} label="Asset" unit={unit} />
        </Panel>
        <Panel>
          <PanelHeader title="By market regime" />
          <GroupTable rows={report.by_regime} label="Regime" isRegime unit={unit} />
        </Panel>
      </div>
    </div>
  );
}
