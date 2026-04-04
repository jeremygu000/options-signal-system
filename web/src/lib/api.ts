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
  EnhancedSignal,
  MLRegimeResponse,
  TrainingStatusResponse,
  SymbolMeta,
  PaginatedSymbolResult,
  SignalBacktestRequest,
  SignalBacktestResponse,
  WalkForwardRequest,
  WalkForwardResponse,
  CreateOrderRequest,
  OrderResponse,
  AccountInfoResponse,
  BrokerPositionResponse,
  ClosePositionRequest,
  PortfolioHistoryRequest,
  PortfolioHistoryResponse,
  FundamentalAnalysisResponse,
  PutCallRatioResponse,
  UnusualVolumeResponse,
  WatchlistCreate,
  WatchlistUpdate,
  WatchlistResponse,
  WatchlistItemCreate,
  WatchlistItemResponse,
  WatchlistItemUpdate,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8400";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

export function authHeaders(): HeadersInit {
  if (!API_KEY) return {};
  return { Authorization: `Bearer ${API_KEY}` };
}

async function fetcher<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    ...init,
    headers: { ...authHeaders(), ...init?.headers },
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

export function analyzeMultiLeg(
  req: MultiLegRequest,
): Promise<MultiLegResponse> {
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

export function createPosition(
  data: PositionCreate,
): Promise<PositionResponse> {
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
  return fetcher<PositionResponse[]>(
    `/api/v1/positions${query ? `?${query}` : ""}`,
  );
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
    headers: { ...authHeaders() },
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
  return fetcher<PositionResponse[]>(
    `/api/v1/positions/alerts/expiring?days=${days}`,
  );
}

export function batchMarkExpired(): Promise<{ marked_expired: number }> {
  return fetcher<{ marked_expired: number }>(
    "/api/v1/positions/batch/mark-expired",
    {
      method: "POST",
    },
  );
}

export function fetchEnhancedSignals(): Promise<EnhancedSignal[]> {
  return fetcher<EnhancedSignal[]>("/api/v1/signals/enhanced");
}

export function fetchMLRegime(): Promise<MLRegimeResponse> {
  return fetcher<MLRegimeResponse>("/api/v1/ml/regime");
}

export function triggerTraining(
  lookbackDays = 365,
): Promise<TrainingStatusResponse> {
  return fetcher<TrainingStatusResponse>("/api/v1/ml/train", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lookback_days: lookbackDays }),
  });
}

export function fetchMLStatus(): Promise<TrainingStatusResponse> {
  return fetcher<TrainingStatusResponse>("/api/v1/ml/status");
}

