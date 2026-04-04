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
import IconButton from "@mui/material/IconButton";
import SectionHeader from "@/components/SectionHeader";
import { useThemeMode } from "@/components/ThemeProvider";
import Table from "@mui/material/Table";
import TableHead from "@mui/material/TableHead";
import TableBody from "@mui/material/TableBody";
import TableRow from "@mui/material/TableRow";
import TableCell from "@mui/material/TableCell";
import TableSortLabel from "@mui/material/TableSortLabel";
import {
  fetchSymbols,
  fetchExpirations,
  fetchOptionsChain,
  fetchOptionsChainDetail,
  runBacktest,
  interpretBacktest,
  calculateGreeks,
  fetchIVAnalysis,
  analyzeMultiLeg,
} from "@/lib/api";
import type {
  SymbolInfo,
  OptionsChainSummary,
  OptionsChainDetail,
  OptionsContract,
  BacktestRequest,
  BacktestResponse,
  BacktestMetrics,
  StrategyType,
  GreeksRequest,
  GreeksResponse,
  IVAnalysisResponse,
  MultiLegResponse,
  OptionLegInput,
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
    metrics.win_rate > 50
      ? "#36bb80"
      : metrics.win_rate < 40
        ? "#ff7134"
        : undefined;
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
              <Typography
                variant="body2"
                sx={{ fontFamily: "var(--font-geist-mono)", fontWeight: 700 }}
              >
                {opt.symbol}
              </Typography>
              <Typography
                variant="caption"
                sx={{ ml: 1, color: "text.secondary" }}
              >
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
          {["a", "b", "c", "d", "e", "f", "g", "h"].map((id) => (
            <Skeleton
              key={`exp-skel-${id}`}
              variant="rounded"
              width={120}
              height={32}
            />
          ))}
        </Box>
      )}

      {!loadingExpirations && expirations.length > 0 && (
        <>
          <Typography
            variant="body2"
            sx={{ color: "text.secondary", mb: 1.5, fontSize: "0.8rem" }}
          >
            共 {expirations.length} 个到期日 · {expirations.length} expirations
            available
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
                    <Box
                      sx={{ display: "flex", alignItems: "center", gap: 0.5 }}
                    >
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
              <Box
                sx={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  bgcolor: "#ff7134",
                }}
              />
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                ≤14d 近月
              </Typography>
            </Box>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Box
                sx={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  bgcolor: "#fdbc2a",
                }}
              />
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                15–45d 中期
              </Typography>
            </Box>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Box
                sx={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  bgcolor: "#3b89ff",
                }}
              />
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                &gt;45d 远月
              </Typography>
            </Box>
          </Box>
        </>
      )}

      {!loadingExpirations &&
        !loadingSymbols &&
        expirations.length === 0 &&
        selectedSymbol &&
        !error && (
          <Alert severity="info">
            暂无到期日数据 · No expirations available
          </Alert>
        )}
    </Box>
  );
}

type SortColumn =
  | "strike"
  | "bid"
  | "ask"
  | "implied_volatility"
  | "delta"
  | "gamma"
  | "theta"
  | "vega"
  | "rho"
  | "volume"
  | "open_interest";

