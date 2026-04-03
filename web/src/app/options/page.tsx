"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import Skeleton from "@mui/material/Skeleton";
import Alert from "@mui/material/Alert";
import Chip from "@mui/material/Chip";
import Grid from "@mui/material/Grid";
import TextField from "@mui/material/TextField";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import CircularProgress from "@mui/material/CircularProgress";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import Autocomplete from "@mui/material/Autocomplete";
import SectionHeader from "@/components/SectionHeader";
import { useThemeMode } from "@/components/ThemeProvider";
import {
  fetchSymbols,
  fetchExpirations,
  fetchOptionsChain,
  runBacktest,
} from "@/lib/api";
import type {
  SymbolInfo,
  OptionsChainSummary,
  BacktestRequest,
  BacktestResponse,
  BacktestMetrics,
  StrategyType,
} from "@/lib/types";

function daysUntil(dateStr: string): number {
  const now = new Date();
  const exp = new Date(dateStr);
  const diff = exp.getTime() - now.getTime();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

const STRATEGY_LABELS: Record<StrategyType, string> = {
  short_call_spread: "Short Call Spread",
  long_put_spread: "Long Put Spread",
  short_calls: "Short Calls",
  short_puts: "Short Puts",
  long_calls: "Long Calls",
  long_puts: "Long Puts",
  long_call_spread: "Long Call Spread",
  short_put_spread: "Short Put Spread",
  iron_condor: "Iron Condor",
  straddle: "Straddle",
};

const ALL_STRATEGIES: StrategyType[] = [
  "short_call_spread",
  "long_put_spread",
  "short_calls",
  "short_puts",
  "long_calls",
  "long_puts",
  "long_call_spread",
  "short_put_spread",
  "iron_condor",
  "straddle",
];

function fmt(value: number, decimals = 2): string {
  return value.toFixed(decimals);
}

function fmtMoney(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

interface EquityCurveChartProps {
  data: number[];
}

function EquityCurveChart({ data }: EquityCurveChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { mode } = useThemeMode();

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;

    let chart: import("lightweight-charts").IChartApi | null = null;
    let resizeObserver: ResizeObserver | null = null;

    async function init() {
      const lc = await import("lightweight-charts");
      const el = containerRef.current;
      if (!el) return;

      const isDark = mode === "dark";
      const bg = isDark ? "#111827" : "#ffffff";
      const textColor = isDark ? "#8899aa" : "#627183";
      const gridColor = isDark ? "#1e2a3a" : "#f0f2f5";

      chart = lc.createChart(el, {
        width: el.clientWidth,
        height: 260,
        layout: {
          background: { color: bg },
          textColor,
        },
        grid: {
          vertLines: { color: gridColor },
          horzLines: { color: gridColor },
        },
        crosshair: {
          mode: lc.CrosshairMode.Normal,
        },
        rightPriceScale: {
          borderColor: gridColor,
        },
        timeScale: {
          borderColor: gridColor,
          timeVisible: false,
        },
      });

      const lineSeries = chart.addSeries(lc.LineSeries, {
        color: "#3b89ff",
        lineWidth: 2,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
        lastValueVisible: true,
      });

      const baseDate = new Date("2020-01-01");
      const seriesData = data.map((value, idx) => {
        const d = new Date(baseDate);
        d.setDate(d.getDate() + idx);
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, "0");
        const dd = String(d.getDate()).padStart(2, "0");
        return {
          time: `${yyyy}-${mm}-${dd}` as import("lightweight-charts").Time,
          value,
        };
      });

      lineSeries.setData(seriesData);
      chart.timeScale().fitContent();

      resizeObserver = new ResizeObserver(() => {
        if (chart && el) {
          chart.applyOptions({ width: el.clientWidth });
        }
      });
      resizeObserver.observe(el);
    }

    init();

    return () => {
      resizeObserver?.disconnect();
      chart?.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mode captured via closure
  }, [data]);

  return <Box ref={containerRef} sx={{ width: "100%", minHeight: 260 }} />;
}

interface MetricCardProps {
  label: string;
  sublabel: string;
  value: string;
  color?: string;
}

