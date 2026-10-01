import type { AssetClass, Timeframe } from "@nexus/shared-types";

export const TIMEFRAMES: Timeframe[] = ["1m", "5m", "15m", "30m", "1H", "4H", "1D", "1W"];
export const ANALYSIS_TIMEFRAMES: Timeframe[] = ["1m", "5m", "15m", "30m", "1H", "4H", "1D"];
export const ASSET_CLASSES: AssetClass[] = ["FOREX", "CRYPTO", "INDICES", "COMMODITIES"];
export const DEFAULT_SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "ETHUSD", "NAS100", "US30", "SPX500", "USOIL"];

export const SYMBOL_NAMES: Record<string, string> = {
  XAUUSD: "Gold",
  EURUSD: "Euro / US Dollar",
  GBPUSD: "Pound / US Dollar",
  USDJPY: "US Dollar / Yen",
  BTCUSD: "Bitcoin",
  ETHUSD: "Ether",
  NAS100: "Nasdaq 100",
  US30: "Dow Jones 30",
  SPX500: "S&P 500",
  USOIL: "WTI Crude Oil",
};

export const ASSET_CLASS_OF: Record<string, AssetClass> = {
  XAUUSD: "COMMODITIES",
  USOIL: "COMMODITIES",
  EURUSD: "FOREX",
  GBPUSD: "FOREX",
  USDJPY: "FOREX",
  BTCUSD: "CRYPTO",
  ETHUSD: "CRYPTO",
  NAS100: "INDICES",
  US30: "INDICES",
  SPX500: "INDICES",
};

export const PRECISION: Record<string, number> = {
  XAUUSD: 2, EURUSD: 5, GBPUSD: 5, USDJPY: 3, BTCUSD: 2, ETHUSD: 2, NAS100: 1, US30: 1, SPX500: 2, USOIL: 2,
};

export const REGIME_LABEL: Record<string, string> = {
  TRENDING_BULLISH: "Trending Bullish",
  TRENDING_BEARISH: "Trending Bearish",
  RANGING: "Ranging",
  BREAKOUT: "Breakout",
  HIGH_VOLATILITY: "High Volatility",
  LOW_VOLATILITY: "Low Volatility",
  MEAN_REVERSION: "Mean Reversion",
  UNCERTAIN: "Uncertain",
};
