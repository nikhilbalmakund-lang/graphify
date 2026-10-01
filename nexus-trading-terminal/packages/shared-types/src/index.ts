/**
 * NEXUS shared API types.
 *
 * Hand-maintained domain types mirroring the FastAPI responses. `api.d.ts`
 * (generated with `npm run gen:types`) contains the full OpenAPI document
 * types; the aliases below are what the web app imports.
 */

export type DataMode = "LIVE" | "DEMO" | "IMPORTED";
export type Direction = "LONG" | "SHORT" | "NO_TRADE";
export type Timeframe = "1m" | "5m" | "15m" | "30m" | "1H" | "4H" | "1D" | "1W";
export type AssetClass = "FOREX" | "CRYPTO" | "INDICES" | "COMMODITIES";
export type Regime =
  | "TRENDING_BULLISH"
  | "TRENDING_BEARISH"
  | "RANGING"
  | "BREAKOUT"
  | "HIGH_VOLATILITY"
  | "LOW_VOLATILITY"
  | "MEAN_REVERSION"
  | "UNCERTAIN";
export type ProviderStatus = "CONNECTED" | "DEMO" | "DISCONNECTED" | "ERROR" | "NOT_CONFIGURED" | "CONFIGURED_UNVERIFIED" | "OK";
export type Impact = "LOW" | "MEDIUM" | "HIGH";
export type SentimentLabel = "BULLISH" | "BEARISH" | "NEUTRAL" | "UNCERTAIN";

export interface ApiErrorBody {
  error: { code: string; message: string; request_id?: string | null; details?: Record<string, unknown> | null };
}

export interface ModeMeta {
  mode: DataMode;
  provider: string;
  is_demo: boolean;
}

export interface Asset {
  symbol: string;
  name: string;
  asset_class: AssetClass;
  session: string;
  price_precision: number;
  pip_size: number;
  contract_size: number;
  min_lot: number;
  lot_step: number;
  max_leverage: number;
  typical_spread: number;
  currencies: string[];
  market_open: boolean;
  market_status: string;
}

export interface Quote {
  symbol: string;
  bid: number;
  ask: number;
  price: number;
  timestamp: string;
  provider: string;
  is_demo: boolean;
  change_24h: number | null;
  change_pct_24h: number | null;
  market_open: boolean;
  spread_is_estimate: boolean;
}

export interface DataIssue {
  code: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  count: number;
  detail: string;
}

export interface DataQualityReport {
  symbol: string;
  timeframe: string;
  provider: string;
  is_demo: boolean;
  bars: number;
  issues: DataIssue[];
  missing_bars: number;
  duplicate_bars: number;
  invalid_rows: number;
  is_stale: boolean;
  market_open: boolean;
  usable: boolean;
  quality_score: number;
  last_bar_age_seconds: number | null;
}

/** [unix_seconds, open, high, low, close, volume] */
export type Bar = [number, number, number, number, number, number];

export interface Candles {
  symbol: string;
  timeframe: Timeframe;
  bars: Bar[];
  last_bar_complete: boolean;
  volume_available: boolean;
  data_quality: DataQualityReport;
  price_precision: number;
  mode: DataMode;
  provider: string;
  is_demo: boolean;
}

export interface OverviewCard {
  symbol: string;
  status: "OK" | "ERROR";
  error?: string;
  name?: string;
  asset_class?: AssetClass;
  price?: number;
  bid?: number;
  ask?: number;
  change_24h?: number | null;
  change_pct_24h?: number | null;
  market_open?: boolean;
  trend?: "BULLISH" | "BEARISH" | "NEUTRAL";
  trend_score?: number | null;
  momentum_score?: number | null;
  atr_pct?: number | null;
  vol_percentile?: number | null;
  regime?: Regime;
  regime_clarity?: number;
  sparkline?: number[];
  timeframe?: string;
  price_precision?: number;
  data_quality?: number;
  is_demo?: boolean;
  provider?: string;
}

export interface FeatureSnapshot {
  feature_version: string;
  timestamp: string;
  close: number;
  [key: string]: number | string | boolean | null;
}