function MetricCard({ label, sublabel, value, color }: MetricCardProps) {
  return (
    <Card sx={{ height: "100%" }}>
      <CardContent sx={{ pb: "16px !important" }}>
        <Typography
          variant="caption"
          sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
        >
          {sublabel}
        </Typography>
        <Typography
          variant="body2"
          sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}
        >
          {label}
        </Typography>
        <Typography
          variant="h6"
          sx={{
            fontFamily: "var(--font-geist-mono)",
            fontWeight: 700,
            fontSize: "1.25rem",
            color: color ?? "text.primary",
          }}
        >
          {value}
        </Typography>
      </CardContent>
    </Card>
  );
}

function renderMetrics(metrics: BacktestMetrics) {
  const winColor =
    metrics.win_rate > 50 ? "#36bb80" : metrics.win_rate < 40 ? "#ff7134" : undefined;
  const drawdownColor = "#ff7134";
  const sharpeColor = metrics.sharpe_ratio > 1 ? "#36bb80" : undefined;

  const cards: MetricCardProps[] = [
    {
      label: "总交易次数",
      sublabel: "Total Trades",
      value: String(metrics.total_trades),
    },
    {
      label: "胜率",
      sublabel: "Win Rate",
      value: `${fmt(metrics.win_rate)}%`,
      color: winColor,
    },
    {
      label: "平均收益",
      sublabel: "Mean Return",
      value: `${fmt(metrics.mean_return)}%`,
      color: metrics.mean_return >= 0 ? "#36bb80" : "#ff7134",
    },
    {
      label: "夏普比率",
      sublabel: "Sharpe Ratio",
      value: fmt(metrics.sharpe_ratio),
      color: sharpeColor,
    },
    {
      label: "索提诺比率",
      sublabel: "Sortino Ratio",
      value: fmt(metrics.sortino_ratio),
    },
    {
      label: "最大回撤",
      sublabel: "Max Drawdown",
      value: `${fmt(metrics.max_drawdown)}%`,
      color: drawdownColor,
    },
    {
      label: "盈利因子",
      sublabel: "Profit Factor",
      value: fmt(metrics.profit_factor),
      color: metrics.profit_factor > 1 ? "#36bb80" : "#ff7134",
    },
    {
      label: "卡尔玛比率",
      sublabel: "Calmar Ratio",
      value: fmt(metrics.calmar_ratio),
    },
    {
      label: "最终权益",
      sublabel: "Final Equity",
      value: fmtMoney(metrics.final_equity),
      color: metrics.final_equity > 100000 ? "#36bb80" : "#ff7134",
    },
  ];

  return cards;
}

