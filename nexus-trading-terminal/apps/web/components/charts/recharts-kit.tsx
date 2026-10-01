"use client";

import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";

import { fmtNum } from "@/lib/format";

const AXIS = { stroke: "#283446", tick: { fill: "#8090a5", fontSize: 10, fontFamily: "var(--font-mono)" }, tickLine: false } as const;
const TOOLTIP = {
  contentStyle: { background: "#141c28", border: "1px solid #283446", borderRadius: 4, fontSize: 11, fontFamily: "var(--font-mono)", color: "#d6dee9" },
  labelStyle: { color: "#8090a5" },
  itemStyle: { color: "#d6dee9" },
  cursor: { stroke: "#283446" },
} as const;

const shortDate = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", timeZone: "UTC" });
};

/** Equity curve with optional balance line. Points: {ts, equity, balance?}. */
export function EquityChart({ data, height = 220, color = "#22d3ee" }: { data: { ts: string; equity: number; balance?: number }[]; height?: number; color?: string }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="eqfill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.25} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#1b2533" vertical={false} />
        <XAxis dataKey="ts" tickFormatter={shortDate} {...AXIS} minTickGap={40} />
        <YAxis {...AXIS} width={64} domain={["auto", "auto"]} tickFormatter={(v: number) => fmtNum(v, 0)} />
        <Tooltip {...TOOLTIP} labelFormatter={(l) => shortDate(String(l))} formatter={(v) => fmtNum(Number(v), 2)} />
        <Area type="monotone" dataKey="equity" name="Equity" stroke={color} strokeWidth={1.5} fill="url(#eqfill)" isAnimationActive={false} />
        {data.some((d) => d.balance !== undefined) ? <Area type="stepAfter" dataKey="balance" name="Balance" stroke="#8090a5" strokeDasharray="3 3" fill="none" isAnimationActive={false} /> : null}
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Drawdown (negative %, area under zero). Points: {ts, dd} where dd is a fraction (0.05 = 5%). */
export function DrawdownChart({ data, height = 140 }: { data: { ts: string; dd: number }[]; height?: number }) {
  const pts = data.map((d) => ({ ts: d.ts, dd: -Math.abs(d.dd) * 100 }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={pts} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#1b2533" vertical={false} />
        <XAxis dataKey="ts" tickFormatter={shortDate} {...AXIS} minTickGap={40} />
        <YAxis {...AXIS} width={64} tickFormatter={(v: number) => `${fmtNum(v, 1)}%`} />
        <Tooltip {...TOOLTIP} labelFormatter={(l) => shortDate(String(l))} formatter={(v) => `${fmtNum(Number(v), 2)}%`} />
        <Area type="monotone" dataKey="dd" name="Drawdown" stroke="#f0525c" strokeWidth={1.2} fill="#f0525c" fillOpacity={0.18} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Signed bar chart (green positive, red negative). */
export function SignedBars({ data, height = 200, valueLabel = "Value", format = (v: number) => fmtNum(v, 2) }: { data: { label: string; value: number }[]; height?: number; valueLabel?: string; format?: (v: number) => string }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#1b2533" vertical={false} />
        <XAxis dataKey="label" {...AXIS} interval="preserveStartEnd" minTickGap={8} />
        <YAxis {...AXIS} width={64} tickFormatter={(v: number) => format(v)} />
        <ReferenceLine y={0} stroke="#283446" />
        <Tooltip {...TOOLTIP} cursor={{ fill: "#141c28" }} formatter={(v) => [format(Number(v)), valueLabel]} />
        <Bar dataKey="value" isAnimationActive={false} radius={[2, 2, 0, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.value >= 0 ? "#26c281" : "#f0525c"} fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Histogram of counts (e.g. R-multiple distribution). */
export function CountBars({ data, height = 180, color = "#a78bfa" }: { data: { label: string; count: number; tone?: "up" | "down" }[]; height?: number; color?: string }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#1b2533" vertical={false} />
        <XAxis dataKey="label" {...AXIS} />
        <YAxis {...AXIS} width={40} allowDecimals={false} />
        <Tooltip {...TOOLTIP} cursor={{ fill: "#141c28" }} formatter={(v) => [String(v), "Trades"]} />
        <Bar dataKey="count" isAnimationActive={false} radius={[2, 2, 0, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.tone === "up" ? "#26c281" : d.tone === "down" ? "#f0525c" : color} fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Reliability diagram: predicted vs observed frequency, with the diagonal for perfect calibration. */
export function ReliabilityChart({ bins, height = 220 }: { bins: { mean_predicted: number | null; observed_frequency: number | null; count: number }[]; height?: number }) {
  const pts = bins.filter((b) => b.mean_predicted !== null && b.observed_frequency !== null && b.count > 0).map((b) => ({ x: b.mean_predicted! * 100, y: b.observed_frequency! * 100, n: b.count }));
  const diag = [
    { x: 0, d: 0 },
    { x: 100, d: 100 },
  ];
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#1b2533" />
        <XAxis type="number" dataKey="x" domain={[0, 100]} {...AXIS} tickFormatter={(v: number) => `${v}%`} name="Predicted" />
        <YAxis type="number" domain={[0, 100]} {...AXIS} width={44} tickFormatter={(v: number) => `${v}%`} />
        <Tooltip {...TOOLTIP} formatter={(v, n) => [`${fmtNum(Number(v), 1)}%`, String(n)]} />
        <Line data={diag} dataKey="d" stroke="#536073" strokeDasharray="4 4" dot={false} isAnimationActive={false} name="Perfect calibration" />
        <Scatter data={pts} dataKey="y" fill="#22d3ee" name="Observed" isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
