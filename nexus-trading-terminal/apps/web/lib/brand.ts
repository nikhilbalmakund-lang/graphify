/**
 * Centralised branding. Change the product name here (or via
 * NEXT_PUBLIC_BRAND_NAME / NEXT_PUBLIC_BRAND_SHORT) - nothing else in the UI
 * hard-codes it.
 */
export const brand = {
  name: process.env.NEXT_PUBLIC_BRAND_NAME ?? "NEXUS Trading Intelligence",
  short: process.env.NEXT_PUBLIC_BRAND_SHORT ?? "NEXUS",
  tagline: "AI trading intelligence terminal",
  description: "Single-user AI trading research terminal: quant signals, AI review, backtesting and paper trading.",
} as const;