export interface Level {
  price: number;
  kind: "SUPPORT" | "RESISTANCE";
  touches: number;
  last_touch: string;
  strength: number;
  distance_atr: number | null;
}

export interface LiquidityZone {
  kind: string;
  price: number;
  touches: number;
  heuristic: boolean;
  note: string;
}

export interface SwingPoint {
  timestamp: string;
  price: number;
  kind: "HIGH" | "LOW";
  label: string;
}

export interface StructureSnapshot {
  trend: "BULLISH" | "BEARISH" | "NEUTRAL";
  last_swing_high: SwingPoint | null;
  last_swing_low: SwingPoint | null;
  recent_labels: string[];
  last_event: { type: "BOS" | "CHOCH"; direction: string; level: number | null; timestamp: string; bars_ago: number } | null;
  supports: Level[];
  resistances: Level[];
  range: { is_range: boolean; high: number | null; low: number | null; height_atr: number | null };
  breakout: { direction: string; level: number; timestamp: string; bars_ago: number; retested: boolean; failed: boolean } | null;
  sweep: { direction: string; level: number; timestamp: string; bars_ago: number; heuristic: boolean } | null;
  liquidity_zones: LiquidityZone[];
  swings: SwingPoint[];
  heuristic_note: string;
}

export interface RegimeResult {
  regime: Regime;
  clarity: number;
  flags: Regime[];
  evidence: Record<string, number | null>;
  explanation: string;
  version: string;
}

export interface TimeframeView {
  timeframe: string;
  available: boolean;
  note: string;
  close: number | null;
  trend: "BULLISH" | "BEARISH" | "NEUTRAL";
  direction_value: number;
  trend_score: number | null;
  momentum_score: number | null;
  structure_trend: string;
  regime: string | null;
  atr_pct: number | null;
  vol_percentile: number | null;
  rsi14: number | null;
  vwap_relation: string;
  nearest_support: number | null;
  nearest_resistance: number | null;
}

export interface MTFAnalysis {
  views: TimeframeView[];
  alignment: number;
  bullish_weight: number;
  bearish_weight: number;
  dominant: string;
  summary: string;
}

export interface Overlays extends ModeMeta {
  symbol: string;
  timeframe: string;
  lines: Record<string, [number, number][]>;
  panes: Record<string, [number, number][]>;
  structure: StructureSnapshot;
  events: { time: number; type: string; direction: string }[];
}

export interface Target {
  label: string;
  price: number;
  rr: number;
  basis: string;
  allocation: number;
}

export interface ScoreComponent {
  name: string;
  weight: number;
  points: number;
  raw: number;
  notes_for: string[];
  notes_against: string[];
}

export interface FilterResult {
  name: string;
  passed: boolean;
  blocking: boolean;
  detail: string;
  value: number | string | null;
  threshold: number | string | null;
}

export interface HistoricalEvidence {
  sample_size: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  avg_r: number | null;
  expectancy: number | null;
  max_drawdown_r: number | null;
  sample_label: "NONE" | "INSUFFICIENT" | "SMALL" | "MODERATE" | "LARGE";
  is_demo: boolean;
  notes: string[];
}

export interface RiskCheck {
  name: string;
  passed: boolean;
  detail: string;
  value: number | string | null;
  limit: number | string | null;
}

export interface RiskDecision {
  approved: boolean;
  state: "NORMAL" | "RESTRICTED" | "HALTED";
  checks: RiskCheck[];
  lots: number;
  risk_amount: number;
  risk_pct: number;
  notional: number;
  margin_required: number;
  leverage_after: number;
  sizing_method: string;
  sizing_notes: string[];
  reasons: string[];
  engine_version: string;
}

export interface SignalOutcome {
  status: string;
  filled: boolean;
  fill_time: string | null;
  fill_price: number | null;
  exit_time: string | null;
  exit_reason: string | null;
  r_multiple: number | null;
  mfe_r: number | null;
  mae_r: number | null;
  tp_hits: string[];
  resolved: boolean;
  updated_at: string;
}

export interface AISummary {
  agreement: string;
  directions?: Record<string, string>;
  critic?: string | null;
  critic_reasons?: string[];
  downgraded?: boolean;
  reasons?: string[];
  notes?: string[];
  note?: string;
  claude_status?: string;
  gemini_status?: string;
}