function ExpirationsBrowser() {
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<SymbolInfo | null>(null);
  const [expirations, setExpirations] = useState<string[]>([]);
  const [loadingSymbols, setLoadingSymbols] = useState(true);
  const [loadingExpirations, setLoadingExpirations] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSymbols()
      .then((syms) => {
        setSymbols(syms);
        if (syms.length > 0) setSelectedSymbol(syms[0]);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load symbols"),
      )
      .finally(() => setLoadingSymbols(false));
  }, []);

  useEffect(() => {
    if (!selectedSymbol) return;
    setLoadingExpirations(true);
    setExpirations([]);
    fetchExpirations(selectedSymbol.symbol)
      .then((dates) => setExpirations(dates))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load expirations"),
      )
      .finally(() => setLoadingExpirations(false));
  }, [selectedSymbol]);

  return (
    <Box component="section" id="expirations" sx={{ mb: 6 }}>
      <SectionHeader
        number="01"
        title="到期日浏览"
        subtitle="Expirations Browser"
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {loadingSymbols ? (
        <Skeleton variant="rounded" height={56} sx={{ mb: 2, maxWidth: 320 }} />
      ) : (
        <Autocomplete
          options={symbols}
          value={selectedSymbol}
          onChange={(_, val) => setSelectedSymbol(val)}
          getOptionLabel={(opt) => opt.symbol}
          renderOption={(props, opt) => (
            <Box component="li" {...props} key={opt.symbol}>
              <Typography variant="body2" sx={{ fontFamily: "var(--font-geist-mono)", fontWeight: 700 }}>
                {opt.symbol}
              </Typography>
              <Typography variant="caption" sx={{ ml: 1, color: "text.secondary" }}>
                {opt.daily_rows} rows · {opt.last_date}
              </Typography>
            </Box>
          )}
          renderInput={(params) => (
            <TextField
              {...params}
              label="选择标的 Select Symbol"
              size="small"
              sx={{ maxWidth: 320 }}
            />
          )}
          sx={{ mb: 3 }}
        />
      )}

      {loadingExpirations && (
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={`exp-skel-${i}`} variant="rounded" width={120} height={32} />
          ))}
        </Box>
      )}

      {!loadingExpirations && expirations.length > 0 && (
        <>
          <Typography
            variant="body2"
            sx={{ color: "text.secondary", mb: 1.5, fontSize: "0.8rem" }}
          >
            共 {expirations.length} 个到期日 · {expirations.length} expirations available
          </Typography>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
            {expirations.map((date) => {
              const dte = daysUntil(date);
              const isNear = dte <= 14;
              const isMid = dte > 14 && dte <= 45;
              return (
                <Chip
                  key={date}
                  label={
                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                      <Typography
                        component="span"
                        sx={{
                          fontFamily: "var(--font-geist-mono)",
                          fontSize: "0.75rem",
                          fontWeight: 700,
                        }}
                      >
                        {date}
                      </Typography>
                      <Typography
                        component="span"
                        sx={{ fontSize: "0.65rem", opacity: 0.8 }}
                      >
                        {dte}d
                      </Typography>
                    </Box>
                  }
                  size="small"
                  sx={{
                    bgcolor: isNear
                      ? "rgba(255,113,52,0.12)"
                      : isMid
                      ? "rgba(253,188,42,0.12)"
                      : "rgba(59,137,255,0.10)",
                    color: isNear ? "#ff7134" : isMid ? "#d49a14" : "#3b89ff",
                    border: `1px solid ${isNear ? "rgba(255,113,52,0.3)" : isMid ? "rgba(253,188,42,0.3)" : "rgba(59,137,255,0.2)"}`,
                  }}
                />
              );
            })}
          </Box>
          <Box sx={{ mt: 2, display: "flex", gap: 2 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: "#ff7134" }} />
              <Typography variant="caption" sx={{ color: "text.secondary" }}>≤14d 近月</Typography>
            </Box>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: "#fdbc2a" }} />
              <Typography variant="caption" sx={{ color: "text.secondary" }}>15–45d 中期</Typography>
            </Box>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: "#3b89ff" }} />
              <Typography variant="caption" sx={{ color: "text.secondary" }}>&gt;45d 远月</Typography>
            </Box>
          </Box>
        </>
      )}

      {!loadingExpirations && !loadingSymbols && expirations.length === 0 && selectedSymbol && !error && (
        <Alert severity="info">暂无到期日数据 · No expirations available</Alert>
      )}
    </Box>
  );
}