function OptionsChainSection() {
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<SymbolInfo | null>(null);
  const [chain, setChain] = useState<OptionsChainSummary | null>(null);
  const [detail, setDetail] = useState<OptionsChainDetail | null>(null);
  const [loadingSymbols, setLoadingSymbols] = useState(true);
  const [loadingChain, setLoadingChain] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedExpiration, setSelectedExpiration] = useState<string>("all");
  const [sortCol, setSortCol] = useState<SortColumn>("strike");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

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

  const loadDetail = useCallback((sym: string, expiration?: string) => {
    setLoadingDetail(true);
    setDetail(null);
    fetchOptionsChainDetail(sym, expiration === "all" ? undefined : expiration)
      .then((data) => setDetail(data))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load detail"),
      )
      .finally(() => setLoadingDetail(false));
  }, []);

  useEffect(() => {
    if (selectedSymbol) {
      setSelectedExpiration("all");
      loadChain(selectedSymbol.symbol);
      loadDetail(selectedSymbol.symbol);
    }
  }, [selectedSymbol, loadChain, loadDetail]);

  useEffect(() => {
    if (selectedSymbol) {
      loadDetail(selectedSymbol.symbol, selectedExpiration);
    }
  }, [selectedExpiration, selectedSymbol, loadDetail]);

  const callRatio =
    chain && chain.total_contracts > 0
      ? (chain.calls_count / chain.total_contracts) * 100
      : 0;
  const putRatio =
    chain && chain.total_contracts > 0
      ? (chain.puts_count / chain.total_contracts) * 100
      : 0;

  const handleSort = (col: SortColumn) => {
    if (sortCol === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
  };

  const sortedContracts: OptionsContract[] = detail
    ? detail.contracts.toSorted((a, b) => {
        const av = a[sortCol] ?? 0;
        const bv = b[sortCol] ?? 0;
        const cmp =
          (av as number) < (bv as number)
            ? -1
            : (av as number) > (bv as number)
              ? 1
              : 0;
        return sortDir === "asc" ? cmp : -cmp;
      })
    : [];

  const monoStyle = { fontFamily: "var(--font-geist-mono)" } as const;
  const cellSx = { ...monoStyle, fontSize: "0.75rem", py: 0.5, px: 1 } as const;
  const headCellSx = {
    ...monoStyle,
    fontSize: "0.7rem",
    fontWeight: 700,
    py: 0.75,
    px: 1,
    whiteSpace: "nowrap" as const,
  } as const;

  const cols: { id: SortColumn; label: string }[] = [
    { id: "strike", label: "Strike" },
    { id: "bid", label: "Bid" },
    { id: "ask", label: "Ask" },
    { id: "implied_volatility", label: "IV" },
    { id: "delta", label: "Delta" },
    { id: "gamma", label: "Gamma" },
    { id: "theta", label: "Theta" },
    { id: "vega", label: "Vega" },
    { id: "rho", label: "Rho" },
    { id: "volume", label: "Volume" },
    { id: "open_interest", label: "OI" },
  ];

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
              <Typography
                variant="body2"
                sx={{ fontFamily: "var(--font-geist-mono)", fontWeight: 700 }}
              >
                {opt.symbol}
              </Typography>
              <Typography
                variant="caption"
                sx={{ ml: 1, color: "text.secondary" }}
              >
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
          {["a", "b", "c", "d"].map((id) => (
            <Grid key={`chain-skel-${id}`} size={{ xs: 6, sm: 3 }}>
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
                  <Typography variant="caption" color="text.secondary">
                    总合约数
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5 }}>
                    Total Contracts
                  </Typography>
                  <Typography
                    variant="h5"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 700,
                      color: "#3b89ff",
                    }}
                  >
                    {chain.total_contracts.toLocaleString()}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Card>
                <CardContent>
                  <Typography variant="caption" color="text.secondary">
                    看涨期权
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5 }}>
                    Calls
                  </Typography>
                  <Typography
                    variant="h5"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 700,
                      color: "#36bb80",
                    }}
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
                  <Typography variant="caption" color="text.secondary">
                    看跌期权
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5 }}>
                    Puts
                  </Typography>
                  <Typography
                    variant="h5"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 700,
                      color: "#ff7134",
                    }}
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
                  <Typography variant="caption" color="text.secondary">
                    到期日数量
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5 }}>
                    Expirations
                  </Typography>
                  <Typography
                    variant="h5"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 700,
                      color: "#fdbc2a",
                    }}
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
              <Box
                sx={{
                  display: "flex",
                  height: 12,
                  borderRadius: 1,
                  overflow: "hidden",
                  mb: 1,
                }}
              >
                <Box
                  sx={{
                    width: `${callRatio}%`,
                    bgcolor: "#36bb80",
                    transition: "width 0.4s ease",
                  }}
                />
                <Box
                  sx={{
                    width: `${putRatio}%`,
                    bgcolor: "#ff7134",
                    transition: "width 0.4s ease",
                  }}
                />
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

          <Card sx={{ mb: 2 }}>
            <CardContent sx={{ pb: "12px !important" }}>
              <Typography variant="body2" sx={{ fontWeight: 700, mb: 1.5 }}>
                筛选到期日 · Filter by Expiration
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
                <Chip
                  key="all"
                  label={
                    <Typography
                      component="span"
                      sx={{
                        fontFamily: "var(--font-geist-mono)",
                        fontSize: "0.72rem",
                        fontWeight: 600,
                      }}
                    >
                      All
                    </Typography>
                  }
                  size="small"
                  onClick={() => setSelectedExpiration("all")}
                  sx={{
                    bgcolor:
                      selectedExpiration === "all"
                        ? "#3b89ff"
                        : "action.selected",
                    color:
                      selectedExpiration === "all" ? "#fff" : "text.primary",
                    border: "1px solid",
                    borderColor:
                      selectedExpiration === "all" ? "#3b89ff" : "divider",
                    cursor: "pointer",
                    "&:hover": { opacity: 0.85 },
                  }}
                />
                {chain.expirations.map((date) => (
                  <Chip
                    key={date}
                    label={
                      <Typography
                        component="span"
                        sx={{
                          fontFamily: "var(--font-geist-mono)",
                          fontSize: "0.72rem",
                          fontWeight: 600,
                        }}
                      >
                        {date}
                      </Typography>
                    }
                    size="small"
                    onClick={() => setSelectedExpiration(date)}
                    sx={{
                      bgcolor:
                        selectedExpiration === date
                          ? "#3b89ff"
                          : "action.selected",
                      color:
                        selectedExpiration === date ? "#fff" : "text.primary",
                      border: "1px solid",
                      borderColor:
                        selectedExpiration === date ? "#3b89ff" : "divider",
                      cursor: "pointer",
                      "&:hover": { opacity: 0.85 },
                    }}
                  />
                ))}
              </Box>
            </CardContent>
          </Card>

          <Card>
            <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
              <Box sx={{ p: 2, pb: 1 }}>
                <Typography variant="body2" sx={{ fontWeight: 700 }}>
                  合约明细 · Contract Details
                  {selectedExpiration !== "all" && (
                    <Typography
                      component="span"
                      sx={{
                        ...monoStyle,
                        fontSize: "0.75rem",
                        ml: 1,
                        color: "text.secondary",
                      }}
                    >
                      {selectedExpiration}
                    </Typography>
                  )}
                </Typography>
              </Box>
              <Box sx={{ overflowX: "auto" }}>
                {loadingDetail ? (
                  <Box sx={{ p: 2 }}>
                    {["a", "b", "c", "d", "e", "f", "g", "h"].map((id) => (
                      <Skeleton
                        key={`tbl-skel-${id}`}
                        variant="rectangular"
                        height={28}
                        sx={{ mb: 0.5, borderRadius: 0.5 }}
                      />
                    ))}
                  </Box>
                ) : sortedContracts.length === 0 ? (
                  <Box sx={{ p: 3 }}>
                    <Alert severity="info" sx={{ border: "none" }}>
                      暂无合约数据 · No contract data available
                    </Alert>
                  </Box>
                ) : (
                  <Table size="small" sx={{ minWidth: 900 }}>
                    <TableHead>
                      <TableRow>
                        <TableCell sx={headCellSx}>Type</TableCell>
                        {selectedExpiration === "all" && (
                          <TableCell sx={headCellSx}>Expiration</TableCell>
                        )}
                        {cols.map((col) => (
                          <TableCell key={col.id} align="right" sx={headCellSx}>
                            <TableSortLabel
                              active={sortCol === col.id}
                              direction={sortCol === col.id ? sortDir : "asc"}
                              onClick={() => handleSort(col.id)}
                            >
                              {col.label}
                            </TableSortLabel>
                          </TableCell>
                        ))}
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {sortedContracts.map((c) => {
                        const isCall = c.option_type === "c";
                        const typeColor = isCall ? "#36bb80" : "#ff7134";
                        return (
                          <TableRow
                            key={`${c.expiration}-${c.option_type}-${c.strike}`}
                            sx={{ "&:hover": { bgcolor: "action.hover" } }}
                          >
                            <TableCell
                              sx={{
                                ...cellSx,
                                fontWeight: 700,
                                color: typeColor,
                              }}
                            >
                              {isCall ? "Call" : "Put"}
                            </TableCell>
                            {selectedExpiration === "all" && (
                              <TableCell
                                sx={{ ...cellSx, color: "text.secondary" }}
                              >
                                {c.expiration}
                              </TableCell>
                            )}
                            <TableCell align="right" sx={cellSx}>
                              {fmt(c.strike, 2)}
                            </TableCell>
                            <TableCell align="right" sx={cellSx}>
                              {fmt(c.bid, 2)}
                            </TableCell>
                            <TableCell align="right" sx={cellSx}>
                              {fmt(c.ask, 2)}
                            </TableCell>
                            <TableCell align="right" sx={cellSx}>
                              {c.implied_volatility != null
                                ? `${(c.implied_volatility * 100).toFixed(1)}%`
                                : "—"}
                            </TableCell>
                            <TableCell
                              align="right"
                              sx={{
                                ...cellSx,
                                color: isCall ? "#36bb80" : "#ff7134",
                              }}
                            >
                              {c.delta != null ? fmt(c.delta, 4) : "—"}
                            </TableCell>
                            <TableCell align="right" sx={cellSx}>
                              {c.gamma != null ? fmt(c.gamma, 4) : "—"}
                            </TableCell>
                            <TableCell
                              align="right"
                              sx={{ ...cellSx, color: "text.secondary" }}
                            >
                              {c.theta != null ? fmt(c.theta, 4) : "—"}
                            </TableCell>
                            <TableCell align="right" sx={cellSx}>
                              {c.vega != null ? fmt(c.vega, 4) : "—"}
                            </TableCell>
                            <TableCell align="right" sx={cellSx}>
                              {c.rho != null ? fmt(c.rho, 4) : "—"}
                            </TableCell>
                            <TableCell align="right" sx={cellSx}>
                              {c.volume != null
                                ? c.volume.toLocaleString()
                                : "—"}
                            </TableCell>
                            <TableCell align="right" sx={cellSx}>
                              {c.open_interest != null
                                ? c.open_interest.toLocaleString()
                                : "—"}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                )}
              </Box>
            </CardContent>
          </Card>
        </>
      )}

      {!loadingChain &&
        !loadingSymbols &&
        !chain &&
        selectedSymbol &&
        !error && (
          <Alert severity="info">
            暂无期权链数据 · No options chain data available
          </Alert>
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

  const [aiText, setAiText] = useState("");
  const [aiStreaming, setAiStreaming] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const aiPanelRef = useRef<HTMLDivElement>(null);

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

  function setField<K extends keyof BacktestParams>(
    key: K,
    value: BacktestParams[K],
  ) {
    setParams((p) => ({ ...p, [key]: value }));
  }

  async function handleRun() {
    if (!params.symbol) return;
    setRunning(true);
    setResult(null);
    setError(null);
    setAiText("");
    setAiError(null);

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
      take_profit:
        params.take_profit !== "" ? Number(params.take_profit) : null,
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

  async function handleInterpret() {
    if (!result || result.error) return;
    setAiText("");
    setAiError(null);
    setAiStreaming(true);

    const m = result.metrics;
    await interpretBacktest(
      {
        symbol: result.symbol,
        strategy: result.strategy,
        trade_count: result.trade_count,
        metrics: {
          total_trades: m.total_trades,
          win_rate: m.win_rate,
          mean_return: m.mean_return,
          sharpe_ratio: m.sharpe_ratio,
          sortino_ratio: m.sortino_ratio,
          max_drawdown: m.max_drawdown,
          profit_factor: m.profit_factor,
          calmar_ratio: m.calmar_ratio,
          final_equity: m.final_equity,
        },
      },
      (token) => {
        setAiText((prev) => prev + token);
        aiPanelRef.current?.scrollTo({
          top: aiPanelRef.current.scrollHeight,
          behavior: "smooth",
        });
      },
      (err) => {
        setAiError(err);
        setAiStreaming(false);
      },
      () => setAiStreaming(false),
    );
  }

  const metricCards =
    result && !result.error ? renderMetrics(result.metrics) : [];

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
                          sx={{
                            fontFamily: "var(--font-geist-mono)",
                            fontWeight: 700,
                            fontSize: "0.875rem",
                          }}
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
                  onChange={(e) =>
                    setField("strategy", e.target.value as StrategyType)
                  }
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

          <Typography
            variant="body2"
            sx={{ fontWeight: 700, mb: 2, color: "text.secondary" }}
          >
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
                onChange={(e) =>
                  setField("max_entry_dte", Number(e.target.value))
                }
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
                onChange={(e) =>
                  setField("max_positions", Number(e.target.value))
                }
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
                onChange={(e) =>
                  setField("commission_per_contract", Number(e.target.value))
                }
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
                onChange={(e) =>
                  setField("max_expirations", Number(e.target.value))
                }
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
              startIcon={
                running ? <CircularProgress size={16} color="inherit" /> : null
              }
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
              sx={{
                bgcolor: "rgba(59,137,255,0.1)",
                color: "#3b89ff",
                border: "1px solid rgba(59,137,255,0.25)",
              }}
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
                <Alert severity="info">
                  无权益曲线数据 · No equity curve data
                </Alert>
              )}
            </CardContent>
          </Card>

          <Box sx={{ mt: 3 }}>
            <Button
              variant="contained"
              onClick={handleInterpret}
              disabled={aiStreaming}
              startIcon={
                aiStreaming ? (
                  <CircularProgress size={16} color="inherit" />
                ) : null
              }
              sx={{
                bgcolor: "#7c4dff",
                px: 3,
                py: 1,
                fontWeight: 700,
                fontSize: "0.85rem",
                "&:hover": { bgcolor: "#651fff" },
                mb: 2,
              }}
            >
              {aiStreaming ? "分析中..." : "🤖 AI 解读 · AI Interpretation"}
            </Button>

            {aiError && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {aiError}
              </Alert>
            )}

            {(aiText || aiStreaming) && (
              <Card sx={{ border: "1px solid rgba(124,77,255,0.25)" }}>
                <CardContent>
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 700, mb: 1.5, color: "#7c4dff" }}
                  >
                    🤖 AI 分析 · AI Analysis
                  </Typography>
                  <Box
                    ref={aiPanelRef}
                    sx={{
                      maxHeight: 400,
                      overflow: "auto",
                      whiteSpace: "pre-wrap",
                      fontSize: "0.85rem",
                      lineHeight: 1.7,
                      color: "text.primary",
                    }}
                  >
                    {aiText}
                    {aiStreaming && (
                      <Box
                        component="span"
                        sx={{
                          display: "inline-block",
                          width: 6,
                          height: 14,
                          bgcolor: "#7c4dff",
                          ml: 0.3,
                          animation: "blink 1s step-end infinite",
                          "@keyframes blink": {
                            "50%": { opacity: 0 },
                          },
                        }}
                      />
                    )}
                  </Box>
                </CardContent>
              </Card>
            )}
          </Box>
        </>
      )}
    </Box>
  );
}