export async function analyzeSignal(
  symbol: string,
  onToken: (token: string) => void,
  onError: (error: string) => void,
  onDone: () => void,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/ml/analyze/${symbol}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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

export function fetchAvailableSymbols(): Promise<string[]> {
  return fetcher<string[]>("/api/v1/symbols/available");
}

export function searchSymbols(params?: {
  query?: string;
  min_volume?: number;
  min_rows?: number;
  sort_by?: string;
  limit?: number;
  offset?: number;
}): Promise<PaginatedSymbolResult> {
  const qs = new URLSearchParams();
  if (params?.query) qs.set("query", params.query);
  if (params?.min_volume != null)
    qs.set("min_volume", String(params.min_volume));
  if (params?.min_rows != null) qs.set("min_rows", String(params.min_rows));
  if (params?.sort_by) qs.set("sort_by", params.sort_by);
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  const q = qs.toString();
  return fetcher<PaginatedSymbolResult>(
    `/api/v1/symbols/search${q ? `?${q}` : ""}`,
  );
}

export function fetchSymbolsMetadata(): Promise<SymbolMeta[]> {
  return fetcher<SymbolMeta[]>("/api/v1/symbols/metadata");
}

export function runSignalBacktest(
  req: SignalBacktestRequest,
): Promise<SignalBacktestResponse> {
  return fetcher<SignalBacktestResponse>("/api/v1/backtest/signals", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export function runWalkForward(
  req: WalkForwardRequest,
): Promise<WalkForwardResponse> {
  return fetcher<WalkForwardResponse>("/api/v1/backtest/walk-forward", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export function fetchBrokerAccount(): Promise<AccountInfoResponse> {
  return fetcher<AccountInfoResponse>("/api/v1/broker/account");
}

export function submitOrder(req: CreateOrderRequest): Promise<OrderResponse> {
  return fetcher<OrderResponse>("/api/v1/broker/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export function fetchBrokerOrders(params?: {
  status?: string;
  limit?: number;
  symbols?: string;
}): Promise<OrderResponse[]> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.symbols) qs.set("symbols", params.symbols);
  const q = qs.toString();
  return fetcher<OrderResponse[]>(`/api/v1/broker/orders${q ? `?${q}` : ""}`);
}

export async function cancelOrder(orderId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/broker/orders/${orderId}`, {
    method: "DELETE",
    cache: "no-store",
    headers: { ...authHeaders() },
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: cancel order ${orderId}`);
  }
}

export async function cancelAllOrders(): Promise<{ cancelled: number }> {
  return fetcher<{ cancelled: number }>("/api/v1/broker/orders", {
    method: "DELETE",
  });
}

export function fetchBrokerPositions(): Promise<BrokerPositionResponse[]> {
  return fetcher<BrokerPositionResponse[]>("/api/v1/broker/positions");
}

export function fetchBrokerPosition(
  symbol: string,
): Promise<BrokerPositionResponse> {
  return fetcher<BrokerPositionResponse>(`/api/v1/broker/positions/${symbol}`);
}

export async function closeBrokerPosition(
  symbol: string,
  req?: ClosePositionRequest,
): Promise<OrderResponse> {
  return fetcher<OrderResponse>(`/api/v1/broker/positions/${symbol}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: req ? JSON.stringify(req) : undefined,
  });
}

export async function closeAllBrokerPositions(): Promise<{ closed: number }> {
  return fetcher<{ closed: number }>("/api/v1/broker/positions", {
    method: "DELETE",
  });
}

export function fetchPortfolioHistory(
  req: PortfolioHistoryRequest,
): Promise<PortfolioHistoryResponse> {
  return fetcher<PortfolioHistoryResponse>("/api/v1/broker/portfolio/history", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export function fetchFundamentalAnalysis(
  symbol: string,
): Promise<FundamentalAnalysisResponse> {
  return fetcher<FundamentalAnalysisResponse>(
    `/api/v1/fundamentals/${encodeURIComponent(symbol)}`,
  );
}

export function fetchPutCallRatio(
  symbol: string,
): Promise<PutCallRatioResponse> {
  return fetcher<PutCallRatioResponse>(
    `/api/v1/options/put-call-ratio/${encodeURIComponent(symbol)}`,
  );
}

export function fetchUnusualVolume(
  symbol: string,
): Promise<UnusualVolumeResponse> {
  return fetcher<UnusualVolumeResponse>(
    `/api/v1/options/unusual-volume/${encodeURIComponent(symbol)}`,
  );
}

export function fetchWatchlists(): Promise<WatchlistResponse[]> {
  return fetcher<WatchlistResponse[]>("/api/v1/watchlists");
}

export function fetchWatchlist(id: string): Promise<WatchlistResponse> {
  return fetcher<WatchlistResponse>(
    `/api/v1/watchlists/${encodeURIComponent(id)}`,
  );
}

export function createWatchlist(
  req: WatchlistCreate,
): Promise<WatchlistResponse> {
  return fetcher<WatchlistResponse>("/api/v1/watchlists", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export function updateWatchlist(
  id: string,
  req: WatchlistUpdate,
): Promise<WatchlistResponse> {
  return fetcher<WatchlistResponse>(
    `/api/v1/watchlists/${encodeURIComponent(id)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    },
  );
}

export function activateWatchlist(id: string): Promise<WatchlistResponse> {
  return fetcher<WatchlistResponse>(
    `/api/v1/watchlists/${encodeURIComponent(id)}/activate`,
    { method: "POST" },
  );
}

export async function deleteWatchlist(id: string): Promise<void> {
  const res = await fetch(
    `${API_URL}/api/v1/watchlists/${encodeURIComponent(id)}`,
    {
      method: "DELETE",
      cache: "no-store",
      headers: { ...authHeaders() },
    },
  );
  if (!res.ok) {
    throw new Error(`API error ${res.status}: delete watchlist ${id}`);
  }
}

export function fetchActiveWatchlistSymbols(): Promise<string[]> {
  return fetcher<string[]>("/api/v1/watchlists/active/symbols");
}

export function addWatchlistItem(
  watchlistId: string,
  req: WatchlistItemCreate,
): Promise<WatchlistItemResponse> {
  return fetcher<WatchlistItemResponse>(
    `/api/v1/watchlists/${encodeURIComponent(watchlistId)}/items`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    },
  );
}

export function updateWatchlistItem(
  itemId: string,
  req: WatchlistItemUpdate,
): Promise<WatchlistItemResponse> {
  return fetcher<WatchlistItemResponse>(
    `/api/v1/watchlists/items/${encodeURIComponent(itemId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    },
  );
}

export async function deleteWatchlistItem(itemId: string): Promise<void> {
  const res = await fetch(
    `${API_URL}/api/v1/watchlists/items/${encodeURIComponent(itemId)}`,
    {
      method: "DELETE",
      cache: "no-store",
      headers: { ...authHeaders() },
    },
  );
  if (!res.ok) {
    throw new Error(`API error ${res.status}: delete watchlist item ${itemId}`);
  }
}
