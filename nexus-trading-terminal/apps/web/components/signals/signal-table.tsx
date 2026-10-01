"use client";

import type { Signal } from "@nexus/shared-types";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { DataBadge, DirectionBadge, RegimeBadge, StatusBadge } from "@/components/market/badges";
import { Table, TD, TH, THead, TR, useSort } from "@/components/ui/table";
import { fmtPrice, fmtR, fmtRR, fmtTime } from "@/lib/format";

import { ScoreBar } from "./score";
import { entryText } from "./signal-card";

export function SignalTable({ signals }: { signals: Signal[] }) {
  const router = useRouter();
  const rows = signals.map((s) => ({ ...s, r: s.outcome?.r_multiple ?? null }));
  const { sorted, sort, onSort } = useSort(rows, { key: "created_at", dir: "desc" });
  return (
    <Table>
      <THead>
        <tr>
          <TH sortKey="created_at" sort={sort} onSort={onSort}>
            Time (UTC)
          </TH>
          <TH sortKey="symbol" sort={sort} onSort={onSort}>
            Asset
          </TH>
          <TH>TF</TH>
          <TH sortKey="direction" sort={sort} onSort={onSort}>
            Signal
          </TH>
          <TH sortKey="score" sort={sort} onSort={onSort}>
            Score
          </TH>
          <TH>Regime</TH>
          <TH align="right">Entry</TH>
          <TH align="right">Stop</TH>
          <TH align="right">TP1</TH>
          <TH sortKey="effective_rr" sort={sort} onSort={onSort} align="right">
            R:R
          </TH>
          <TH sortKey="status" sort={sort} onSort={onSort}>
            Status
          </TH>
          <TH sortKey="r" sort={sort} onSort={onSort} align="right">
            Result
          </TH>
          <TH>Data</TH>
        </tr>
      </THead>
      <tbody>
        {sorted.map((s) => (
          <TR key={s.id} className="cursor-pointer" onClick={() => router.push(`/signals/${s.id}`)}>
            <TD className="num text-muted">{fmtTime(s.created_at, true)}</TD>
            <TD>
              <Link href={`/signals/${s.id}`} className="font-semibold text-fg hover:text-accent" onClick={(e) => e.stopPropagation()}>
                {s.symbol}
              </Link>
            </TD>
            <TD className="num text-muted">{s.timeframe}</TD>
            <TD>
              <DirectionBadge direction={s.direction} />
            </TD>
            <TD>
              <ScoreBar score={s.score} />
            </TD>
            <TD>
              <RegimeBadge regime={s.regime} />
            </TD>
            <TD align="right" className="num">
              {s.direction === "NO_TRADE" ? "—" : entryText(s)}
            </TD>
            <TD align="right" className="num text-down">
              {s.direction === "NO_TRADE" ? "—" : fmtPrice(s.stop, s.symbol)}
            </TD>
            <TD align="right" className="num text-up">
              {s.direction === "NO_TRADE" ? "—" : fmtPrice(s.targets[0]?.price, s.symbol)}
            </TD>
            <TD align="right" className="num">
              {s.direction === "NO_TRADE" ? "—" : fmtRR(s.effective_rr ?? s.rr)}
            </TD>
            <TD>
              <StatusBadge status={s.status} />
            </TD>
            <TD align="right" className={s.r === null ? "num text-faint" : s.r >= 0 ? "num text-up" : "num text-down"}>
              {fmtR(s.r)}
            </TD>
            <TD>
              <DataBadge isDemo={s.is_demo} provider={s.provider} />
            </TD>
          </TR>
        ))}
      </tbody>
    </Table>
  );
}