function GreeksCalculator() {
  const [spot, setSpot] = useState(100);
  const [strike, setStrike] = useState(100);
  const [dteDays, setDteDays] = useState(30);
  const [riskFreeRate, setRiskFreeRate] = useState(0.05);
  const [iv, setIv] = useState(0.25);
  const [optionType, setOptionType] = useState<"call" | "put">("call");
  const [greeks, setGreeks] = useState<GreeksResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCalculate = useCallback(async () => {
    setLoading(true);
    setError(null);
    const req: GreeksRequest = {
      spot,
      strike,
      dte_days: dteDays,
      risk_free_rate: riskFreeRate,
      iv,
      option_type: optionType,
    };
    try {
      const res = await calculateGreeks(req);
      setGreeks(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Calculation failed");
    } finally {
      setLoading(false);
    }
  }, [spot, strike, dteDays, riskFreeRate, iv, optionType]);

  return (
    <Box component="section" id="greeks" sx={{ mb: 6 }}>
      <SectionHeader
        number="04"
        title="希腊字母计算器"
        subtitle="Greeks Calculator"
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="body2" sx={{ fontWeight: 700, mb: 2 }}>
            参数输入 · Input Parameters
          </Typography>

          <Grid container spacing={2}>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="标的价格 Spot"
                type="number"
                size="small"
                fullWidth
                value={spot}
                onChange={(e) => setSpot(Number(e.target.value))}
                slotProps={{ htmlInput: { min: 0.01, step: 1 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="行权价 Strike"
                type="number"
                size="small"
                fullWidth
                value={strike}
                onChange={(e) => setStrike(Number(e.target.value))}
                slotProps={{ htmlInput: { min: 0.01, step: 1 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="距到期天数 DTE"
                type="number"
                size="small"
                fullWidth
                value={dteDays}
                onChange={(e) => setDteDays(Number(e.target.value))}
                slotProps={{ htmlInput: { min: 0, max: 3650, step: 1 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="无风险利率 Risk-Free"
                type="number"
                size="small"
                fullWidth
                value={riskFreeRate}
                onChange={(e) => setRiskFreeRate(Number(e.target.value))}
                slotProps={{ htmlInput: { min: 0, max: 1, step: 0.01 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <TextField
                label="隐含波动率 IV"
                type="number"
                size="small"
                fullWidth
                value={iv}
                onChange={(e) => setIv(Number(e.target.value))}
                slotProps={{ htmlInput: { min: 0.01, max: 5, step: 0.01 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <FormControl fullWidth size="small">
                <InputLabel>期权类型 Type</InputLabel>
                <Select
                  value={optionType}
                  label="期权类型 Type"
                  onChange={(e) =>
                    setOptionType(e.target.value as "call" | "put")
                  }
                >
                  <MenuItem value="call">Call 看涨</MenuItem>
                  <MenuItem value="put">Put 看跌</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>

          <Box sx={{ mt: 3 }}>
            <Button
              variant="contained"
              size="large"
              onClick={handleCalculate}
              disabled={loading}
              startIcon={
                loading ? <CircularProgress size={16} color="inherit" /> : null
              }
              sx={{
                bgcolor: "#36bb80",
                px: 4,
                py: 1.2,
                fontWeight: 700,
                fontSize: "0.9rem",
                "&:hover": { bgcolor: "#2a9a68" },
              }}
            >
              {loading ? "计算中..." : "计算 Calculate"}
            </Button>
          </Box>
        </CardContent>
      </Card>

      {greeks && (
        <Grid container spacing={2}>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Card sx={{ height: "100%" }}>
              <CardContent sx={{ pb: "16px !important" }}>
                <Typography
                  variant="caption"
                  sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                >
                  Price
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}
                >
                  期权价格
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontFamily: "var(--font-geist-mono)",
                    fontWeight: 700,
                    fontSize: "1.25rem",
                    color: "#3b89ff",
                  }}
                >
                  {fmt(greeks.price, 2)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Card sx={{ height: "100%" }}>
              <CardContent sx={{ pb: "16px !important" }}>
                <Typography
                  variant="caption"
                  sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                >
                  Delta
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}
                >
                  Delta
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontFamily: "var(--font-geist-mono)",
                    fontWeight: 700,
                    fontSize: "1.25rem",
                    color: greeks.delta >= 0 ? "#36bb80" : "#ff7134",
                  }}
                >
                  {fmt(greeks.delta, 4)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Card sx={{ height: "100%" }}>
              <CardContent sx={{ pb: "16px !important" }}>
                <Typography
                  variant="caption"
                  sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                >
                  Gamma
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}
                >
                  Gamma
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontFamily: "var(--font-geist-mono)",
                    fontWeight: 700,
                    fontSize: "1.25rem",
                    color: "#3b89ff",
                  }}
                >
                  {fmt(greeks.gamma, 4)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Card sx={{ height: "100%" }}>
              <CardContent sx={{ pb: "16px !important" }}>
                <Typography
                  variant="caption"
                  sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                >
                  Theta
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}
                >
                  Theta
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontFamily: "var(--font-geist-mono)",
                    fontWeight: 700,
                    fontSize: "1.25rem",
                    color: "#ff7134",
                  }}
                >
                  {fmt(greeks.theta, 4)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Card sx={{ height: "100%" }}>
              <CardContent sx={{ pb: "16px !important" }}>
                <Typography
                  variant="caption"
                  sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                >
                  Vega
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}
                >
                  Vega
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontFamily: "var(--font-geist-mono)",
                    fontWeight: 700,
                    fontSize: "1.25rem",
                    color: "#36bb80",
                  }}
                >
                  {fmt(greeks.vega, 4)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Card sx={{ height: "100%" }}>
              <CardContent sx={{ pb: "16px !important" }}>
                <Typography
                  variant="caption"
                  sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                >
                  Rho
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}
                >
                  Rho
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontFamily: "var(--font-geist-mono)",
                    fontWeight: 700,
                    fontSize: "1.25rem",
                  }}
                >
                  {fmt(greeks.rho, 4)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  );
}

interface IVSkewChartProps {
  callPoints: { strike: number; implied_volatility: number }[];
  putPoints: { strike: number; implied_volatility: number }[];
}

function IVSkewChart({ callPoints, putPoints }: IVSkewChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { mode } = useThemeMode();

  useEffect(() => {
    if (!containerRef.current) return;
    if (callPoints.length === 0 && putPoints.length === 0) return;

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
        height: 280,
        layout: { background: { color: bg }, textColor },
        grid: {
          vertLines: { color: gridColor },
          horzLines: { color: gridColor },
        },
        crosshair: { mode: lc.CrosshairMode.Normal },
        rightPriceScale: { borderColor: gridColor },
        timeScale: { borderColor: gridColor, timeVisible: false },
      });

      if (callPoints.length > 0) {
        const callSeries = chart.addSeries(lc.LineSeries, {
          color: "#36bb80",
          lineWidth: 2,
          title: "Calls",
          crosshairMarkerVisible: true,
          crosshairMarkerRadius: 4,
        });
        const callData = callPoints
          .toSorted((a, b) => a.strike - b.strike)
          .map((p) => ({
            time: p.strike as unknown as import("lightweight-charts").Time,
            value: p.implied_volatility * 100,
          }));
        callSeries.setData(callData);
      }

      if (putPoints.length > 0) {
        const putSeries = chart.addSeries(lc.LineSeries, {
          color: "#ff7134",
          lineWidth: 2,
          title: "Puts",
          crosshairMarkerVisible: true,
          crosshairMarkerRadius: 4,
        });
        const putData = putPoints
          .toSorted((a, b) => a.strike - b.strike)
          .map((p) => ({
            time: p.strike as unknown as import("lightweight-charts").Time,
            value: p.implied_volatility * 100,
          }));
        putSeries.setData(putData);
      }

      chart.timeScale().fitContent();

      resizeObserver = new ResizeObserver(() => {
        if (chart && el) chart.applyOptions({ width: el.clientWidth });
      });
      resizeObserver.observe(el);
    }

    init();

    return () => {
      resizeObserver?.disconnect();
      chart?.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mode captured via closure
  }, [callPoints, putPoints]);

  return <Box ref={containerRef} sx={{ width: "100%", minHeight: 280 }} />;
}

interface IVTermStructureChartProps {
  points: { dte_days: number; atm_iv: number }[];
}

function IVTermStructureChart({ points }: IVTermStructureChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { mode } = useThemeMode();

  useEffect(() => {
    if (!containerRef.current || points.length === 0) return;

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
        height: 280,
        layout: { background: { color: bg }, textColor },
        grid: {
          vertLines: { color: gridColor },
          horzLines: { color: gridColor },
        },
        crosshair: { mode: lc.CrosshairMode.Normal },
        rightPriceScale: { borderColor: gridColor },
        timeScale: { borderColor: gridColor, timeVisible: false },
      });

      const series = chart.addSeries(lc.LineSeries, {
        color: "#3b89ff",
        lineWidth: 2,
        title: "ATM IV",
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
        lastValueVisible: true,
      });

      const sorted = points.toSorted((a, b) => a.dte_days - b.dte_days);
      const seriesData = sorted.map((p) => ({
        time: p.dte_days as unknown as import("lightweight-charts").Time,
        value: p.atm_iv * 100,
      }));

      series.setData(seriesData);
      chart.timeScale().fitContent();

      resizeObserver = new ResizeObserver(() => {
        if (chart && el) chart.applyOptions({ width: el.clientWidth });
      });
      resizeObserver.observe(el);
    }

    init();

    return () => {
      resizeObserver?.disconnect();
      chart?.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mode captured via closure
  }, [points]);

  return <Box ref={containerRef} sx={{ width: "100%", minHeight: 280 }} />;
}

function ivGaugeColor(value: number): string {
  if (value < 30) return "#36bb80";
  if (value <= 70) return "#fdbc2a";
  return "#ff7134";
}

function IVGauge({ label, value }: { label: string; value: number }) {
  const clamped = Math.min(100, Math.max(0, value));
  const color = ivGaugeColor(clamped);
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 1,
      }}
    >
      <Box sx={{ position: "relative", display: "inline-flex" }}>
        <CircularProgress
          variant="determinate"
          value={100}
          size={100}
          thickness={4}
          sx={{ color: "action.disabledBackground", position: "absolute" }}
        />
        <CircularProgress
          variant="determinate"
          value={clamped}
          size={100}
          thickness={4}
          sx={{ color }}
        />
        <Box
          sx={{
            top: 0,
            left: 0,
            bottom: 0,
            right: 0,
            position: "absolute",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Typography
            variant="body1"
            sx={{
              fontFamily: "var(--font-geist-mono)",
              fontWeight: 700,
              color,
              fontSize: "1.1rem",
            }}
          >
            {Math.round(clamped)}
          </Typography>
        </Box>
      </Box>
      <Typography variant="caption" sx={{ color: "text.secondary" }}>
        {label}
      </Typography>
    </Box>
  );
}

function IVAnalysisSection() {
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<SymbolInfo | null>(null);
  const [ivData, setIvData] = useState<IVAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingSymbols, setLoadingSymbols] = useState(true);

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
    setLoading(true);
    setIvData(null);
    setError(null);
    fetchIVAnalysis(selectedSymbol.symbol)
      .then((data) => setIvData(data))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load IV data"),
      )
      .finally(() => setLoading(false));
  }, [selectedSymbol]);

  const callPoints =
    ivData?.skew_points.filter((p) => p.option_type === "c") ?? [];
  const putPoints =
    ivData?.skew_points.filter((p) => p.option_type === "p") ?? [];

  return (
    <Box component="section" id="iv-analysis" sx={{ mb: 6 }}>
      <SectionHeader
        number="05"
        title="IV Analysis · 隐含波动率分析"
        subtitle="IV Rank, Percentile, Skew & Term Structure"
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
              <Typography
                variant="body2"
                sx={{ fontFamily: "var(--font-geist-mono)", fontWeight: 700 }}
              >
                {opt.symbol}
              </Typography>
              <Typography
                variant="caption"
                sx={{ ml: 1, color: "text.secondary" }}
              >
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

      {loading && (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <Box sx={{ display: "flex", gap: 3, mb: 1 }}>
            <Skeleton variant="circular" width={100} height={100} />
            <Skeleton variant="circular" width={100} height={100} />
          </Box>
          <Box sx={{ display: "flex", gap: 2 }}>
            {(["atm", "h52", "l52", "skew", "vrp"] as const).map((k) => (
              <Skeleton
                key={`iv-skel-${k}`}
                variant="rounded"
                height={80}
                sx={{ flex: 1 }}
              />
            ))}
          </Box>
          <Skeleton variant="rounded" height={280} />
          <Skeleton variant="rounded" height={280} />
        </Box>
      )}

      {!loading && ivData && !ivData.error && (
        <>
          <Box sx={{ display: "flex", gap: 4, mb: 3, flexWrap: "wrap" }}>
            <IVGauge label="IV Rank" value={ivData.iv_rank} />
            <IVGauge label="IV Percentile" value={ivData.iv_percentile} />
            <Box
              sx={{
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                gap: 0.5,
              }}
            >
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                {ivData.symbol} · Spot
              </Typography>
              <Typography
                variant="h5"
                sx={{
                  fontFamily: "var(--font-geist-mono)",
                  fontWeight: 700,
                  color: "#3b89ff",
                }}
              >
                ${fmt(ivData.spot_price, 2)}
              </Typography>
            </Box>
          </Box>

          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent sx={{ pb: "16px !important" }}>
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                  >
                    ATM IV
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}
                  >
                    平价隐波
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 700,
                      fontSize: "1.25rem",
                      color: "#3b89ff",
                    }}
                  >
                    {fmt(ivData.current_atm_iv * 100, 1)}%
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent sx={{ pb: "16px !important" }}>
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                  >
                    52W IV High
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}
                  >
                    年度最高隐波
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 700,
                      fontSize: "1.25rem",
                      color: "#ff7134",
                    }}
                  >
                    {fmt(ivData.iv_high_52w * 100, 1)}%
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent sx={{ pb: "16px !important" }}>
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                  >
                    52W IV Low
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}
                  >
                    年度最低隐波
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 700,
                      fontSize: "1.25rem",
                      color: "#36bb80",
                    }}
                  >
                    {fmt(ivData.iv_low_52w * 100, 1)}%
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent sx={{ pb: "16px !important" }}>
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                  >
                    Put/Call Skew
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}
                  >
                    认沽/认购偏斜
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 700,
                      fontSize: "1.25rem",
                      color: ivData.put_call_skew > 0 ? "#ff7134" : "#36bb80",
                    }}
                  >
                    {ivData.put_call_skew > 0 ? "+" : ""}
                    {fmt(ivData.put_call_skew * 100, 2)}%
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent sx={{ pb: "16px !important" }}>
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                  >
                    IV-RV Spread
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}
                  >
                    波动率风险溢价
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 700,
                      fontSize: "1.25rem",
                      color: ivData.iv_rv_spread > 0 ? "#fdbc2a" : "#3b89ff",
                    }}
                  >
                    {ivData.iv_rv_spread > 0 ? "+" : ""}
                    {fmt(ivData.iv_rv_spread * 100, 2)}%
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography
                variant="body2"
                sx={{ fontWeight: 700, mb: 2, fontSize: "0.85rem" }}
              >
                IV Skew · 波动率微笑
              </Typography>
              <Box sx={{ display: "flex", gap: 2, mb: 1.5 }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                  <Box
                    sx={{
                      width: 24,
                      height: 3,
                      borderRadius: 2,
                      bgcolor: "#36bb80",
                    }}
                  />
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary" }}
                  >
                    Calls 认购
                  </Typography>
                </Box>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                  <Box
                    sx={{
                      width: 24,
                      height: 3,
                      borderRadius: 2,
                      bgcolor: "#ff7134",
                    }}
                  />
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary" }}
                  >
                    Puts 认沽
                  </Typography>
                </Box>
                <Typography
                  variant="caption"
                  sx={{ color: "text.secondary", ml: "auto" }}
                >
                  X: Strike · Y: IV%
                </Typography>
              </Box>
              {callPoints.length === 0 && putPoints.length === 0 ? (
                <Alert severity="info">No skew data available</Alert>
              ) : (
                <IVSkewChart callPoints={callPoints} putPoints={putPoints} />
              )}
            </CardContent>
          </Card>

          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography
                variant="body2"
                sx={{ fontWeight: 700, mb: 2, fontSize: "0.85rem" }}
              >
                IV Term Structure · 期限结构
              </Typography>
              <Typography
                variant="caption"
                sx={{ color: "text.secondary", display: "block", mb: 1.5 }}
              >
                X: DTE (days to expiration) · Y: ATM IV%
              </Typography>
              {ivData.term_structure.length === 0 ? (
                <Alert severity="info">No term structure data available</Alert>
              ) : (
                <IVTermStructureChart points={ivData.term_structure} />
              )}
            </CardContent>
          </Card>

          {ivData.hv_points.length > 0 && (
            <Box>
              <Typography
                variant="body2"
                sx={{ fontWeight: 700, mb: 2, fontSize: "0.85rem" }}
              >
                Historical Volatility Comparison · 历史波动率对比
              </Typography>
              <Grid container spacing={2}>
                {ivData.hv_points.map((hv) => {
                  const hvPct = hv.realized_vol * 100;
                  const atmPct = ivData.current_atm_iv * 100;
                  const diff = atmPct - hvPct;
                  return (
                    <Grid key={hv.window_days} size={{ xs: 6, sm: 4, md: 3 }}>
                      <Card sx={{ height: "100%" }}>
                        <CardContent sx={{ pb: "16px !important" }}>
                          <Box
                            sx={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "flex-start",
                              mb: 1,
                            }}
                          >
                            <Typography
                              variant="caption"
                              sx={{
                                color: "text.secondary",
                                display: "block",
                              }}
                            >
                              {hv.label}
                            </Typography>
                            <Chip
                              label={
                                diff > 0
                                  ? `IV +${fmt(diff, 1)}%`
                                  : `IV ${fmt(diff, 1)}%`
                              }
                              size="small"
                              sx={{
                                fontSize: "0.65rem",
                                height: 18,
                                bgcolor:
                                  diff > 0
                                    ? "rgba(253,188,42,0.15)"
                                    : "rgba(54,187,128,0.15)",
                                color: diff > 0 ? "#d49a14" : "#36bb80",
                                border: `1px solid ${diff > 0 ? "rgba(253,188,42,0.3)" : "rgba(54,187,128,0.3)"}`,
                              }}
                            />
                          </Box>
                          <Typography
                            variant="h6"
                            sx={{
                              fontFamily: "var(--font-geist-mono)",
                              fontWeight: 700,
                              fontSize: "1.25rem",
                              color: "#8899aa",
                            }}
                          >
                            {fmt(hvPct, 1)}%
                          </Typography>
                          <Typography
                            variant="caption"
                            sx={{ color: "text.secondary" }}
                          >
                            ATM IV:{" "}
                            <Box
                              component="span"
                              sx={{
                                fontFamily: "var(--font-geist-mono)",
                                color: "#3b89ff",
                              }}
                            >
                              {fmt(atmPct, 1)}%
                            </Box>
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                  );
                })}
              </Grid>
            </Box>
          )}
        </>
      )}

      {!loading && ivData?.error && (
        <Alert severity="warning">{ivData.error}</Alert>
      )}

      {!loading && !ivData && selectedSymbol && !error && (
        <Alert severity="info">正在等待数据 · Waiting for IV data</Alert>
      )}
    </Box>
  );
}

