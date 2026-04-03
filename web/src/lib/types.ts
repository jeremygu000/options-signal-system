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
}

export interface IndicatorSnapshot {
  symbol: string;
  sma5: number;
  sma10: number;
  atr14: number;
  vwap: number;
  prev_high: number;
  prev_low: number;
  rolling_high_20: number;
  rolling_low_20: number;
  range_position: number;
  timestamp: string;
}

export interface OHLCVBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface SymbolInfo {
  symbol: string;
  bias: Bias;
  has_daily_data: boolean;
  has_intraday_data: boolean;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
}

export interface ComparePoint {
  date: string;
  time?: number;
  close: number;
}

export type CompareResponse = Record<string, ComparePoint[]>;