export interface Signal {
  id: string;
  symbol: string;
  timeframe: Timeframe;
  created_at: string;
  bar_time: string;
  direction: Direction;
  proposed_direction: Direction;
  status: string;
  score: number;
  score_long: number;
  score_short: number;
  regime: Regime;
  price: number;
  entry_type: "MARKET" | "LIMIT" | "ZONE" | null;
  entry_price: number | null;
  entry_zone_low: number | null;
  entry_zone_high: number | null;
  stop: number | null;
  invalidation_level: number | null;
  invalidation_text: string | null;
  targets: Target[];
  rr: number | null;
  effective_rr: number | null;
  expires_at: string | null;
  expiry_bars: number;
  supporting: string[];
  opposing: string[];
  no_trade_reasons: string[];
  components: ScoreComponent[];
  mtf_adjustment: number;
  filters: FilterResult[];
  evidence: HistoricalEvidence | null;
  ai_summary: AISummary | null;
  risk_decision: RiskDecision | null;
  calibrated_probability: number | null;
  ensemble: {
    net_direction: Direction;
    agreement: number;
    conflict: boolean;
    supporting: string[];
    opposing: string[];
    summary: string;
    votes: { strategy: string; direction: Direction; strength: number; applicable: boolean; reasons: string[] }[];
  } | null;
  data_mode: DataMode;
  provider: string;
  is_demo: boolean;
  source: string;
  versions: { signal_engine: string; features: string; risk_engine: string | null; strategies: Record<string, string>; prompts: Record<string, string>; models: Record<string, string> };
  outcome: SignalOutcome | null;
}

export interface AIAnalysisRow {
  role: "claude_analyst" | "gemini_analyst" | "critic" | "consensus";
  provider: string;
  model: string | null;
  prompt_name: string | null;
  prompt_version: string | null;
  prompt_date: string | null;
  settings: Record<string, unknown>;
  status: string;
  output: Record<string, unknown> | null;
  validation: { valid: boolean; issues: { code: string; severity: string; detail: string }[]; unsupported_prices: number[] } | null;
  error: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
  latency_ms: number | null;
  created_at: string;
}

export interface SignalDetail extends Signal {
  analysis: {
    features: FeatureSnapshot;
    structure: StructureSnapshot;
    mtf: MTFAnalysis;
    regime: RegimeResult;
    data_quality: DataQualityReport;
    context: Record<string, Record<string, unknown>>;
  } | null;
  ai_analyses: AIAnalysisRow[];
}

export interface ScannerRow {
  symbol: string;
  status: "OK" | "ERROR";
  error?: string;
  signal_id: string;
  price: number;
  change_pct_24h: number | null;
  trend: string;
  trend_score: number | null;
  regime: Regime;
  score: number;
  direction: Direction;
  proposed_direction: Direction;
  signal_status: string;
  rr: number | null;
  vol_percentile: number | null;
  news_risk: boolean;
  next_event: string | null;
  next_event_minutes: number | null;
  risk: "HIGH" | "ELEVATED" | "NORMAL";
  no_trade_reasons: string[];
  is_demo: boolean;
}

export interface NewsItem {
  id: string;
  headline: string;
  summary: string | null;
  source: string;
  url: string | null;
  published_at: string;
  symbols: string[];
  countries: string[];
  sentiment: SentimentLabel | null;
  sentiment_source: string | null;
  sentiment_rationale: string | null;
  importance: Impact;
  provider: string;
  is_demo: boolean;
}

export interface EconomicEvent {
  id: string;
  event: string;
  currency: string;
  country: string;
  time: string;
  impact: Impact;
  previous: string | null;
  forecast: string | null;
  actual: string | null;
  source: string;
  provider: string;
  is_demo: boolean;
  minutes_until: number;
}

export interface TakeProfit {
  price: number;
  fraction: number;
  label: string;
}

export interface PaperAccount {
  id: string;
  name: string;
  currency: string;
  starting_balance: number;
  balance: number;
  equity: number;
  margin_used: number;
  free_margin: number;
  unrealized_pnl: number;
  peak_equity: number;
  day_start_equity: number;
  week_start_equity: number;
  kill_switch: boolean;
  max_leverage: number;
  is_paper: boolean;
}

