"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import Skeleton from "@mui/material/Skeleton";
import Alert from "@mui/material/Alert";
import Chip from "@mui/material/Chip";
import Grid from "@mui/material/Grid";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Table from "@mui/material/Table";
import TableHead from "@mui/material/TableHead";
import TableBody from "@mui/material/TableBody";
import TableRow from "@mui/material/TableRow";
import TableCell from "@mui/material/TableCell";
import SectionHeader from "@/components/SectionHeader";
import { useThemeMode } from "@/components/ThemeProvider";
import { runSignalBacktest, runWalkForward } from "@/lib/api";
import type {
  SignalBacktestResponse,
  SignalBacktestMetrics,
  WalkForwardResponse,
} from "@/lib/types";

const SKELETON_METRIC_IDS = [
  "m1",
  "m2",
  "m3",
  "m4",
  "m5",
  "m6",
  "m7",
  "m8",
  "m9",
];
const SKELETON_ROW_IDS = ["r1", "r2", "r3", "r4", "r5"];
const ALL_HORIZONS = [1, 3, 5, 10, 20];

function fmt(value: number, decimals = 2): string {
  return value.toFixed(decimals);
}

function pct(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

interface EquityCurveChartProps {
  data: number[];
  dates: string[];
}

function EquityCurveChart({ data, dates }: EquityCurveChartProps) {
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
        layout: { background: { color: bg }, textColor },
        grid: {
          vertLines: { color: gridColor },
          horzLines: { color: gridColor },
        },
        crosshair: { mode: lc.CrosshairMode.Normal },
        rightPriceScale: { borderColor: gridColor },
        timeScale: { borderColor: gridColor, timeVisible: false },
      });

      const lineSeries = chart.addSeries(lc.LineSeries, {
        color: "#3b89ff",
        lineWidth: 2,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
        lastValueVisible: true,
      });

      const seriesData = data.map((value, idx) => {
        const dateStr = dates[idx];
        if (dateStr) {
          return {
            time: dateStr as import("lightweight-charts").Time,
            value,
          };
        }
        const base = new Date("2020-01-01");
        base.setDate(base.getDate() + idx);
        const yyyy = base.getFullYear();
        const mm = String(base.getMonth() + 1).padStart(2, "0");
        const dd = String(base.getDate()).padStart(2, "0");
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

function buildMetricCards(metrics: SignalBacktestMetrics): MetricCardProps[] {
  const hitColor =
    metrics.overall_hit_rate > 0.55
      ? "#36bb80"
      : metrics.overall_hit_rate < 0.45
        ? "#ff7134"
        : undefined;
  return [
    {
      label: "综合命中率",
      sublabel: "Overall Hit Rate",
      value: pct(metrics.overall_hit_rate),
      color: hitColor,
    },
    {
      label: "平均收益",
      sublabel: "Avg Return",
      value: pct(metrics.avg_return),
      color: metrics.avg_return >= 0 ? "#36bb80" : "#ff7134",
    },
    {
      label: "盈利因子",
      sublabel: "Profit Factor",
      value: fmt(metrics.profit_factor),
      color: metrics.profit_factor > 1 ? "#36bb80" : "#ff7134",
    },
    {
      label: "最大回撤",
      sublabel: "Max Drawdown",
      value: pct(metrics.max_drawdown),
      color: "#ff7134",
    },
    {
      label: "夏普比率",
      sublabel: "Sharpe Ratio",
      value: fmt(metrics.sharpe),
      color: metrics.sharpe > 1 ? "#36bb80" : undefined,
    },
    {
      label: "信号天数",
      sublabel: "Signal Days",
      value: String(metrics.signal_days),
    },
    {
      label: "强信号天数",
      sublabel: "Strong Days",
      value: String(metrics.strong_days),
      color: "#3b89ff",
    },
    {
      label: "观察信号天数",
      sublabel: "Watch Days",
      value: String(metrics.watch_days),
      color: "#fdbc2a",
    },
    {
      label: "无信号天数",
      sublabel: "No Signal Days",
      value: String(metrics.none_days),
      color: "text.secondary",
    },
  ];
}

export default function BacktestPage() {
  const [symbol, setSymbol] = useState("SPY");
  const [startDate, setStartDate] = useState("2022-01-01");
  const [endDate, setEndDate] = useState(() => {
    const d = new Date();
    return d.toISOString().split("T")[0] ?? "2024-01-01";
  });
  const [horizons, setHorizons] = useState<number[]>([1, 3, 5, 10, 20]);

  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<SignalBacktestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [wfSymbol, setWfSymbol] = useState("SPY");
  const [wfTrainDays, setWfTrainDays] = useState(252);
  const [wfTestDays, setWfTestDays] = useState(63);
  const [wfStepDays, setWfStepDays] = useState(21);
  const [wfHorizon, setWfHorizon] = useState(5);
  const [wfRunning, setWfRunning] = useState(false);
  const [wfResult, setWfResult] = useState<WalkForwardResponse | null>(null);
  const [wfError, setWfError] = useState<string | null>(null);

  const toggleHorizon = useCallback((h: number) => {
    setHorizons((prev) =>
      prev.includes(h) ? prev.filter((x) => x !== h) : [...prev, h],
    );
  }, []);

  const handleRun = useCallback(async () => {
    if (!symbol.trim()) return;
    setRunning(true);
    setResult(null);
    setError(null);
    try {
      const res = await runSignalBacktest({
        symbol: symbol.trim().toUpperCase(),
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        horizons: horizons.length > 0 ? horizons : undefined,
      });
      if (res.error) {
        setError(res.error);
      } else {
        setResult(res);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Signal backtest failed");
    } finally {
      setRunning(false);
    }
  }, [symbol, startDate, endDate, horizons]);

  const handleWfRun = useCallback(async () => {
    if (!wfSymbol.trim()) return;
    setWfRunning(true);
    setWfResult(null);
    setWfError(null);
    try {
      const res = await runWalkForward({
        symbol: wfSymbol.trim().toUpperCase(),
        train_days: wfTrainDays,
        test_days: wfTestDays,
        step_days: wfStepDays,
        horizon: wfHorizon,
      });
      if (res.error) {
        setWfError(res.error);
      } else {
        setWfResult(res);
      }
    } catch (e: unknown) {
      setWfError(e instanceof Error ? e.message : "Walk-forward failed");
    } finally {
      setWfRunning(false);
    }
  }, [wfSymbol, wfTrainDays, wfTestDays, wfStepDays, wfHorizon]);

  const metricCards =
    result && !result.error ? buildMetricCards(result.metrics) : [];

  const equityDates =
    result && result.outcomes.length > 0
      ? result.outcomes.map((o) => o.date)
      : [];

  const monoSx = { fontFamily: "var(--font-geist-mono)" } as const;
  const cellSx = { ...monoSx, fontSize: "0.75rem", py: 0.5, px: 1 } as const;
  const headCellSx = {
    ...monoSx,
    fontSize: "0.7rem",
    fontWeight: 700,
    py: 0.75,
    px: 1,
    whiteSpace: "nowrap" as const,
  } as const;

  const stabilityColor =
    wfResult && wfResult.stability_ratio >= 0.8
      ? "#36bb80"
      : wfResult && wfResult.stability_ratio >= 0.6
        ? "#fdbc2a"
        : "#ff7134";

  return (
    <Box sx={{ maxWidth: 1200, mx: "auto", px: { xs: 2, md: 3 }, py: 3 }}>
      <Box component="section" sx={{ mb: 6 }}>
        <SectionHeader
          number="01"
          title="信号回测配置"
          subtitle="Signal Backtest Config"
        />

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Grid container spacing={2} alignItems="flex-end">
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <TextField
                  label="标的 Symbol"
                  size="small"
                  fullWidth
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                  slotProps={{
                    input: {
                      sx: {
                        fontFamily: "var(--font-geist-mono)",
                        fontWeight: 700,
                      },
                    },
                  }}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <TextField
                  label="开始日期 Start Date"
                  type="date"
                  size="small"
                  fullWidth
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <TextField
                  label="结束日期 End Date"
                  type="date"
                  size="small"
                  fullWidth
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
              </Grid>
            </Grid>

            <Box sx={{ mt: 2 }}>
              <Typography
                variant="body2"
                sx={{ fontWeight: 600, mb: 1, fontSize: "0.8rem" }}
              >
                持有周期 Horizons (天 days)
              </Typography>
              <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap" }}>
                {ALL_HORIZONS.map((h) => {
                  const active = horizons.includes(h);
                  return (
                    <Chip
                      key={`horizon-${h}`}
                      label={
                        <Typography
                          component="span"
                          sx={{
                            ...monoSx,
                            fontSize: "0.75rem",
                            fontWeight: 700,
                          }}
                        >
                          {h}d
                        </Typography>
                      }
                      size="small"
                      onClick={() => toggleHorizon(h)}
                      sx={{
                        bgcolor: active ? "#3b89ff" : "action.selected",
                        color: active ? "#fff" : "text.primary",
                        border: "1px solid",
                        borderColor: active ? "#3b89ff" : "divider",
                        cursor: "pointer",
                        "&:hover": { opacity: 0.85 },
                      }}
                    />
                  );
                })}
              </Box>
            </Box>

            <Box sx={{ mt: 3 }}>
              <Button
                variant="contained"
                size="large"
                onClick={handleRun}
                disabled={running || !symbol.trim()}
                startIcon={
                  running ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : null
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
      </Box>

      {running && (
        <Box component="section" sx={{ mb: 6 }}>
          <SectionHeader number="02" title="回测结果" subtitle="Results" />
          <Grid container spacing={2} sx={{ mb: 3 }}>
            {SKELETON_METRIC_IDS.map((id) => (
              <Grid key={`mskel-${id}`} size={{ xs: 6, sm: 4, md: 3 }}>
                <Skeleton variant="rounded" height={88} />
              </Grid>
            ))}
          </Grid>
          <Skeleton variant="rounded" height={280} />
        </Box>
      )}

      {result && !result.error && (
        <>
          <Box component="section" sx={{ mb: 6 }}>
            <SectionHeader
              number="02"
              title="指标概览"
              subtitle="Metrics Dashboard"
            />
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
              <Chip
                label={result.symbol}
                size="small"
                sx={{
                  bgcolor: "rgba(59,137,255,0.1)",
                  color: "#3b89ff",
                  border: "1px solid rgba(59,137,255,0.25)",
                  fontFamily: "var(--font-geist-mono)",
                  fontWeight: 700,
                }}
              />
              <Chip
                label={`${result.start_date} → ${result.end_date}`}
                size="small"
                sx={{
                  bgcolor: "action.selected",
                  color: "text.secondary",
                  fontFamily: "var(--font-geist-mono)",
                  fontSize: "0.7rem",
                }}
              />
            </Box>
            <Grid container spacing={2}>
              {metricCards.map((card) => (
                <Grid key={card.sublabel} size={{ xs: 6, sm: 4, md: 3 }}>
                  <MetricCard {...card} />
                </Grid>
              ))}
            </Grid>
          </Box>

          <Box component="section" sx={{ mb: 6 }}>
            <SectionHeader
              number="03"
              title="权益曲线"
              subtitle="Equity Curve"
            />
            <Card>
              <CardContent>
                {result.equity_curve.length > 0 ? (
                  <EquityCurveChart
                    data={result.equity_curve}
                    dates={equityDates}
                  />
                ) : (
                  <Alert severity="info">
                    无权益曲线数据 · No equity curve data
                  </Alert>
                )}
              </CardContent>
            </Card>
          </Box>

          {result.metrics.by_horizon.length > 0 && (
            <Box component="section" sx={{ mb: 6 }}>
              <SectionHeader
                number="04"
                title="周期分析"
                subtitle="Horizon Breakdown"
              />
              <Card>
                <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
                  <Box sx={{ overflowX: "auto" }}>
                    <Table size="small" sx={{ minWidth: 820 }}>
                      <TableHead>
                        <TableRow>
                          <TableCell sx={headCellSx}>Horizon</TableCell>
                          <TableCell align="right" sx={headCellSx}>
                            Signals
                          </TableCell>
                          <TableCell align="right" sx={headCellSx}>
                            Hits
                          </TableCell>
                          <TableCell align="right" sx={headCellSx}>
                            Hit Rate
                          </TableCell>
                          <TableCell align="right" sx={headCellSx}>
                            Avg Return
                          </TableCell>
                          <TableCell align="right" sx={headCellSx}>
                            Strong Sigs
                          </TableCell>
                          <TableCell align="right" sx={headCellSx}>
                            Strong Hit%
                          </TableCell>
                          <TableCell align="right" sx={headCellSx}>
                            Watch Sigs
                          </TableCell>
                          <TableCell align="right" sx={headCellSx}>
                            Watch Hit%
                          </TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {result.metrics.by_horizon.map((row) => {
                          const hrColor =
                            row.hit_rate > 0.55
                              ? "#36bb80"
                              : row.hit_rate < 0.45
                                ? "#ff7134"
                                : "inherit";
                          return (
                            <TableRow
                              key={`horizon-row-${row.horizon}`}
                              sx={{ "&:hover": { bgcolor: "action.hover" } }}
                            >
                              <TableCell
                                sx={{
                                  ...cellSx,
                                  fontWeight: 700,
                                  color: "#3b89ff",
                                }}
                              >
                                {row.horizon}
                              </TableCell>
                              <TableCell align="right" sx={cellSx}>
                                {row.total_signals}
                              </TableCell>
                              <TableCell align="right" sx={cellSx}>
                                {row.hits}
                              </TableCell>
                              <TableCell
                                align="right"
                                sx={{
                                  ...cellSx,
                                  color: hrColor,
                                  fontWeight: 600,
                                }}
                              >
                                {pct(row.hit_rate)}
                              </TableCell>
                              <TableCell
                                align="right"
                                sx={{
                                  ...cellSx,
                                  color:
                                    row.avg_return >= 0 ? "#36bb80" : "#ff7134",
                                }}
                              >
                                {pct(row.avg_return)}
                              </TableCell>
                              <TableCell align="right" sx={cellSx}>
                                {row.strong_signals}
                              </TableCell>
                              <TableCell
                                align="right"
                                sx={{
                                  ...cellSx,
                                  color:
                                    row.strong_hit_rate > 0.55
                                      ? "#36bb80"
                                      : row.strong_hit_rate < 0.45
                                        ? "#ff7134"
                                        : "inherit",
                                }}
                              >
                                {pct(row.strong_hit_rate)}
                              </TableCell>
                              <TableCell align="right" sx={cellSx}>
                                {row.watch_signals}
                              </TableCell>
                              <TableCell
                                align="right"
                                sx={{
                                  ...cellSx,
                                  color:
                                    row.watch_hit_rate > 0.55
                                      ? "#36bb80"
                                      : row.watch_hit_rate < 0.45
                                        ? "#ff7134"
                                        : "inherit",
                                }}
                              >
                                {pct(row.watch_hit_rate)}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </Box>
                </CardContent>
              </Card>
            </Box>
          )}

          {result.metrics.by_regime.length > 0 && (
            <Box component="section" sx={{ mb: 6 }}>
              <SectionHeader
                number="05"
                title="市场环境分析"
                subtitle="Regime Breakdown"
              />
              <Card>
                <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
                  <Box sx={{ overflowX: "auto" }}>
                    <Table size="small" sx={{ minWidth: 480 }}>
                      <TableHead>
                        <TableRow>
                          <TableCell sx={headCellSx}>Regime</TableCell>
                          <TableCell align="right" sx={headCellSx}>
                            Signals
                          </TableCell>
                          <TableCell align="right" sx={headCellSx}>
                            Hit Rate
                          </TableCell>
                          <TableCell align="right" sx={headCellSx}>
                            Avg Return
                          </TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {result.metrics.by_regime.map((row) => {
                          const regimeColor =
                            row.regime === "risk_on"
                              ? "#36bb80"
                              : row.regime === "risk_off"
                                ? "#ff7134"
                                : "#fdbc2a";
                          return (
                            <TableRow
                              key={`regime-row-${row.regime}`}
                              sx={{ "&:hover": { bgcolor: "action.hover" } }}
                            >
                              <TableCell
                                sx={{
                                  ...cellSx,
                                  fontWeight: 700,
                                  color: regimeColor,
                                }}
                              >
                                {row.regime}
                              </TableCell>
                              <TableCell align="right" sx={cellSx}>
                                {row.total_signals}
                              </TableCell>
                              <TableCell
                                align="right"
                                sx={{
                                  ...cellSx,
                                  fontWeight: 600,
                                  color:
                                    row.hit_rate > 0.55
                                      ? "#36bb80"
                                      : row.hit_rate < 0.45
                                        ? "#ff7134"
                                        : "inherit",
                                }}
                              >
                                {pct(row.hit_rate)}
                              </TableCell>
                              <TableCell
                                align="right"
                                sx={{
                                  ...cellSx,
                                  color:
                                    row.avg_return >= 0 ? "#36bb80" : "#ff7134",
                                }}
                              >
                                {pct(row.avg_return)}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </Box>
                </CardContent>
              </Card>
            </Box>
          )}
        </>
      )}

      <Box component="section" sx={{ mb: 6 }}>
        <SectionHeader
          number="06"
          title="滚动验证分析"
          subtitle="Walk-Forward Analysis"
        />

        {wfError && (
          <Alert
            severity="error"
            sx={{ mb: 2 }}
            onClose={() => setWfError(null)}
          >
            {wfError}
          </Alert>
        )}

        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="body2" sx={{ fontWeight: 700, mb: 2 }}>
              配置 Configuration
            </Typography>
            <Grid container spacing={2} alignItems="flex-end">
              <Grid size={{ xs: 12, sm: 6, md: 2 }}>
                <TextField
                  label="标的 Symbol"
                  size="small"
                  fullWidth
                  value={wfSymbol}
                  onChange={(e) => setWfSymbol(e.target.value.toUpperCase())}
                  slotProps={{
                    input: { sx: { ...monoSx, fontWeight: 700 } },
                  }}
                />
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                <TextField
                  label="训练天数 Train Days"
                  type="number"
                  size="small"
                  fullWidth
                  value={wfTrainDays}
                  onChange={(e) => setWfTrainDays(Number(e.target.value))}
                  slotProps={{ htmlInput: { min: 60, max: 1260, step: 21 } }}
                />
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                <TextField
                  label="测试天数 Test Days"
                  type="number"
                  size="small"
                  fullWidth
                  value={wfTestDays}
                  onChange={(e) => setWfTestDays(Number(e.target.value))}
                  slotProps={{ htmlInput: { min: 10, max: 252, step: 10 } }}
                />
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                <TextField
                  label="步进天数 Step Days"
                  type="number"
                  size="small"
                  fullWidth
                  value={wfStepDays}
                  onChange={(e) => setWfStepDays(Number(e.target.value))}
                  slotProps={{ htmlInput: { min: 5, max: 126, step: 5 } }}
                />
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                <TextField
                  label="持有周期 Horizon (d)"
                  type="number"
                  size="small"
                  fullWidth
                  value={wfHorizon}
                  onChange={(e) => setWfHorizon(Number(e.target.value))}
                  slotProps={{ htmlInput: { min: 1, max: 60 } }}
                />
              </Grid>
            </Grid>

            <Box sx={{ mt: 3 }}>
              <Button
                variant="contained"
                size="large"
                onClick={handleWfRun}
                disabled={wfRunning || !wfSymbol.trim()}
                startIcon={
                  wfRunning ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : null
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
                {wfRunning ? "运行中..." : "运行滚动验证 Run Walk-Forward"}
              </Button>
            </Box>
          </CardContent>
        </Card>

        {wfRunning && (
          <>
            <Grid container spacing={2} sx={{ mb: 3 }}>
              {["s1", "s2", "s3"].map((id) => (
                <Grid key={`wfskel-${id}`} size={{ xs: 12, sm: 4 }}>
                  <Skeleton variant="rounded" height={80} />
                </Grid>
              ))}
            </Grid>
            <Box>
              {SKELETON_ROW_IDS.map((id) => (
                <Skeleton
                  key={`wftblskel-${id}`}
                  variant="rectangular"
                  height={32}
                  sx={{ mb: 0.5, borderRadius: 0.5 }}
                />
              ))}
            </Box>
          </>
        )}

        {wfResult && !wfResult.error && (
          <>
            <Grid container spacing={2} sx={{ mb: 3 }}>
              <Grid size={{ xs: 12, sm: 4 }}>
                <Card>
                  <CardContent sx={{ pb: "16px !important" }}>
                    <Typography
                      variant="caption"
                      sx={{
                        color: "text.secondary",
                        display: "block",
                        mb: 0.5,
                      }}
                    >
                      Avg OOS Hit Rate
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}
                    >
                      样本外平均命中率
                    </Typography>
                    <Typography
                      variant="h6"
                      sx={{
                        ...monoSx,
                        fontWeight: 700,
                        fontSize: "1.25rem",
                        color:
                          wfResult.avg_oos_hit_rate > 0.55
                            ? "#36bb80"
                            : wfResult.avg_oos_hit_rate < 0.45
                              ? "#ff7134"
                              : "text.primary",
                      }}
                    >
                      {pct(wfResult.avg_oos_hit_rate)}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <Card>
                  <CardContent sx={{ pb: "16px !important" }}>
                    <Typography
                      variant="caption"
                      sx={{
                        color: "text.secondary",
                        display: "block",
                        mb: 0.5,
                      }}
                    >
                      Avg OOS Return
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}
                    >
                      样本外平均收益
                    </Typography>
                    <Typography
                      variant="h6"
                      sx={{
                        ...monoSx,
                        fontWeight: 700,
                        fontSize: "1.25rem",
                        color:
                          wfResult.avg_oos_return >= 0 ? "#36bb80" : "#ff7134",
                      }}
                    >
                      {pct(wfResult.avg_oos_return)}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <Card>
                  <CardContent sx={{ pb: "16px !important" }}>
                    <Typography
                      variant="caption"
                      sx={{
                        color: "text.secondary",
                        display: "block",
                        mb: 0.5,
                      }}
                    >
                      Stability Ratio
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{ fontWeight: 700, mb: 0.5, fontSize: "0.8rem" }}
                    >
                      稳定性比率
                    </Typography>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                      <Typography
                        variant="h6"
                        sx={{
                          ...monoSx,
                          fontWeight: 700,
                          fontSize: "1.25rem",
                          color: stabilityColor,
                        }}
                      >
                        {fmt(wfResult.stability_ratio)}
                      </Typography>
                      <Chip
                        label={
                          wfResult.stability_ratio >= 0.8
                            ? "稳定"
                            : wfResult.stability_ratio >= 0.6
                              ? "中等"
                              : "不稳定"
                        }
                        size="small"
                        sx={{
                          bgcolor:
                            wfResult.stability_ratio >= 0.8
                              ? "rgba(54,187,128,0.15)"
                              : wfResult.stability_ratio >= 0.6
                                ? "rgba(253,188,42,0.15)"
                                : "rgba(255,113,52,0.15)",
                          color: stabilityColor,
                          border: `1px solid ${stabilityColor}40`,
                          fontWeight: 700,
                          fontSize: "0.7rem",
                        }}
                      />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>

            {wfResult.windows.length > 0 && (
              <Card>
                <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
                  <Box sx={{ p: 2, pb: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 700 }}>
                      滚动窗口明细 · Window Details
                    </Typography>
                  </Box>
                  <Box sx={{ overflowX: "auto" }}>
                    <Table size="small" sx={{ minWidth: 720 }}>
                      <TableHead>
                        <TableRow>
                          <TableCell sx={headCellSx}>#</TableCell>
                          <TableCell sx={headCellSx}>Train Period</TableCell>
                          <TableCell sx={headCellSx}>Test Period</TableCell>
                          <TableCell align="right" sx={headCellSx}>
                            IS Hit Rate
                          </TableCell>
                          <TableCell align="right" sx={headCellSx}>
                            OOS Hit Rate
                          </TableCell>
                          <TableCell align="right" sx={headCellSx}>
                            OOS Return
                          </TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {wfResult.windows.map((w, idx) => {
                          const oosColor =
                            w.out_of_sample_hit_rate > 0.55
                              ? "#36bb80"
                              : w.out_of_sample_hit_rate < 0.45
                                ? "#ff7134"
                                : "inherit";
                          return (
                            <TableRow
                              key={`wf-window-${w.train_start}-${w.test_start}`}
                              sx={{ "&:hover": { bgcolor: "action.hover" } }}
                            >
                              <TableCell
                                sx={{ ...cellSx, color: "text.secondary" }}
                              >
                                {idx + 1}
                              </TableCell>
                              <TableCell sx={cellSx}>
                                {w.train_start} → {w.train_end}
                              </TableCell>
                              <TableCell sx={cellSx}>
                                {w.test_start} → {w.test_end}
                              </TableCell>
                              <TableCell
                                align="right"
                                sx={{
                                  ...cellSx,
                                  color:
                                    w.in_sample_hit_rate > 0.55
                                      ? "#36bb80"
                                      : w.in_sample_hit_rate < 0.45
                                        ? "#ff7134"
                                        : "inherit",
                                }}
                              >
                                {pct(w.in_sample_hit_rate)}
                              </TableCell>
                              <TableCell
                                align="right"
                                sx={{
                                  ...cellSx,
                                  color: oosColor,
                                  fontWeight: 600,
                                }}
                              >
                                {pct(w.out_of_sample_hit_rate)}
                              </TableCell>
                              <TableCell
                                align="right"
                                sx={{
                                  ...cellSx,
                                  color:
                                    w.out_of_sample_return >= 0
                                      ? "#36bb80"
                                      : "#ff7134",
                                }}
                              >
                                {pct(w.out_of_sample_return)}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </Box>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </Box>
    </Box>
  );
}
