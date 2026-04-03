import type {
  HealthResponse,
  SymbolInfo,
  MarketRegimeResult,
  FullScanResponse,
  IndicatorSnapshot,
  PaginatedOHLCV,
  CompareResponse,
  OptionsChainSummary,
  BacktestRequest,
  BacktestResponse,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8300";

async function fetcher<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    ...init,
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${path}`);
  }
  return res.json() as Promise<T>;
}

export function fetchHealth(): Promise<HealthResponse> {
  return fetcher<HealthResponse>("/api/v1/health");
}

export function fetchSymbols(): Promise<SymbolInfo[]> {
  return fetcher<SymbolInfo[]>("/api/v1/symbols");
}

export function fetchRegime(): Promise<MarketRegimeResult> {
  return fetcher<MarketRegimeResult>("/api/v1/regime");
}

export function fetchSignals(): Promise<FullScanResponse> {
  return fetcher<FullScanResponse>("/api/v1/signals");
}

export function fetchScan(): Promise<FullScanResponse> {
  return fetcher<FullScanResponse>("/api/v1/scan");
}

export function fetchIndicators(symbol: string): Promise<IndicatorSnapshot> {
  return fetcher<IndicatorSnapshot>(`/api/v1/indicators/${symbol}`);
}

export function fetchOHLCV(
  symbol: string,
  days = 90,
  offset = 0,
  limit = 500,
): Promise<PaginatedOHLCV> {
  return fetcher<PaginatedOHLCV>(
    `/api/v1/ohlcv/${symbol}?days=${days}&offset=${offset}&limit=${limit}`,
  );
}

export function fetchCompare(
  tickers: string,
  days = 90,
): Promise<CompareResponse> {
  return fetcher<CompareResponse>(
    `/api/v1/compare?tickers=${tickers}&days=${days}`,
  );
}

export function fetchExpirations(symbol: string): Promise<string[]> {
  return fetcher<string[]>(`/api/v1/options/expirations/${symbol}`);
}

export function fetchOptionsChain(
  symbol: string,
  maxExpirations = 4,
): Promise<OptionsChainSummary> {
  return fetcher<OptionsChainSummary>(
    `/api/v1/options/chain/${symbol}?max_expirations=${maxExpirations}`,
  );
}

export function runBacktest(req: BacktestRequest): Promise<BacktestResponse> {
  return fetcher<BacktestResponse>("/api/v1/backtest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}