export interface Position {
  id: string;
  symbol: string;
  direction: number;
  lots: number;
  initial_lots: number;
  entry_price: number;
  stop_loss: number | null;
  initial_stop: number | null;
  take_profits: TakeProfit[];
  status: "OPEN" | "CLOSED";
  opened_at: string;
  closed_at: string | null;
  exit_price: number | null;
  exit_reason: string | null;
  realized_pnl: number;
  fees: number;
  risk_usd: number | null;
  signal_id: string | null;
  strategy: string | null;
  regime: string | null;
  source: string;
  current_price: number | null;
  unrealized_pnl: number;
  is_paper: boolean;
}

export interface Order {
  id: string;
  symbol: string;
  side: "BUY" | "SELL";
  type: "MARKET" | "LIMIT" | "STOP";
  lots: number;
  price: number | null;
  stop_loss: number | null;
  take_profits: TakeProfit[];
  status: "PENDING" | "FILLED" | "CANCELLED" | "REJECTED" | "EXPIRED";
  created_at: string;
  filled_at: string | null;
  fill_price: number | null;
  expires_at: string | null;
  reject_reason: string | null;
  signal_id: string | null;
  source: string;
  position_id: string | null;
  is_paper: boolean;
}

export interface Fill {
  id: string;
  order_id: string | null;
  position_id: string;
  symbol: string;
  side: "BUY" | "SELL";
  lots: number;
  price: number;
  fee: number;
  slippage: number;
  reason: string;
  timestamp: string;
  realized_pnl: number;
}

export interface RiskStatus {
  state: "NORMAL" | "RESTRICTED" | "HALTED";
  kill_switch: boolean;
  equity: number;
  drawdown: number;
  daily_pnl: number;
  daily_loss_used: number;
  weekly_pnl: number;
  weekly_loss_used: number;
  open_positions: number;
  open_risk_usd: number;
  gross_exposure: number;
  leverage: number;
  limits: Record<string, number | string | boolean>;
  messages: string[];
  live_trading?: { allowed: boolean; reasons: string[] };
}

export interface PaperOverview {
  label: string;
  account: PaperAccount;
  positions: Position[];
  closed_positions: Position[];
  orders: Order[];
  fills: Fill[];
  risk: RiskStatus;
  is_demo_prices: boolean;
}

export interface PeriodPnl {
  period: string;
  pnl: number;
  trades: number;
}

export interface GroupStats {
  key: string;
  trades: number;
  pnl: number;
  win_rate: number | null;
  expectancy_r: number | null;
}

export interface PerformanceReport {
  trades: number;
  win_rate: number | null;
  expectancy: number | null;
  expectancy_r: number | null;
  total_pnl: number;
  max_drawdown: number;
  daily: PeriodPnl[];
  weekly: PeriodPnl[];
  monthly: PeriodPnl[];
  by_strategy: GroupStats[];
  by_asset: GroupStats[];
  by_regime: GroupStats[];
  r_distribution: Record<string, number>;
  sample_note: string;
}

export interface Portfolio {
  label: string;
  is_demo_prices: boolean;
  account: PaperAccount;
  summary: {
    balance: number;
    equity: number;
    cash: number;
    margin_used: number;
    free_margin: number;
    open_pnl: number;
    closed_pnl: number;
    daily_pnl: number;
    weekly_pnl: number;
    drawdown: number;
    peak_equity: number;
  };
  positions: Position[];
  exposure: { symbol: string; notional: number }[];
  equity_curve: { ts: string; equity: number; balance: number; drawdown: number }[];
  performance: PerformanceReport;
  risk: RiskStatus;
}