interface LegFormState {
  id: string;
  option_type: "c" | "p";
  action: "buy" | "sell";
  strike: number;
  quantity: number;
  premium: number;
  iv: number;
}

const STRATEGY_TEMPLATES: Record<
  string,
  {
    label: string;
    legs: { option_type: "c" | "p"; action: "buy" | "sell"; strike_offset: number }[];
  }
> = {
  custom: { label: "Custom", legs: [] },
  bull_call_spread: {
    label: "Bull Call Spread",
    legs: [
      { option_type: "c", action: "buy", strike_offset: -5 },
      { option_type: "c", action: "sell", strike_offset: 5 },
    ],
  },
  bear_put_spread: {
    label: "Bear Put Spread",
    legs: [
      { option_type: "p", action: "buy", strike_offset: 5 },
      { option_type: "p", action: "sell", strike_offset: -5 },
    ],
  },
  long_straddle: {
    label: "Long Straddle",
    legs: [
      { option_type: "c", action: "buy", strike_offset: 0 },
      { option_type: "p", action: "buy", strike_offset: 0 },
    ],
  },
  long_strangle: {
    label: "Long Strangle",
    legs: [
      { option_type: "c", action: "buy", strike_offset: 5 },
      { option_type: "p", action: "buy", strike_offset: -5 },
    ],
  },
  iron_condor: {
    label: "Iron Condor",
    legs: [
      { option_type: "p", action: "buy", strike_offset: -10 },
      { option_type: "p", action: "sell", strike_offset: -5 },
      { option_type: "c", action: "sell", strike_offset: 5 },
      { option_type: "c", action: "buy", strike_offset: 10 },
    ],
  },
  iron_butterfly: {
    label: "Iron Butterfly",
    legs: [
      { option_type: "p", action: "buy", strike_offset: -10 },
      { option_type: "p", action: "sell", strike_offset: 0 },
      { option_type: "c", action: "sell", strike_offset: 0 },
      { option_type: "c", action: "buy", strike_offset: 10 },
    ],
  },
};

