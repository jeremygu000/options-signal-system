import type {
  HealthResponse,
  SymbolInfo,
  MarketRegimeResult,
  FullScanResponse,
  IndicatorSnapshot,
  PaginatedOHLCV,
  CompareResponse,
  OptionsChainSummary,
  OptionsChainDetail,
  BacktestRequest,
  BacktestResponse,
  GreeksRequest,
  GreeksResponse,
  IVAnalysisResponse,
  MultiLegRequest,
  MultiLegResponse,
  PositionCreate,
  PositionUpdate,
  PositionClose,
  PositionResponse,
  PortfolioSummaryResponse,
  StrategyGroupResponse,
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

export function fetchOptionsChainDetail(
  symbol: string,
  expiration?: string,
  maxExpirations = 4,
): Promise<OptionsChainDetail> {
  const params = new URLSearchParams();
  params.set("max_expirations", String(maxExpirations));
  if (expiration) params.set("expiration", expiration);
  return fetcher<OptionsChainDetail>(
    `/api/v1/options/chain/${symbol}/detail?${params.toString()}`,
  );
}

export function runBacktest(req: BacktestRequest): Promise<BacktestResponse> {
  return fetcher<BacktestResponse>("/api/v1/backtest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export function calculateGreeks(req: GreeksRequest): Promise<GreeksResponse> {
  return fetcher<GreeksResponse>("/api/v1/greeks/calculate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export function fetchIVAnalysis(symbol: string): Promise<IVAnalysisResponse> {
  return fetcher<IVAnalysisResponse>(`/api/v1/iv/analysis/${symbol}`);
}

export function analyzeMultiLeg(req: MultiLegRequest): Promise<MultiLegResponse> {
  return fetcher<MultiLegResponse>("/api/v1/options/multi-leg/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export interface InterpretBacktestPayload {
  symbol: string;
  strategy: string;
  trade_count: number;
  metrics: Record<string, number>;
  equity_curve_summary?: string;
}

export async function interpretBacktest(
  payload: InterpretBacktestPayload,
  onToken: (token: string) => void,
  onError: (error: string) => void,
  onDone: () => void,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/backtest/interpret`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok || !res.body) {
    onError(`API error ${res.status}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    // oxlint-disable-next-line no-await-in-loop -- sequential stream reads are intentional
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const json = line.slice(6);
      try {
        const parsed = JSON.parse(json) as {
          token?: string;
          done?: boolean;
          error?: string;
        };
        if (parsed.error) {
          onError(parsed.error);
          return;
        }
        if (parsed.token) onToken(parsed.token);
        if (parsed.done) {
          onDone();
          return;
        }
      } catch {
        /* empty */
      }
    }
  }
  onDone();
}

export function createPosition(data: PositionCreate): Promise<PositionResponse> {
  return fetcher<PositionResponse>("/api/v1/positions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function fetchPositions(params?: {
  status?: string;
  symbol?: string;
  strategy?: string;
}): Promise<PositionResponse[]> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.symbol) qs.set("symbol", params.symbol);
  if (params?.strategy) qs.set("strategy", params.strategy);
  const query = qs.toString();
  return fetcher<PositionResponse[]>(`/api/v1/positions${query ? `?${query}` : ""}`);
}

export function fetchPosition(id: string): Promise<PositionResponse> {
  return fetcher<PositionResponse>(`/api/v1/positions/${id}`);
}

export function updatePosition(
  id: string,
  data: PositionUpdate,
): Promise<PositionResponse> {
  return fetcher<PositionResponse>(`/api/v1/positions/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function closePosition(
  id: string,
  data: PositionClose,
): Promise<PositionResponse> {
  return fetcher<PositionResponse>(`/api/v1/positions/${id}/close`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function deletePosition(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/positions/${id}`, {
    method: "DELETE",
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: /api/v1/positions/${id}`);
  }
}

export function fetchPortfolioSummary(): Promise<PortfolioSummaryResponse> {
  return fetcher<PortfolioSummaryResponse>("/api/v1/portfolio/summary");
}

export function fetchPortfolioStrategies(): Promise<StrategyGroupResponse[]> {
  return fetcher<StrategyGroupResponse[]>("/api/v1/portfolio/strategies");
}

export function fetchExpiringPositions(days = 7): Promise<PositionResponse[]> {
  return fetcher<PositionResponse[]>(`/api/v1/positions/alerts/expiring?days=${days}`);
}

export function batchMarkExpired(): Promise<{ marked_expired: number }> {
  return fetcher<{ marked_expired: number }>("/api/v1/positions/batch/mark-expired", {
    method: "POST",
  });
}