export interface JournalEntry {
  id: string;
  entry_type: "SIGNAL" | "PAPER_TRADE" | "MANUAL_TRADE";
  symbol: string;
  timeframe: string | null;
  direction: "LONG" | "SHORT";
  strategy: string | null;
  regime: string | null;
  signal_score: number | null;
  entry_time: string;
  exit_time: string | null;
  entry_price: number | null;
  exit_price: number | null;
  stop: number | null;
  lots: number | null;
  fees: number;
  slippage: number;
  pnl: number | null;
  r_multiple: number | null;
  duration_seconds: number | null;
  mfe_r: number | null;
  mae_r: number | null;
  result: string;
  ai_reasoning: Record<string, unknown> | null;
  notes: string | null;
  tags: string[];
  signal_id: string | null;
  position_id: string | null;
  is_demo: boolean;
}

export interface Metrics {
  total_trades: number;
  wins: number;
  losses: number;
  breakeven: number;
  win_rate: number | null;
  profit_factor: number | null;
  expectancy: number | null;
  expectancy_r: number | null;
  average_r: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  gross_profit: number;
  gross_loss: number;
  net_profit: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  max_drawdown_abs: number;
  sharpe: number | null;
  sortino: number | null;
  cagr_pct: number | null;
  volatility_pct: number | null;
  exposure_pct: number | null;
  largest_win: number | null;
  largest_loss: number | null;
  longest_losing_streak: number;
  longest_winning_streak: number;
  avg_bars_held: number | null;
  start_equity: number;
  end_equity: number;
  years: number | null;
}

export interface MetricsBundle {
  metrics: Metrics;
  monthly_returns: Record<string, number>;
  losing_periods: { start: string; trough: string; end: string | null; depth_pct: number; duration_bars: number; recovered: boolean }[];
  by_regime: { regime: string; trades: number; win_rate: number | null; average_r: number | null; profit_factor: number | null; net_profit: number }[];
  r_distribution: Record<string, number>;
}

export interface BacktestSummary {
  id: string;
  kind: "BACKTEST" | "WALK_FORWARD";
  strategy: string;
  strategy_version: string;
  symbol: string;
  timeframe: string;
  params: Record<string, unknown>;
  status: string;
  metrics: Metrics | null;
  is_demo: boolean;
  provider: string;
  data_label: string;
  warnings: string[];
  error: string | null;
  created_at: string;
  duration_ms: number | null;
  engine_version: string;
}

export interface BacktestTradeRow {
  trade_no: number;
  direction: "LONG" | "SHORT";
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  lots: number;
  pnl: number;
  pnl_r: number | null;
  fees: number;
  exit_reason: string;
  regime: string | null;
  bars_held: number;
  mfe_r: number | null;
  mae_r: number | null;
}

export interface WalkForwardWindow {
  window: number;
  chosen_params: Record<string, unknown>;
  train: { start: string; end: string; bars: number; metrics: Metrics };
  validation: { start: string; end: string; bars: number; metrics: Metrics };
  test: { start: string; end: string; bars: number; metrics: Metrics };
  candidates_evaluated: number;
}

export interface BacktestDetail extends BacktestSummary {
  config: Record<string, unknown>;
  result: {
    metrics?: MetricsBundle;
    equity_curve?: [string, number][];
    drawdown_curve?: [string, number][];
    trade_start?: string;
    trade_end?: string;
    bars?: number;
    windows?: WalkForwardWindow[];
    oos_metrics?: MetricsBundle;
    oos_equity_curve?: [string, number][];
    overfitting?: { suspicious: boolean; summary: string; flags: { code: string; severity: string; detail: string }[] };
    walk_forward_config?: Record<string, unknown>;
  } | null;
  trades: BacktestTradeRow[];
}

export interface StrategyInfo {
  name: string;
  version: string;
  description: string;
  regimes: string[];
  params: Record<string, unknown>;
  grid: Record<string, unknown[]>;
}

export interface CalibrationReport {
  model_name: string;
  model_version: string;
  status: "CALIBRATED" | "NOT_CALIBRATED" | "INSUFFICIENT_DATA";
  trained_at: string;
  data_mode: string;
  label_definition: string;
  n_total: number;
  n_train: number;
  n_calibration: number;
  n_test: number;
  base_rate: number | null;
  brier: number | null;
  brier_baseline: number | null;
  brier_skill: number | null;
  ece: number | null;
  auc: number | null;
  reliability: { lower: number; upper: number; mean_predicted: number | null; observed_frequency: number | null; count: number }[];
  challenger: { name: string; brier: number; ece: number; auc: number | null } | null;
  reasons: string[];
  test_period: [string, string] | null;
}

