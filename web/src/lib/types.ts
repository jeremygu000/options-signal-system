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
