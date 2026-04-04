export type MarketRegime = "risk_on" | "neutral" | "risk_off";
export type SignalLevel = "强信号" | "观察信号" | "无信号";
export type Bias = "逢高做空" | "逢低做多";

export interface MarketRegimeResult {
  regime: MarketRegime;
  reasons: string[];
  qqq_price: number;
  vix_price: number;
  timestamp: string;
}

export interface Signal {
  symbol: string;
  bias: Bias;
  level: SignalLevel;
  action: string;
  rationale: string[];
  price: number;
  trigger_price: number;
  option_structure: string;
  option_hint: string;
  timestamp: string;
  score: number;
}

export interface FullScanResponse {
  regime: MarketRegimeResult;
  signals: Signal[];
  timestamp: string;
}

export interface IndicatorSnapshot {
  symbol: string;
  price: number;
  sma5: number | null;
  sma10: number | null;
  atr14: number | null;
  vwap: number | null;
  prev_high: number | null;
  prev_low: number | null;
  rolling_high_20: number | null;
  rolling_low_20: number | null;
  range_position: number | null;
}

export interface OHLCVBar {
  date: string;
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PaginatedOHLCV {
  data: OHLCVBar[];
  total: number;
  offset: number;
  limit: number;
}

export interface SymbolInfo {
  symbol: string;
  has_daily: boolean;
  daily_rows: number;
  last_date: string;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
  data_status: Record<string, boolean>;
  version: string;
}

export interface CompareBar {
  date: string;
  time: number;
  close: number;
}

export type CompareResponse = Record<string, CompareBar[]>;

// ── Options & Backtest types ────────────────────────────────────────

export type StrategyType =
  | "short_call_spread"
  | "long_put_spread"
  | "short_calls"
  | "short_puts"
  | "long_calls"
  | "long_puts"
  | "long_call_spread"
  | "short_put_spread"
  | "iron_condor"
  | "straddle";

export interface BacktestRequest {
  symbol: string;
  strategy: StrategyType;
  max_entry_dte: number;
  exit_dte: number;
  leg1_delta: number;
  leg2_delta: number;
  capital: number;
  quantity: number;
  max_positions: number;
  commission_per_contract: number;
  stop_loss: number | null;
  take_profit: number | null;
  max_expirations: number;
}

export interface BacktestMetrics {
  total_trades: number;
  win_rate: number;
  mean_return: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  profit_factor: number;
  calmar_ratio: number;
  final_equity: number;
}

export interface BacktestResponse {
  symbol: string;
  strategy: string;
  metrics: BacktestMetrics;
  equity_curve: number[];
  trade_count: number;
  error: string | null;
  timestamp: string;
}

export interface OptionsChainSummary {
  symbol: string;
  expirations: string[];
  total_contracts: number;
  calls_count: number;
  puts_count: number;
}

export interface OptionsContract {
  option_type: "c" | "p";
  expiration: string;
  strike: number;
  bid: number;
  ask: number;
  volume: number;
  open_interest: number;
  implied_volatility: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

export interface OptionsChainDetail {
  symbol: string;
  expirations: string[];
  total_contracts: number;
  calls_count: number;
  puts_count: number;
  contracts: OptionsContract[];
}

// ── Greeks Calculator types ─────────────────────────────────────────

export interface GreeksRequest {
  spot: number;
  strike: number;
  dte_days: number;
  risk_free_rate: number;
  iv: number;
  option_type: "call" | "put";
}

export interface GreeksResponse {
  price: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

// ── IV Analysis types ───────────────────────────────────────────────

export interface IVSkewPoint {
  strike: number;
  implied_volatility: number;
  option_type: "c" | "p";
  moneyness: number;
}

export interface IVTermPoint {
  expiration: string;
  dte_days: number;
  atm_iv: number;
}

export interface HVPoint {
  window_days: number;
  realized_vol: number;
  label: string;
}

export interface IVAnalysisResponse {
  symbol: string;
  spot_price: number;
  current_atm_iv: number;
  iv_rank: number;
  iv_percentile: number;
  iv_high_52w: number;
  iv_low_52w: number;
  skew_points: IVSkewPoint[];
  put_call_skew: number;
  term_structure: IVTermPoint[];
  hv_points: HVPoint[];
  iv_rv_spread: number;
  error: string | null;
}

// ── Multi-leg Strategy types ────────────────────────────────────────

export interface OptionLegInput {
  option_type: "c" | "p";
  action: "buy" | "sell";
  strike: number;
  expiration: string;
  quantity: number;
  premium: number;
  iv: number;
}

export interface MultiLegRequest {
  legs: OptionLegInput[];
  spot: number;
  dte_days: number;
  risk_free_rate: number;
}

export interface PnLPoint {
  price: number;
  pnl: number;
}

export interface AggregatedGreeks {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

export interface MultiLegResponse {
  net_debit_credit: number;
  max_profit: number;
  max_loss: number;
  breakeven_points: number[];
  greeks: AggregatedGreeks;
  pnl_curve: PnLPoint[];
  error: string | null;
}

// ── Position management types ───────────────────────────────────────

export interface PositionCreate {
  symbol: string;
  option_type: "call" | "put";
  strike: number;
  expiration: string; // YYYY-MM-DD
  quantity: number; // positive=long, negative=short
  entry_price: number;
  entry_date?: string;
  entry_commission?: number;
  strategy_name?: string;
  tags?: string;
  notes?: string;
}

export interface PositionUpdate {
  notes?: string;
  tags?: string;
  strategy_name?: string;
  entry_price?: number;
  entry_commission?: number;
  quantity?: number;
}

export interface PositionClose {
  exit_price: number;
  exit_commission?: number;
  exit_date?: string;
}

export interface PositionResponse {
  id: string;
  symbol: string;
  option_type: string;
  strike: number;
  expiration: string;
  quantity: number;
  entry_price: number;
  entry_date: string;
  entry_commission: number;
  exit_price: number | null;
  exit_date: string | null;
  exit_commission: number;
  status: "open" | "closed" | "expired";
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
  strategy_name: string | null;
  tags: string;
  notes: string;
  created_at: string;
  updated_at: string;
  unrealized_pnl: number | null;
  realized_pnl: number | null;
  total_cost: number | null;
}

export interface PortfolioSummaryResponse {
  total_positions: number;
  open_positions: number;
  closed_positions: number;
  expired_positions: number;
  total_unrealized_pnl: number;
  total_realized_pnl: number;
  total_cost: number;
  greeks: AggregatedGreeks;
}

export interface StrategyGroupResponse {
  strategy_name: string;
  position_count: number;
  open_count: number;
  total_realized_pnl: number;
  positions: PositionResponse[];
}

// ── ML Enhancement types ────────────────────────────────────────────

export interface EnhancedSignal {
  symbol: string;
  bias: Bias;
  level: SignalLevel;
  action: string;
  rationale: string[];
  price: number;
  trigger_price: number;
  option_structure: string;
  option_hint: string;
  timestamp: string;
  score: number;
  ml_confidence: number;
  ml_regime: MarketRegime;
  regime_probabilities: Record<string, number>;
  feature_importance: Record<string, number>;
  combined_score: number;
}

export interface MLRegimeResponse {
  regime: string;
  probabilities: Record<string, number>;
  state: number;
  source: string;
}

export interface TrainingStatusResponse {
  last_trained: string | null;
  regime_metrics: Record<string, unknown>;
  scorer_metrics: Record<string, unknown>;
  symbols_trained: string[];
  error: string | null;
  regime_model_available: boolean;
  scorer_model_available: boolean;
}

// ── Signal Backtest types ───────────────────────────────────────────

export interface SignalBacktestRequest {
  symbol: string;
  start_date?: string;
  end_date?: string;
  horizons?: number[];
}

export interface SignalOutcome {
  date: string;
  signal_level: string;
  bias: string;
  score: number;
  price: number;
  returns: Record<string, number>;
  hit: Record<string, boolean>;
}

export interface HorizonBreakdown {
  horizon: string;
  total_signals: number;
  hits: number;
  hit_rate: number;
  avg_return: number;
  strong_signals: number;
  strong_hits: number;
  strong_hit_rate: number;
  watch_signals: number;
  watch_hits: number;
  watch_hit_rate: number;
}

export interface RegimeBreakdown {
  regime: string;
  total_signals: number;
  hit_rate: number;
  avg_return: number;
}

export interface SignalBacktestMetrics {
  total_days: number;
  signal_days: number;
  strong_days: number;
  watch_days: number;
  none_days: number;
  overall_hit_rate: number;
  avg_return: number;
  profit_factor: number;
  max_drawdown: number;
  sharpe: number;
  by_horizon: HorizonBreakdown[];
  by_regime: RegimeBreakdown[];
}

export interface SignalBacktestResponse {
  symbol: string;
  start_date: string;
  end_date: string;
  metrics: SignalBacktestMetrics;
  outcomes: SignalOutcome[];
  equity_curve: number[];
  error: string | null;
  timestamp: string;
}

export interface WalkForwardRequest {
  symbol: string;
  train_days?: number;
  test_days?: number;
  step_days?: number;
  horizon?: number;
}

export interface WalkForwardWindow {
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  in_sample_hit_rate: number;
  out_of_sample_hit_rate: number;
  out_of_sample_return: number;
}

export interface WalkForwardResponse {
  symbol: string;
  windows: WalkForwardWindow[];
  avg_oos_hit_rate: number;
  avg_oos_return: number;
  stability_ratio: number;
  error: string | null;
  timestamp: string;
}

// ── Broker / Trading types ──────────────────────────────────────────

export type OrderSide = "buy" | "sell";
export type OrderType = "market" | "limit" | "stop" | "stop_limit";
export type TimeInForce = "day" | "gtc" | "ioc" | "fok";
export type OrderStatus =
  | "new"
  | "accepted"
  | "partially_filled"
  | "filled"
  | "done_for_day"
  | "canceled"
  | "expired"
  | "replaced"
  | "rejected"
  | "pending_new"
  | "pending_cancel"
  | "pending_replace";

export interface CreateOrderRequest {
  symbol: string;
  side: OrderSide;
  order_type: OrderType;
  time_in_force: TimeInForce;
  qty: number | null;
  notional: number | null;
  limit_price: number | null;
  stop_price: number | null;
}

export interface OrderResponse {
  id: string;
  symbol: string;
  side: string;
  order_type: string;
  time_in_force: string;
  qty: string | null;
  notional: string | null;
  limit_price: string | null;
  stop_price: string | null;
  filled_qty: string | null;
  filled_avg_price: string | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
  submitted_at: string | null;
  filled_at: string | null;
  expired_at: string | null;
  canceled_at: string | null;
}

export interface AccountInfoResponse {
  id: string;
  status: string;
  cash: number;
  equity: number;
  portfolio_value: number;
  buying_power: number;
  long_market_value: number;
  short_market_value: number;
  pattern_day_trader: boolean;
  trading_blocked: boolean;
  transfers_blocked: boolean;
  currency: string;
}

export interface BrokerPositionResponse {
  symbol: string;
  qty: string;
  side: string;
  market_value: string | null;
  avg_entry_price: string | null;
  current_price: string | null;
  unrealized_pl: string | null;
  unrealized_plpc: string | null;
  cost_basis: string | null;
  change_today: string | null;
}

export interface ClosePositionRequest {
  qty: number | null;
  percentage: number | null;
}

export interface PortfolioHistoryRequest {
  period: string;
  timeframe: string;
  extended_hours: boolean;
}

export interface PortfolioHistoryResponse {
  timestamp: number[];
  equity: number[];
  profit_loss: number[];
  profit_loss_pct: number[];
  base_value: number;
}

// ── Fundamental analysis types ───────────────────────────────────────

export interface ValuationMetrics {
  market_cap: number;
  trailing_pe: number;
  forward_pe: number;
  trailing_eps: number;
  forward_eps: number;
  price_to_book: number;
  price_to_sales: number;
  peg_ratio: number;
  enterprise_value: number;
  ev_to_ebitda: number;
  dividend_yield: number;
  beta: number;
}

export interface AnalystRating {
  recommendation_key: string;
  recommendation_mean: number;
  strong_buy: number;
  buy: number;
  hold: number;
  sell: number;
  strong_sell: number;
  number_of_analysts: number;
}

export interface PriceTarget {
  current: number;
  low: number;
  high: number;
  mean: number;
  median: number;
  number_of_analysts: number;
}

export interface EarningsSurprise {
  date: string;
  eps_estimate: number;
  eps_actual: number;
  surprise_pct: number;
}

export interface UpgradeDowngrade {
  date: string;
  firm: string;
  to_grade: string;
  from_grade: string;
  action: string;
}

export interface ShortInterest {
  short_ratio: number;
  short_pct_of_float: number;
  shares_short: number;
}

export interface IncomeHighlights {
  revenue: number;
  revenue_growth: number;
  gross_margin: number;
  operating_margin: number;
  profit_margin: number;
  earnings_growth: number;
}

export interface FundamentalAnalysisResponse {
  symbol: string;
  spot_price: number;
  currency: string;
  valuation: ValuationMetrics;
  analyst_rating: AnalystRating;
  price_target: PriceTarget;
  short_interest: ShortInterest;
  income: IncomeHighlights;
  earnings_surprises: EarningsSurprise[];
  upgrades_downgrades: UpgradeDowngrade[];
  next_earnings_date: string | null;
  error: string | null;
}

// ── WebSocket ──────────────────────────────────────────────────────

export type WSChannel = "signals" | "regime" | "broker" | "health";

export interface WSMessage<T = unknown> {
  type: "push" | "subscribed" | "unsubscribed" | "pong" | "error";
  ts: number;
  channel?: WSChannel;
  data?: T;
  error?: string;
}

// ── Symbol Discovery types ──────────────────────────────────────────

export interface SymbolMeta {
  symbol: string;
  rows: number;
  first_date: string;
  last_date: string;
  avg_volume: number;
  last_close: number;
  return_1y: number;
}

export interface PaginatedSymbolResult {
  items: SymbolMeta[];
  total: number;
  offset: number;
  limit: number;
}