interface PnLChartProps {
  pnlCurve: { price: number; pnl: number }[];
}

function PnLChart({ pnlCurve }: PnLChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { mode } = useThemeMode();

  useEffect(() => {
    if (!containerRef.current || pnlCurve.length === 0) return;

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
        height: 300,
        layout: { background: { color: bg }, textColor },
        grid: {
          vertLines: { color: gridColor },
          horzLines: { color: gridColor },
        },
        crosshair: { mode: lc.CrosshairMode.Normal },
        rightPriceScale: { borderColor: gridColor },
        timeScale: { borderColor: gridColor, timeVisible: false },
      });

      const sorted = pnlCurve.toSorted((a, b) => a.price - b.price);

      const baselineSeries = chart.addSeries(lc.BaselineSeries, {
        baseValue: { type: "price", price: 0 },
        topLineColor: "#00c853",
        topFillColor1: "rgba(0,200,83,0.28)",
        topFillColor2: "rgba(0,200,83,0.05)",
        bottomLineColor: "#ff1744",
        bottomFillColor1: "rgba(255,23,68,0.05)",
        bottomFillColor2: "rgba(255,23,68,0.28)",
        lineWidth: 2,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
      });

      const seriesData = sorted.map((p) => ({
        time: p.price as unknown as import("lightweight-charts").Time,
        value: p.pnl,
      }));

      baselineSeries.setData(seriesData);

      chart.timeScale().fitContent();

      resizeObserver = new ResizeObserver(() => {
        if (chart && el) chart.applyOptions({ width: el.clientWidth });
      });
      resizeObserver.observe(el);
    }

    init();

    return () => {
      resizeObserver?.disconnect();
      chart?.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mode captured via closure
  }, [pnlCurve]);

  return <Box ref={containerRef} sx={{ width: "100%", minHeight: 300 }} />;
}