export interface ToolTrace {
  name: string;
  arguments: Record<string, unknown>;
  ok: boolean;
  summary: string;
  duration_ms: number;
}

export interface ChatAnswer {
  summary: string;
  facts: string[];
  calculations: string[];
  interpretation: string[];
  uncertainty: string[];
}

export interface ChatResponse {
  answer: ChatAnswer;
  tool_trace: ToolTrace[];
  provider: string;
  model: string;
  is_ai: boolean;
  warnings: string[];
  is_demo_data: boolean;
}

export interface Briefing {
  id: string;
  session: string;
  created_at: string;
  provider: string;
  model: string;
  is_ai: boolean;
  is_demo_data: boolean;
  content: {
    theme: string;
    strongest_trends: string[];
    volatility: string;
    major_risks: string[];
    upcoming_events: string[];
    assets_to_monitor: string[];
    facts: string[];
    interpretation: string[];
    uncertainty: string[];
    warnings?: string[];
  };
  prompt_version: string | null;
}

export interface ScenarioCase {
  name: "BULLISH" | "BEARISH" | "NO_TRADE";
  trigger: string;
  confirmation: string;
  invalidation: string;
  trigger_level: number | null;
  invalidation_level: number | null;
  targets: number[];
  notes: string;
}

export interface ResearchResult {
  symbol: string;
  timeframe: string;
  report: {
    market_overview: string;
    technical_analysis: string[];
    macro_context: string[];
    risks: string[];
    historical_evidence: string[];
    scenarios: { name: string; trigger: string; confirmation: string; invalidation: string; notes: string }[];
    uncertainty: string[];
  };
  provider: string;
  model: string;
  is_ai: boolean;
  is_demo_data: boolean;
  scenarios: { scenarios: ScenarioCase[]; basis: string };
  warnings: string[];
  generated_at: string;
}

export interface ConditionsSummary {
  sample_size: number;
  sample_label: string;
  outcomes: Record<string, number>;
  average_r: number | null;
  median_r: number | null;
  r_quantiles: Record<string, number>;
  regimes: Record<string, number>;
  directions: Record<string, number>;
  first: string | null;
  last: string | null;
  caveats: string[];
}

export interface ComponentStatus {
  name: string;
  status: ProviderStatus;
  detail: string;
  provider: string | null;
  latency_ms: number | null;
}

export interface SystemStatus {
  app_name: string;
  version: string;
  mode: DataMode;
  trading_mode: string;
  live_trading: { env_enabled: boolean; ui_switch_on: boolean; broker: string; allowed: boolean; reasons: string[] };
  components: ComponentStatus[];
  versions: Record<string, string>;
  background: Record<string, { interval_s: number | null; runs: number; errors: number; last_run: string | null; last_error: string | null }>;
  memory: { state: string; built?: { key: string; records: number }[]; pending?: string[]; errors?: { key: string; error: string }[] };
  server_time: string;
}

export interface NotificationItem {
  id: number;
  ts: string;
  type: string;
  title: string;
  body: string;
  severity: "INFO" | "WARNING" | "ERROR";
  symbol: string | null;
  signal_id: string | null;
  is_demo: boolean;
  read: boolean;
}

export interface AlertItem {
  id: string;
  type: string;
  symbol: string | null;
  condition: Record<string, unknown>;
  enabled: boolean;
  note: string | null;
  cooldown_minutes: number;
  last_triggered_at: string | null;
  created_at: string;
}

export interface SecretStatus {
  key: string;
  configured: boolean;
  hint: string | null;
}

export interface SettingsPayload {
  settings: Record<string, Record<string, unknown>>;
  secrets: SecretStatus[];
  providers: Record<string, string>;
  live_trading: { env_enabled: boolean; ui_switch_on: boolean; broker: string; allowed: boolean; reasons: string[] };
  app: { name: string; short_name: string };
}

export interface LiveMessage<T = unknown> {
  topic: "quotes" | "signals" | "notifications" | "paper" | "system" | "backtests";
  ts?: string;
  data: T;
}
