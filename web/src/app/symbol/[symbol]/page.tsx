"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import Grid from "@mui/material/Grid";
import Skeleton from "@mui/material/Skeleton";
import Alert from "@mui/material/Alert";
import Divider from "@mui/material/Divider";
import LinearProgress from "@mui/material/LinearProgress";
import Button from "@mui/material/Button";
import { useThemeMode } from "@/components/ThemeProvider";
import { fetchScan, fetchIndicators, fetchOHLCV } from "@/lib/api";
import type { Signal, IndicatorSnapshot, OHLCVBar } from "@/lib/types";

const REFRESH_INTERVAL_MS = 30_000;

function signalLevelColor(level: string): "error" | "warning" | "default" {
  if (level === "强信号") return "error";
  if (level === "观察信号") return "warning";
  return "default";
}

function biasColor(bias: string): string {
  return bias === "逢高做空" ? "#ff7134" : "#36bb80";
}

function borderLeftColor(level: string): string {
  if (level === "强信号") return "error.main";
  if (level === "观察信号") return "warning.main";
  return "divider";
}

function rangeProgressColor(val: number): "error" | "success" | "warning" {
  if (val > 0.7) return "error";
  if (val < 0.3) return "success";
  return "warning";
}

function IndicatorRow({
  label,
  sub,
  value,
  mono = true,
}: {
  label: string;
  sub?: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <Grid size={{ xs: 6, sm: 4, md: 3 }}>
      <Box sx={{ mb: 1.5 }}>
        <Typography
          variant="caption"
          sx={{ color: "text.secondary", display: "block", lineHeight: 1.2 }}
        >
          {label}
        </Typography>
        {sub && (
          <Typography
            variant="caption"
            sx={{
              color: "text.disabled",
              fontSize: "0.6rem",
              display: "block",
              lineHeight: 1.2,
              mb: 0.25,
            }}
          >
            {sub}
          </Typography>
        )}
        {mono ? (
          <Typography
            sx={{
              fontWeight: 600,
              fontFamily: "var(--font-geist-mono)",
              fontSize: "0.875rem",
            }}
          >
            {value}
          </Typography>
        ) : (
          <>{value}</>
        )}
      </Box>
    </Grid>
  );
}

function CandlestickChart({
  symbol,
  data,
}: {
  symbol: string;
  data: OHLCVBar[];
}) {
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
        height: 380,
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
          timeVisible: true,
        },
      });

      const candleSeries = chart.addSeries(lc.CandlestickSeries, {
        upColor: "#36bb80",
        downColor: "#ff7134",
        borderUpColor: "#36bb80",
        borderDownColor: "#ff7134",
        wickUpColor: "#36bb80",
        wickDownColor: "#ff7134",
      });

      const volSeries = chart.addSeries(lc.HistogramSeries, {
        color: "#3b89ff",
        priceFormat: { type: "volume" as const },
        priceScaleId: "volume",
      });

      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });

      const candleData = data.map((bar) => ({
        time: bar.date as import("lightweight-charts").Time,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      }));

      const volData = data.map((bar) => ({
        time: bar.date as import("lightweight-charts").Time,
        value: bar.volume,
        color:
          bar.close >= bar.open
            ? "rgba(54,187,128,0.4)"
            : "rgba(255,113,52,0.4)",
      }));

      candleSeries.setData(candleData);
      volSeries.setData(volData);
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
  }, [data, symbol]);

  return <Box ref={containerRef} sx={{ width: "100%", minHeight: 380 }} />;
}