function OptionsChainSection() {
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<SymbolInfo | null>(null);
  const [chain, setChain] = useState<OptionsChainSummary | null>(null);
  const [loadingSymbols, setLoadingSymbols] = useState(true);
  const [loadingChain, setLoadingChain] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSymbols()
      .then((syms) => {
        setSymbols(syms);
        if (syms.length > 0) setSelectedSymbol(syms[0]);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load symbols"),
      )
      .finally(() => setLoadingSymbols(false));
  }, []);

  const loadChain = useCallback((sym: string) => {
    setLoadingChain(true);
    setChain(null);
    fetchOptionsChain(sym, 4)
      .then((data) => setChain(data))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load chain"),
      )
      .finally(() => setLoadingChain(false));
  }, []);

  useEffect(() => {
    if (selectedSymbol) loadChain(selectedSymbol.symbol);
  }, [selectedSymbol, loadChain]);

  const callRatio =
    chain && chain.total_contracts > 0
      ? (chain.calls_count / chain.total_contracts) * 100
      : 0;
  const putRatio =
    chain && chain.total_contracts > 0
      ? (chain.puts_count / chain.total_contracts) * 100
      : 0;

  return (
    <Box component="section" id="chain" sx={{ mb: 6 }}>
      <SectionHeader
        number="02"
        title="期权链概览"
        subtitle="Options Chain Summary"
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {loadingSymbols ? (
        <Skeleton variant="rounded" height={56} sx={{ mb: 2, maxWidth: 320 }} />
      ) : (
        <Autocomplete
          options={symbols}
          value={selectedSymbol}
          onChange={(_, val) => setSelectedSymbol(val)}
          getOptionLabel={(opt) => opt.symbol}
          renderOption={(props, opt) => (
            <Box component="li" {...props} key={opt.symbol}>
              <Typography variant="body2" sx={{ fontFamily: "var(--font-geist-mono)", fontWeight: 700 }}>
                {opt.symbol}
              </Typography>
              <Typography variant="caption" sx={{ ml: 1, color: "text.secondary" }}>
                {opt.daily_rows} rows
              </Typography>
            </Box>
          )}
          renderInput={(params) => (
            <TextField
              {...params}
              label="选择标的 Select Symbol"
              size="small"
              sx={{ maxWidth: 320 }}
            />
          )}
          sx={{ mb: 3 }}
        />
      )}

      {loadingChain && (
        <Grid container spacing={2}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Grid key={`chain-skel-${i}`} size={{ xs: 6, sm: 3 }}>
              <Skeleton variant="rounded" height={88} />
            </Grid>
          ))}
        </Grid>
      )}

      {!loadingChain && chain && (
        <>
          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Card>
                <CardContent>
                  <Typography variant="caption" color="text.secondary">总合约数</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5 }}>Total Contracts</Typography>
                  <Typography
                    variant="h5"
                    sx={{ fontFamily: "var(--font-geist-mono)", fontWeight: 700, color: "#3b89ff" }}
                  >
                    {chain.total_contracts.toLocaleString()}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Card>
                <CardContent>
                  <Typography variant="caption" color="text.secondary">看涨期权</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5 }}>Calls</Typography>
                  <Typography
                    variant="h5"
                    sx={{ fontFamily: "var(--font-geist-mono)", fontWeight: 700, color: "#36bb80" }}
                  >
                    {chain.calls_count.toLocaleString()}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "#36bb80" }}>
                    {fmt(callRatio)}%
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Card>
                <CardContent>
                  <Typography variant="caption" color="text.secondary">看跌期权</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5 }}>Puts</Typography>
                  <Typography
                    variant="h5"
                    sx={{ fontFamily: "var(--font-geist-mono)", fontWeight: 700, color: "#ff7134" }}
                  >
                    {chain.puts_count.toLocaleString()}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "#ff7134" }}>
                    {fmt(putRatio)}%
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Card>
                <CardContent>
                  <Typography variant="caption" color="text.secondary">到期日数量</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5 }}>Expirations</Typography>
                  <Typography
                    variant="h5"
                    sx={{ fontFamily: "var(--font-geist-mono)", fontWeight: 700, color: "#fdbc2a" }}
                  >
                    {chain.expirations.length}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="body2" sx={{ fontWeight: 700, mb: 1.5 }}>
                看涨/看跌比率 · Call/Put Ratio
              </Typography>
              <Box sx={{ display: "flex", height: 12, borderRadius: 1, overflow: "hidden", mb: 1 }}>
                <Box sx={{ width: `${callRatio}%`, bgcolor: "#36bb80", transition: "width 0.4s ease" }} />
                <Box sx={{ width: `${putRatio}%`, bgcolor: "#ff7134", transition: "width 0.4s ease" }} />
              </Box>
              <Box sx={{ display: "flex", justifyContent: "space-between" }}>
                <Typography variant="caption" sx={{ color: "#36bb80" }}>
                  Calls {fmt(callRatio)}%
                </Typography>
                <Typography variant="caption" sx={{ color: "#ff7134" }}>
                  Puts {fmt(putRatio)}%
                </Typography>
              </Box>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="body2" sx={{ fontWeight: 700, mb: 1.5 }}>
                可用到期日 · Available Expirations
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
                {chain.expirations.map((date) => (
                  <Chip
                    key={date}
                    label={
                      <Typography
                        component="span"
                        sx={{ fontFamily: "var(--font-geist-mono)", fontSize: "0.72rem", fontWeight: 600 }}
                      >
                        {date}
                      </Typography>
                    }
                    size="small"
                    sx={{
                      bgcolor: "action.selected",
                      border: "1px solid",
                      borderColor: "divider",
                    }}
                  />
                ))}
              </Box>
            </CardContent>
          </Card>
        </>
      )}

      {!loadingChain && !loadingSymbols && !chain && selectedSymbol && !error && (
        <Alert severity="info">暂无期权链数据 · No options chain data available</Alert>
      )}
    </Box>
  );
}

interface BacktestParams {
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
  stop_loss: string;
  take_profit: string;
  max_expirations: number;
}