let legIdCounter = 0;
function newLegId(): string {
  legIdCounter += 1;
  return `leg-${legIdCounter}`;
}

function StrategyBuilderSection() {
  const [spot, setSpot] = useState(100);
  const [dteDays, setDteDays] = useState(30);
  const [riskFreeRate, setRiskFreeRate] = useState(0.05);
  const [selectedTemplate, setSelectedTemplate] = useState("custom");
  const [legs, setLegs] = useState<LegFormState[]>([]);
  const [result, setResult] = useState<MultiLegResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applyTemplate = useCallback(
    (templateKey: string, currentSpot: number) => {
      setSelectedTemplate(templateKey);
      const tpl = STRATEGY_TEMPLATES[templateKey];
      if (!tpl || tpl.legs.length === 0) {
        setLegs([]);
        return;
      }
      const newLegs: LegFormState[] = tpl.legs.map((l) => ({
        id: newLegId(),
        option_type: l.option_type,
        action: l.action,
        strike: currentSpot + l.strike_offset,
        quantity: 1,
        premium: 2.0,
        iv: 0.3,
      }));
      setLegs(newLegs);
    },
    [],
  );

  const updateLeg = useCallback(
    (id: string, field: keyof Omit<LegFormState, "id">, value: string | number) => {
      setLegs((prev) =>
        prev.map((leg) => (leg.id === id ? { ...leg, [field]: value } : leg)),
      );
    },
    [],
  );

  const removeLeg = useCallback((id: string) => {
    setLegs((prev) => prev.filter((leg) => leg.id !== id));
  }, []);

  const addLeg = useCallback(() => {
    setLegs((prev) => [
      ...prev,
      {
        id: newLegId(),
        option_type: "c",
        action: "buy",
        strike: spot,
        quantity: 1,
        premium: 2.0,
        iv: 0.3,
      },
    ]);
  }, [spot]);

  const handleAnalyze = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    const legInputs: OptionLegInput[] = legs.map((l) => ({
      option_type: l.option_type,
      action: l.action,
      strike: l.strike,
      expiration: "2025-01-17",
      quantity: l.quantity,
      premium: l.premium,
      iv: l.iv,
    }));
    try {
      const res = await analyzeMultiLeg({
        legs: legInputs,
        spot,
        dte_days: dteDays,
        risk_free_rate: riskFreeRate,
      });
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }, [legs, spot, dteDays, riskFreeRate]);

  const netColor =
    result && result.net_debit_credit < 0 ? "#00c853" : "#ff1744";

  return (
    <Box component="section" id="strategy-builder" sx={{ mb: 6 }}>
      <SectionHeader
        number="05"
        title="策略构建器"
        subtitle="Strategy Builder — Multi-leg P&L, breakevens & aggregated Greeks"
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid size={{ xs: 6, sm: 3, md: 2 }}>
              <TextField
                label="标的价格 Spot"
                type="number"
                size="small"
                fullWidth
                value={spot}
                onChange={(e) => setSpot(Number(e.target.value))}
                slotProps={{ htmlInput: { min: 0.01, step: 1 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 3, md: 2 }}>
              <TextField
                label="距到期天数 DTE"
                type="number"
                size="small"
                fullWidth
                value={dteDays}
                onChange={(e) => setDteDays(Number(e.target.value))}
                slotProps={{ htmlInput: { min: 0, max: 3650, step: 1 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 3, md: 2 }}>
              <TextField
                label="无风险利率 Risk-Free"
                type="number"
                size="small"
                fullWidth
                value={riskFreeRate}
                onChange={(e) => setRiskFreeRate(Number(e.target.value))}
                slotProps={{ htmlInput: { min: 0, max: 1, step: 0.01 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 3, md: 3 }}>
              <FormControl fullWidth size="small">
                <InputLabel>策略模板 Template</InputLabel>
                <Select
                  value={selectedTemplate}
                  label="策略模板 Template"
                  onChange={(e) => applyTemplate(e.target.value, spot)}
                >
                  {Object.entries(STRATEGY_TEMPLATES).map(([key, tpl]) => (
                    <MenuItem key={key} value={key}>
                      {tpl.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>

          <Typography variant="body2" sx={{ fontWeight: 700, mb: 1.5, fontSize: "0.85rem" }}>
            期权腿 · Option Legs
          </Typography>

          {legs.map((leg) => (
            <Box
              key={leg.id}
              sx={{
                display: "flex",
                flexWrap: "wrap",
                gap: 1,
                mb: 1.5,
                alignItems: "center",
                p: 1.5,
                borderRadius: 1,
                border: "1px solid",
                borderColor: "divider",
              }}
            >
              <FormControl size="small" sx={{ minWidth: 90 }}>
                <InputLabel>类型</InputLabel>
                <Select
                  value={leg.option_type}
                  label="类型"
                  onChange={(e) =>
                    updateLeg(leg.id, "option_type", e.target.value as "c" | "p")
                  }
                >
                  <MenuItem value="c">Call</MenuItem>
                  <MenuItem value="p">Put</MenuItem>
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 90 }}>
                <InputLabel>方向</InputLabel>
                <Select
                  value={leg.action}
                  label="方向"
                  onChange={(e) =>
                    updateLeg(leg.id, "action", e.target.value as "buy" | "sell")
                  }
                >
                  <MenuItem value="buy">Buy</MenuItem>
                  <MenuItem value="sell">Sell</MenuItem>
                </Select>
              </FormControl>
              <TextField
                label="Strike"
                type="number"
                size="small"
                sx={{ width: 90 }}
                value={leg.strike}
                onChange={(e) => updateLeg(leg.id, "strike", Number(e.target.value))}
                slotProps={{ htmlInput: { min: 0.01, step: 1 } }}
              />
              <TextField
                label="Premium"
                type="number"
                size="small"
                sx={{ width: 90 }}
                value={leg.premium}
                onChange={(e) => updateLeg(leg.id, "premium", Number(e.target.value))}
                slotProps={{ htmlInput: { min: 0, step: 0.01 } }}
              />
              <TextField
                label="IV"
                type="number"
                size="small"
                sx={{ width: 80 }}
                value={leg.iv}
                onChange={(e) => updateLeg(leg.id, "iv", Number(e.target.value))}
                slotProps={{ htmlInput: { min: 0.01, max: 5, step: 0.01 } }}
              />
              <TextField
                label="Qty"
                type="number"
                size="small"
                sx={{ width: 70 }}
                value={leg.quantity}
                onChange={(e) => updateLeg(leg.id, "quantity", Number(e.target.value))}
                slotProps={{ htmlInput: { min: 1, step: 1 } }}
              />
              <IconButton
                size="small"
                onClick={() => removeLeg(leg.id)}
                sx={{ color: "text.secondary", ml: "auto" }}
              >
                ✕
              </IconButton>
            </Box>
          ))}

          <Box sx={{ display: "flex", gap: 2, mt: 2 }}>
            <Button
              variant="outlined"
              size="small"
              onClick={addLeg}
              disabled={legs.length >= 4}
            >
              Add Leg
            </Button>
            <Button
              variant="contained"
              size="large"
              onClick={handleAnalyze}
              disabled={legs.length === 0 || loading}
              startIcon={
                loading ? <CircularProgress size={16} color="inherit" /> : null
              }
              sx={{
                bgcolor: "#3b89ff",
                px: 4,
                py: 1.2,
                fontWeight: 700,
                fontSize: "0.9rem",
                "&:hover": { bgcolor: "#2a6ed4" },
              }}
            >
              {loading ? "分析中..." : "Analyze Strategy"}
            </Button>
          </Box>
        </CardContent>
      </Card>

      {result && !result.error && (
        <>
          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent sx={{ pb: "16px !important" }}>
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                  >
                    Net Debit/Credit
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}>
                    净权利金
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 700,
                      fontSize: "1.25rem",
                      color: netColor,
                    }}
                  >
                    {fmtMoney(result.net_debit_credit)}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    {result.net_debit_credit < 0 ? "Credit 收权利金" : "Debit 付权利金"}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent sx={{ pb: "16px !important" }}>
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                  >
                    Max Profit
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}>
                    最大盈利
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 700,
                      fontSize: "1.25rem",
                      color: "#00c853",
                    }}
                  >
                    {result.max_profit >= 999_999_999
                      ? "Unlimited"
                      : fmtMoney(result.max_profit)}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent sx={{ pb: "16px !important" }}>
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                  >
                    Max Loss
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}>
                    最大亏损
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 700,
                      fontSize: "1.25rem",
                      color: "#ff1744",
                    }}
                  >
                    {result.max_loss <= -999_999_999
                      ? "Unlimited"
                      : fmtMoney(result.max_loss)}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent sx={{ pb: "16px !important" }}>
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                  >
                    Breakevens
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}>
                    盈亏平衡点
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 700,
                      fontSize: "1rem",
                      color: "#3b89ff",
                    }}
                  >
                    {result.breakeven_points.length === 0
                      ? "—"
                      : result.breakeven_points
                          .map((p) => fmt(p, 2))
                          .join(", ")}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography
                variant="body2"
                sx={{ fontWeight: 700, mb: 2, fontSize: "0.85rem" }}
              >
                Aggregated Greeks · 综合希腊字母
              </Typography>
              <Grid container spacing={2}>
                {(
                  [
                    ["Delta", result.greeks.delta],
                    ["Gamma", result.greeks.gamma],
                    ["Theta", result.greeks.theta],
                    ["Vega", result.greeks.vega],
                    ["Rho", result.greeks.rho],
                  ] as [string, number][]
                ).map(([label, value]) => (
                  <Grid key={label} size={{ xs: 6, sm: 4, md: 2 }}>
                    <Card sx={{ height: "100%" }}>
                      <CardContent sx={{ pb: "16px !important" }}>
                        <Typography
                          variant="caption"
                          sx={{ color: "text.secondary", display: "block", mb: 0.5 }}
                        >
                          {label}
                        </Typography>
                        <Typography
                          variant="h6"
                          sx={{
                            fontFamily: "var(--font-geist-mono)",
                            fontWeight: 700,
                            fontSize: "1.1rem",
                            color:
                              label === "Theta"
                                ? "#ff7134"
                                : label === "Delta"
                                  ? "#3b89ff"
                                  : "text.primary",
                          }}
                        >
                          {fmt(value, 4)}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </CardContent>
          </Card>

          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography
                variant="body2"
                sx={{ fontWeight: 700, mb: 2, fontSize: "0.85rem" }}
              >
                P&L Curve · 盈亏曲线
              </Typography>
              <Typography
                variant="caption"
                sx={{ color: "text.secondary", display: "block", mb: 1.5 }}
              >
                X: Underlying Price · Y: P&L ($)
              </Typography>
              {result.pnl_curve.length === 0 ? (
                <Alert severity="info">No P&L data available</Alert>
              ) : (
                <PnLChart pnlCurve={result.pnl_curve} />
              )}
            </CardContent>
          </Card>
        </>
      )}

      {result?.error && (
        <Alert severity="error">{result.error}</Alert>
      )}
    </Box>
  );
}

export default function OptionsPage() {
  return (
    <Box sx={{ px: { xs: 2, sm: 3, md: 4 }, py: 4 }}>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h5" sx={{ fontWeight: 700, mb: 0.5 }}>
          期权工具
        </Typography>
        <Typography variant="body2" sx={{ color: "text.secondary" }}>
          Options Tools — Expirations, Chain, Backtest Simulator, Greeks
          Calculator, IV Analysis
        </Typography>
      </Box>

      <ExpirationsBrowser />
      <OptionsChainSection />
      <BacktestSimulator />
      <GreeksCalculator />
      <Divider sx={{ my: 4 }} />
      <StrategyBuilderSection />
      <Divider sx={{ my: 4 }} />
      <IVAnalysisSection />
    </Box>
  );
}
