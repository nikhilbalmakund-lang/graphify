import { PRECISION } from "./constants";

const NBSP = " ";

export function fmtPrice(v: number | null | undefined, symbolOrDigits?: string | number): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const digits = typeof symbolOrDigits === "number" ? symbolOrDigits : (symbolOrDigits ? PRECISION[symbolOrDigits] : undefined) ?? 2;
  return v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtPct(v: number | null | undefined, digits = 2, signed = true): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const s = v.toFixed(digits);
  return `${signed && v > 0 ? "+" : ""}${s}%`;
}

/** Fraction (0.0123) as percent string. */
export function fmtFrac(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function fmtMoney(v: number | null | undefined, digits = 2, signed = false): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const abs = Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  const sign = v < 0 ? "-" : signed && v > 0 ? "+" : "";
  return `${sign}$${abs}`;
}

export function fmtR(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}R`;
}

export function fmtRR(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `1${NBSP}:${NBSP}${v.toFixed(2)}`;
}

export function fmtTime(iso: string | null | undefined, withDate = false): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const time = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
  if (!withDate) return `${time}`;
  const date = d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", timeZone: "UTC" });
  return `${date} ${time}`;
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return `${d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" })} ${d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" })} UTC`;
}

export function timeAgo(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "—";
  const diff = Math.round((now - new Date(iso).getTime()) / 1000);
  if (Number.isNaN(diff)) return "—";
  const abs = Math.abs(diff);
  const unit = abs < 60 ? `${abs}s` : abs < 3600 ? `${Math.floor(abs / 60)}m` : abs < 86400 ? `${Math.floor(abs / 3600)}h` : `${Math.floor(abs / 86400)}d`;
  return diff >= 0 ? `${unit} ago` : `in ${unit}`;
}

/** "1h 20m" style countdown from minutes. */
export function fmtCountdown(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined || Number.isNaN(minutes)) return "—";
  if (minutes < 0) return `${fmtCountdown(-minutes)} ago`;
  const m = Math.floor(minutes);
  const d = Math.floor(m / 1440);
  const h = Math.floor((m % 1440) / 60);
  const mm = m % 60;
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${mm}m`;
  return `${mm}m`;
}

export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  return fmtCountdown(seconds / 60);
}

export function toneOf(v: number | null | undefined): "up" | "down" | "flat" {
  if (v === null || v === undefined || Number.isNaN(v) || v === 0) return "flat";
  return v > 0 ? "up" : "down";
}

export function titleCase(s: string | null | undefined): string {
  if (!s) return "—";
  return s
    .toLowerCase()
    .split(/[_\s]+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}