function BacktestSimulator() {
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [loadingSymbols, setLoadingSymbols] = useState(true);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [params, setParams] = useState<BacktestParams>({
    symbol: "",
    strategy: "short_call_spread",
    max_entry_dte: 45,
    exit_dte: 0,
    leg1_delta: 0.3,
    leg2_delta: 0.1,
    capital: 100000,
    quantity: 1,
    max_positions: 5,
    commission_per_contract: 0.5,
    stop_loss: "",
    take_profit: "",
    max_expirations: 4,
  });

  useEffect(() => {
    fetchSymbols()
      .then((syms) => {
        setSymbols(syms);
        if (syms.length > 0) {
          setParams((p) => ({ ...p, symbol: syms[0].symbol }));
        }
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load symbols"),
      )
      .finally(() => setLoadingSymbols(false));
  }, []);

  function setField<K extends keyof BacktestParams>(key: K, value: BacktestParams[K]) {
    setParams((p) => ({ ...p, [key]: value }));
  }

  async function handleRun() {
    if (!params.symbol) return;
    setRunning(true);
    setResult(null);
    setError(null);

    const req: BacktestRequest = {
      symbol: params.symbol,
      strategy: params.strategy,
      max_entry_dte: params.max_entry_dte,
      exit_dte: params.exit_dte,
      leg1_delta: params.leg1_delta,
      leg2_delta: params.leg2_delta,
      capital: params.capital,
      quantity: params.quantity,
      max_positions: params.max_positions,
      commission_per_contract: params.commission_per_contract,
      stop_loss: params.stop_loss !== "" ? Number(params.stop_loss) : null,
      take_profit: params.take_profit !== "" ? Number(params.take_profit) : null,
      max_expirations: params.max_expirations,
    };

    try {
      const res = await runBacktest(req);
      setResult(res);
      if (res.error) setError(res.error);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Backtest failed");
    } finally {
      setRunning(false);
    }
  }

  const metricCards = result && !result.error ? renderMetrics(result.metrics) : [];

  return (
    <Box component="section" id="backtest" sx={{ mb: 6 }}>
      <SectionHeader
        number="03"
        title="回测模拟器"
        subtitle="Backtest Simulator"
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="body2" sx={{ fontWeight: 700, mb: 2 }}>
            策略配置 · Strategy Configuration
          </Typography>

          <Grid container spacing={2}>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              {loadingSymbols ? (
                <Skeleton variant="rounded" height={56} />
              ) : (
                <FormControl fullWidth size="small">
                  <InputLabel>标的 Symbol</InputLabel>
                  <Select
                    value={params.symbol}
                    label="标的 Symbol"
                    onChange={(e) => setField("symbol", e.target.value)}
                  >
                    {symbols.map((s) => (
                      <MenuItem key={s.symbol} value={s.symbol}>
                        <Typography
                          component="span"
                          sx={{ fontFamily: "var(--font-geist-mono)", fontWeight: 700, fontSize: "0.875rem" }}
                        >
                          {s.symbol}
                        </Typography>
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <FormControl fullWidth size="small">
                <InputLabel>策略 Strategy</InputLabel>
                <Select
                  value={params.strategy}
                  label="策略 Strategy"
                  onChange={(e) => setField("strategy", e.target.value as StrategyType)}
                >
                  {ALL_STRATEGIES.map((s) => (
                    <MenuItem key={s} value={s}>
                      {STRATEGY_LABELS[s]}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>

          <Divider sx={{ my: 2 }} />

          <Typography variant="body2" sx={{ fontWeight: 700, mb: 2, color: "text.secondary" }}>
            参数设置 · Parameters
          </Typography>

          <Grid container spacing={2}>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="Max Entry DTE"
                type="number"
                size="small"
                fullWidth
                value={params.max_entry_dte}
                onChange={(e) => setField("max_entry_dte", Number(e.target.value))}
                slotProps={{ htmlInput: { min: 1, max: 365 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="Exit DTE"
                type="number"
                size="small"
                fullWidth
                value={params.exit_dte}
                onChange={(e) => setField("exit_dte", Number(e.target.value))}
                slotProps={{ htmlInput: { min: 0, max: 60 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="Leg 1 Delta"
                type="number"
                size="small"
                fullWidth
                value={params.leg1_delta}
                onChange={(e) => setField("leg1_delta", Number(e.target.value))}
                slotProps={{ htmlInput: { min: 0.01, max: 1, step: 0.05 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="Leg 2 Delta"
                type="number"
                size="small"
                fullWidth
                value={params.leg2_delta}
                onChange={(e) => setField("leg2_delta", Number(e.target.value))}
                slotProps={{ htmlInput: { min: 0.01, max: 1, step: 0.05 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="Capital ($)"
                type="number"
                size="small"
                fullWidth
                value={params.capital}
                onChange={(e) => setField("capital", Number(e.target.value))}
                slotProps={{ htmlInput: { min: 1000, step: 1000 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="Quantity"
                type="number"
                size="small"
                fullWidth
                value={params.quantity}
                onChange={(e) => setField("quantity", Number(e.target.value))}
                slotProps={{ htmlInput: { min: 1, max: 100 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="Max Positions"
                type="number"
                size="small"
                fullWidth
                value={params.max_positions}
                onChange={(e) => setField("max_positions", Number(e.target.value))}
                slotProps={{ htmlInput: { min: 1, max: 50 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="Commission/Contract ($)"
                type="number"
                size="small"
                fullWidth
                value={params.commission_per_contract}
                onChange={(e) => setField("commission_per_contract", Number(e.target.value))}
                slotProps={{ htmlInput: { min: 0, step: 0.1 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="Stop Loss (%) — optional"
                type="number"
                size="small"
                fullWidth
                value={params.stop_loss}
                onChange={(e) => setField("stop_loss", e.target.value)}
                slotProps={{ htmlInput: { min: 0, max: 100, step: 5 } }}
                placeholder="留空"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="Take Profit (%) — optional"
                type="number"
                size="small"
                fullWidth
                value={params.take_profit}
                onChange={(e) => setField("take_profit", e.target.value)}
                slotProps={{ htmlInput: { min: 0, max: 1000, step: 5 } }}
                placeholder="留空"
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="Max Expirations"
                type="number"
                size="small"
                fullWidth
                value={params.max_expirations}
                onChange={(e) => setField("max_expirations", Number(e.target.value))}
                slotProps={{ htmlInput: { min: 1, max: 12 } }}
              />
            </Grid>
          </Grid>

          <Box sx={{ mt: 3 }}>
            <Button
              variant="contained"
              size="large"
              onClick={handleRun}
              disabled={running || !params.symbol}
              startIcon={running ? <CircularProgress size={16} color="inherit" /> : null}
              sx={{
                bgcolor: "#3b89ff",
                px: 4,
                py: 1.2,
                fontWeight: 700,
                fontSize: "0.9rem",
                "&:hover": { bgcolor: "#1a6fe0" },
              }}
            >
              {running ? "运行中..." : "运行回测 Run Backtest"}
            </Button>
          </Box>
        </CardContent>
      </Card>

      {result && !result.error && (
        <>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 2 }}>
            <Typography variant="body1" sx={{ fontWeight: 700 }}>
              回测结果 · Backtest Results
            </Typography>
            <Chip
              label={`${result.symbol} · ${STRATEGY_LABELS[result.strategy as StrategyType] ?? result.strategy}`}
              size="small"
              sx={{ bgcolor: "rgba(59,137,255,0.1)", color: "#3b89ff", border: "1px solid rgba(59,137,255,0.25)" }}
            />
            <Chip
              label={`${result.trade_count} trades`}
              size="small"
              sx={{ bgcolor: "action.selected", color: "text.secondary" }}
            />
          </Box>

          <Grid container spacing={2} sx={{ mb: 3 }}>
            {metricCards.map((card) => (
              <Grid key={card.sublabel} size={{ xs: 6, sm: 4, md: 3 }}>
                <MetricCard {...card} />
              </Grid>
            ))}
          </Grid>

          <Card>
            <CardContent>
              <Typography variant="body2" sx={{ fontWeight: 700, mb: 2 }}>
                权益曲线 · Equity Curve
              </Typography>
              {result.equity_curve.length > 0 ? (
                <EquityCurveChart data={result.equity_curve} />
              ) : (
                <Alert severity="info">无权益曲线数据 · No equity curve data</Alert>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </Box>
  );
}

export default function OptionsPage() {
  return (
    <Box sx={{ px: { xs: 2, sm: 3, md: 4 }, py: 4 }}>
      <Box sx={{ mb: 4 }}>
        <Typography
          variant="h5"
          sx={{ fontWeight: 700, mb: 0.5 }}
        >
          期权工具
        </Typography>
        <Typography variant="body2" sx={{ color: "text.secondary" }}>
          Options Tools — Expirations, Chain, Backtest Simulator
        </Typography>
      </Box>

      <ExpirationsBrowser />
      <OptionsChainSection />
      <BacktestSimulator />
    </Box>
  );
}
