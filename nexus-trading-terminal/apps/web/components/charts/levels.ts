import type { Overlays, Signal, StructureSnapshot } from "@nexus/shared-types";

import type { ChartLevel, ChartMarker } from "./price-chart";

export function signalLevels(s: Pick<Signal, "direction" | "entry_price" | "entry_zone_low" | "entry_zone_high" | "stop" | "targets">): ChartLevel[] {
  if (s.direction === "NO_TRADE") return [];
  const out: ChartLevel[] = [];
  if (s.entry_zone_low !== null && s.entry_zone_high !== null) {
    out.push({ price: s.entry_zone_high, label: "Entry zone", color: "#22d3ee", style: "dashed", fit: true });
    out.push({ price: s.entry_zone_low, label: "", color: "#22d3ee", style: "dashed", fit: true });
  } else if (s.entry_price !== null) {
    out.push({ price: s.entry_price, label: "Entry", color: "#22d3ee", width: 2, fit: true });
  }
  if (s.stop !== null) out.push({ price: s.stop, label: "Stop", color: "#f0525c", width: 2, fit: true });
  for (const t of s.targets) out.push({ price: t.price, label: t.label, color: "#26c281", style: "dashed", fit: true });
  return out;
}

export function structureLevels(st: StructureSnapshot | undefined, opts: { sr?: boolean; liquidity?: boolean; range?: boolean } = {}): ChartLevel[] {
  if (!st) return [];
  const out: ChartLevel[] = [];
  if (opts.sr !== false) {
    for (const l of st.supports.slice(0, 3)) out.push({ price: l.price, label: `S ×${l.touches}`, color: "#26c28199", style: "dotted" });
    for (const l of st.resistances.slice(0, 3)) out.push({ price: l.price, label: `R ×${l.touches}`, color: "#f0525c99", style: "dotted" });
  }
  if (opts.liquidity) {
    for (const z of st.liquidity_zones.slice(0, 4)) out.push({ price: z.price, label: `Liq${z.heuristic ? "*" : ""}`, color: "#a78bfa99", style: "dotted" });
  }
  if (opts.range && st.range.is_range && st.range.high !== null && st.range.low !== null) {
    out.push({ price: st.range.high, label: "Range hi", color: "#60a5fa99", style: "dashed" });
    out.push({ price: st.range.low, label: "Range lo", color: "#60a5fa99", style: "dashed" });
  }
  return out;
}

const toSec = (iso: string) => Math.floor(new Date(iso).getTime() / 1000);

export function structureMarkers(ov: Overlays | null | undefined, opts: { swings?: boolean; events?: boolean } = {}): ChartMarker[] {
  if (!ov) return [];
  const out: ChartMarker[] = [];
  if (opts.events !== false) {
    for (const e of ov.events) {
      const bull = e.direction === "BULLISH";
      out.push({ time: e.time, position: bull ? "belowBar" : "aboveBar", shape: "circle", color: e.type === "CHOCH" ? "#f5a524" : bull ? "#26c281" : "#f0525c", text: e.type === "CHOCH" ? "CHoCH" : "BOS" });
    }
  }
  if (opts.swings) {
    for (const s of ov.structure.swings.slice(-24)) {
      out.push({ time: toSec(s.timestamp), position: s.kind === "HIGH" ? "aboveBar" : "belowBar", shape: "square", color: "#8090a5", text: s.label });
    }
  }
  return out;
}

export function entryMarker(s: Pick<Signal, "direction" | "bar_time">): ChartMarker[] {
  if (s.direction === "NO_TRADE") return [];
  const long = s.direction === "LONG";
  return [{ time: toSec(s.bar_time), position: long ? "belowBar" : "aboveBar", shape: long ? "arrowUp" : "arrowDown", color: long ? "#26c281" : "#f0525c", text: `${s.direction} signal` }];
}