export default function SymbolDetailPage() {
  const params = useParams<{ symbol: string }>();
  const symbol = (params.symbol ?? "").toUpperCase();

  const [signal, setSignal] = useState<Signal | null>(null);
  const [signalNotFound, setSignalNotFound] = useState(false);
  const [indicators, setIndicators] = useState<IndicatorSnapshot | null>(null);
  const [chartData, setChartData] = useState<OHLCVBar[]>([]);

  const [loadingSignal, setLoadingSignal] = useState(true);
  const [loadingIndicators, setLoadingIndicators] = useState(true);
  const [loadingChart, setLoadingChart] = useState(true);

  const [errorSignal, setErrorSignal] = useState<string | null>(null);
  const [errorIndicators, setErrorIndicators] = useState<string | null>(null);
  const [errorChart, setErrorChart] = useState<string | null>(null);

  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const loadSignal = useCallback(
    (isInitial: boolean) => {
      if (isInitial) setLoadingSignal(true);
      fetchScan()
        .then((res) => {
          const found = res.signals.find((s) => s.symbol === symbol) ?? null;
          setSignal(found);
          setSignalNotFound(found === null);
          setLastUpdated(new Date());
          setErrorSignal(null);
        })
        .catch((e: unknown) =>
          setErrorSignal(
            e instanceof Error ? e.message : "Failed to load signal",
          ),
        )
        .finally(() => {
          if (isInitial) setLoadingSignal(false);
        });
    },
    [symbol],
  );

  const loadIndicators = useCallback(
    (isInitial: boolean) => {
      if (!symbol) return;
      if (isInitial) setLoadingIndicators(true);
      fetchIndicators(symbol)
        .then((res) => {
          setIndicators(res);
          setErrorIndicators(null);
        })
        .catch((e: unknown) =>
          setErrorIndicators(
            e instanceof Error ? e.message : "Failed to load indicators",
          ),
        )
        .finally(() => {
          if (isInitial) setLoadingIndicators(false);
        });
    },
    [symbol],
  );

  const loadChart = useCallback(
    (isInitial: boolean) => {
      if (!symbol) return;
      if (isInitial) setLoadingChart(true);
      fetchOHLCV(symbol, 90)
        .then((res) => {
          setChartData(res.data);
          setErrorChart(null);
        })
        .catch((e: unknown) =>
          setErrorChart(
            e instanceof Error ? e.message : "Failed to load chart data",
          ),
        )
        .finally(() => {
          if (isInitial) setLoadingChart(false);
        });
    },
    [symbol],
  );

  useEffect(() => {
    loadSignal(true);
    loadIndicators(true);
    loadChart(true);
  }, [loadSignal, loadIndicators, loadChart]);

  useEffect(() => {
    const interval = setInterval(() => {
      loadSignal(false);
      loadIndicators(false);
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [loadSignal, loadIndicators]);

  const rp = indicators?.range_position ?? 0;

  return (
    <Box sx={{ px: { xs: 2, sm: 4 }, py: 4, maxWidth: 1200, mx: "auto" }}>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 2,
          mb: 4,
        }}
      >
        <Button
          component={Link}
          href="/"
          variant="outlined"
          size="small"
          sx={{
            borderRadius: 2,
            fontFamily: "var(--font-geist-mono)",
            fontSize: "0.75rem",
            px: 1.5,
            py: 0.5,
            minWidth: 0,
          }}
        >
          ← Dashboard
        </Button>
        <Box sx={{ flex: 1 }}>
          <Typography
            variant="h4"
            sx={{
              fontWeight: 800,
              fontFamily: "var(--font-geist-mono)",
              letterSpacing: "-0.03em",
              lineHeight: 1,
            }}
          >
            {symbol || <Skeleton width={120} />}
          </Typography>
          {lastUpdated && (
            <Typography
              variant="caption"
              sx={{
                fontFamily: "var(--font-geist-mono)",
                fontSize: "0.65rem",
                color: "text.disabled",
              }}
            >
              Auto-refresh 30s &middot; {lastUpdated.toLocaleTimeString()}
            </Typography>
          )}
        </Box>
        {signal && (
          <Chip
            label={signal.level}
            color={signalLevelColor(signal.level)}
            sx={{ fontWeight: 700, fontSize: "0.8rem" }}
          />
        )}
      </Box>

      {signalNotFound && !loadingSignal && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          未找到 {symbol} 的信号数据 — Symbol not found in current scan results.
        </Alert>
      )}

      <Box sx={{ mb: 3 }}>
        {loadingSignal && <Skeleton variant="rounded" height={280} />}
        {errorSignal && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {errorSignal}
          </Alert>
        )}
        {!loadingSignal && signal && (
          <Card
            sx={{
              borderLeft: "4px solid",
              borderLeftColor: borderLeftColor(signal.level),
            }}
          >
            <CardContent>
              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  mb: 2,
                }}
              >
                <Box>
                  <Typography
                    variant="h5"
                    sx={{
                      fontWeight: 800,
                      fontFamily: "var(--font-geist-mono)",
                      letterSpacing: "-0.02em",
                    }}
                  >
                    信号摘要
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary" }}
                  >
                    Signal Summary &middot;{" "}
                    {new Date(signal.timestamp).toLocaleString()}
                  </Typography>
                </Box>
                <Box
                  sx={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-end",
                    gap: 0.75,
                  }}
                >
                  <Chip
                    label={signal.level}
                    color={signalLevelColor(signal.level)}
                    sx={{ fontWeight: 700 }}
                  />
                  <Chip
                    label={signal.bias}
                    size="small"
                    sx={{
                      bgcolor: biasColor(signal.bias),
                      color: "#fff",
                      fontWeight: 600,
                    }}
                  />
                </Box>
              </Box>

              <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid size={{ xs: 6, sm: 3 }}>
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary", display: "block" }}
                  >
                    当前价格
                  </Typography>
                  <Typography
                    sx={{
                      fontWeight: 700,
                      fontFamily: "var(--font-geist-mono)",
                      fontSize: "1.25rem",
                      lineHeight: 1.2,
                    }}
                  >
                    ${signal.price.toFixed(2)}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 6, sm: 3 }}>
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary", display: "block" }}
                  >
                    触发价
                  </Typography>
                  <Typography
                    sx={{
                      fontWeight: 700,
                      fontFamily: "var(--font-geist-mono)",
                      fontSize: "1.25rem",
                      color: "primary.main",
                      lineHeight: 1.2,
                    }}
                  >
                    ${signal.trigger_price.toFixed(2)}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 6, sm: 3 }}>
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary", display: "block" }}
                  >
                    信号分数
                  </Typography>
                  <Typography
                    sx={{
                      fontWeight: 700,
                      fontFamily: "var(--font-geist-mono)",
                      fontSize: "1.25rem",
                      lineHeight: 1.2,
                    }}
                  >
                    {signal.score}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 6, sm: 3 }}>
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary", display: "block" }}
                  >
                    结构
                  </Typography>
                  <Typography
                    sx={{
                      fontWeight: 600,
                      fontSize: "0.875rem",
                      lineHeight: 1.3,
                    }}
                  >
                    {signal.option_structure || "—"}
                  </Typography>
                </Grid>
              </Grid>

              {signal.option_hint && (
                <Box
                  sx={{
                    mb: 2,
                    p: 1.5,
                    borderRadius: 2,
                    bgcolor: "action.hover",
                    border: "1px solid",
                    borderColor: "divider",
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{
                      color: "text.secondary",
                      display: "block",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                      mb: 0.5,
                    }}
                  >
                    期权建议 · Option Hint
                  </Typography>
                  <Typography variant="body2">{signal.option_hint}</Typography>
                </Box>
              )}

              <Divider sx={{ mb: 1.5 }} />

              <Typography
                variant="caption"
                sx={{
                  color: "text.secondary",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  display: "block",
                  mb: 0.75,
                }}
              >
                逻辑依据 · Rationale
              </Typography>
              <Box component="ul" sx={{ m: 0, pl: 2 }}>
                {signal.rationale.map((r) => (
                  <Typography
                    key={r}
                    component="li"
                    variant="body2"
                    sx={{
                      fontSize: "0.8rem",
                      mb: 0.4,
                      color: "text.secondary",
                    }}
                  >
                    {r}
                  </Typography>
                ))}
              </Box>
            </CardContent>
          </Card>
        )}
      </Box>

      <Box sx={{ mb: 3 }}>
        {loadingIndicators && <Skeleton variant="rounded" height={200} />}
        {errorIndicators && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {errorIndicators}
          </Alert>
        )}
        {!loadingIndicators && indicators && (
          <Card>
            <CardContent>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 700,
                  mb: 2,
                }}
              >
                技术指标
                <Typography
                  component="span"
                  variant="caption"
                  sx={{ ml: 1, color: "text.secondary" }}
                >
                  Technical Indicators
                </Typography>
              </Typography>

              <Grid container spacing={1}>
                <IndicatorRow
                  label="SMA5"
                  sub="5-day SMA"
                  value={
                    indicators.sma5 !== null
                      ? `$${indicators.sma5.toFixed(2)}`
                      : "—"
                  }
                />
                <IndicatorRow
                  label="SMA10"
                  sub="10-day SMA"
                  value={
                    indicators.sma10 !== null
                      ? `$${indicators.sma10.toFixed(2)}`
                      : "—"
                  }
                />
                <IndicatorRow
                  label="ATR14"
                  sub="14-day ATR"
                  value={
                    indicators.atr14 !== null
                      ? `$${indicators.atr14.toFixed(2)}`
                      : "—"
                  }
                />
                <IndicatorRow
                  label="VWAP"
                  sub="Intraday VWAP"
                  value={
                    indicators.vwap !== null
                      ? `$${indicators.vwap.toFixed(2)}`
                      : "—"
                  }
                />
                <IndicatorRow
                  label="前高"
                  sub="prev_high"
                  value={
                    indicators.prev_high !== null
                      ? `$${indicators.prev_high.toFixed(2)}`
                      : "—"
                  }
                />
                <IndicatorRow
                  label="前低"
                  sub="prev_low"
                  value={
                    indicators.prev_low !== null
                      ? `$${indicators.prev_low.toFixed(2)}`
                      : "—"
                  }
                />
                <IndicatorRow
                  label="20日高"
                  sub="rolling_high_20"
                  value={
                    indicators.rolling_high_20 !== null
                      ? `$${indicators.rolling_high_20.toFixed(2)}`
                      : "—"
                  }
                />
                <IndicatorRow
                  label="20日低"
                  sub="rolling_low_20"
                  value={
                    indicators.rolling_low_20 !== null
                      ? `$${indicators.rolling_low_20.toFixed(2)}`
                      : "—"
                  }
                />
              </Grid>

              <Divider sx={{ my: 1.5 }} />

              <Box>
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "baseline",
                    mb: 0.75,
                  }}
                >
                  <Box>
                    <Typography
                      variant="caption"
                      sx={{ color: "text.secondary", fontWeight: 600 }}
                    >
                      区间位置
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{
                        ml: 1,
                        color: "text.disabled",
                        fontSize: "0.65rem",
                      }}
                    >
                      range_position
                    </Typography>
                  </Box>
                  <Typography
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontSize: "0.8rem",
                      fontWeight: 700,
                    }}
                  >
                    {indicators.range_position !== null
                      ? `${(indicators.range_position * 100).toFixed(0)}%`
                      : "—"}
                  </Typography>
                </Box>
                {indicators.range_position !== null && (
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(100, Math.max(0, rp * 100))}
                    color={rangeProgressColor(rp)}
                    sx={{ height: 10, borderRadius: 5 }}
                  />
                )}
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    mt: 0.5,
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{ color: "success.main", fontSize: "0.65rem" }}
                  >
                    低位 (支撑)
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{ color: "error.main", fontSize: "0.65rem" }}
                  >
                    高位 (压力)
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        )}
      </Box>

      <Box sx={{ mb: 3 }}>
        {loadingChart && <Skeleton variant="rounded" height={420} />}
        {errorChart && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {errorChart}
          </Alert>
        )}
        {!loadingChart && chartData.length > 0 && (
          <Card>
            <CardContent>
              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  mb: 1.5,
                }}
              >
                <Typography variant="h6" sx={{ fontWeight: 700 }}>
                  价格走势
                  <Typography
                    component="span"
                    variant="caption"
                    sx={{ ml: 1, color: "text.secondary" }}
                  >
                    Price Chart (90 days)
                  </Typography>
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    fontFamily: "var(--font-geist-mono)",
                    fontSize: "0.7rem",
                    color: "text.disabled",
                  }}
                >
                  {chartData.length} bars
                </Typography>
              </Box>
              <CandlestickChart symbol={symbol} data={chartData} />
            </CardContent>
          </Card>
        )}
        {!loadingChart && chartData.length === 0 && !errorChart && (
          <Alert severity="info">暂无图表数据</Alert>
        )}
      </Box>
    </Box>
  );
}
