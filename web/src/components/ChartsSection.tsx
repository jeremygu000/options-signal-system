"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import Skeleton from "@mui/material/Skeleton";
import Alert from "@mui/material/Alert";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import ToggleButton from "@mui/material/ToggleButton";
import FormControlLabel from "@mui/material/FormControlLabel";
import Switch from "@mui/material/Switch";
import SectionHeader from "@/components/SectionHeader";
import { fetchScan, fetchOHLCV, fetchIndicators } from "@/lib/api";
import type { OHLCVBar, IndicatorSnapshot } from "@/lib/types";
import { useThemeMode } from "./ThemeProvider";

interface CandlestickChartProps {
  symbol: string;
  data: OHLCVBar[];
  indicators: IndicatorSnapshot | null;
  showOverlays: boolean;
}

function CandlestickChart({
  symbol,
  data,
  indicators,
  showOverlays,
}: CandlestickChartProps) {
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
        height: 360,
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

      if (showOverlays && indicators) {
        const lastDate = data[data.length - 1]?.date;
        if (lastDate) {
          const markers: Array<{
            label: string;
            value: number | null;
            color: string;
          }> = [
            { label: "SMA5", value: indicators.sma5, color: "#fdbc2a" },
            { label: "SMA10", value: indicators.sma10, color: "#a78bfa" },
            { label: "VWAP", value: indicators.vwap, color: "#3b89ff" },
          ];

          for (const m of markers) {
            if (m.value != null) {
              const line = candleSeries.createPriceLine({
                price: m.value,
                color: m.color,
                lineWidth: 1,
                lineStyle: lc.LineStyle.Dashed,
                axisLabelVisible: true,
                title: m.label,
              });
              void line;
            }
          }
        }
      }

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
  }, [data, symbol, showOverlays, indicators]);

  return (
    <Card>
      <CardContent>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            mb: 1.5,
          }}
        >
          <Typography
            variant="subtitle2"
            sx={{
              fontWeight: 700,
              fontFamily: "var(--font-geist-mono)",
            }}
          >
            {symbol}
          </Typography>
          {indicators && showOverlays && (
            <Box
              sx={{
                display: "flex",
                gap: 1.5,
                alignItems: "center",
              }}
            >
              {[
                { label: "SMA5", value: indicators.sma5, color: "#fdbc2a" },
                { label: "SMA10", value: indicators.sma10, color: "#a78bfa" },
                { label: "VWAP", value: indicators.vwap, color: "#3b89ff" },
              ].map(
                (item) =>
                  item.value != null && (
                    <Box
                      key={item.label}
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 0.5,
                      }}
                    >
                      <Box
                        sx={{
                          width: 12,
                          height: 2,
                          bgcolor: item.color,
                          borderRadius: "1px",
                        }}
                      />
                      <Typography
                        variant="caption"
                        sx={{
                          fontFamily: "var(--font-geist-mono)",
                          fontSize: "0.65rem",
                          color: "text.secondary",
                        }}
                      >
                        {item.label} {item.value.toFixed(2)}
                      </Typography>
                    </Box>
                  ),
              )}
            </Box>
          )}
        </Box>
        <Box ref={containerRef} sx={{ width: "100%", minHeight: 360 }} />
      </CardContent>
    </Card>
  );
}

export default function ChartsSection() {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [chartData, setChartData] = useState<OHLCVBar[]>([]);
  const [indicators, setIndicators] = useState<IndicatorSnapshot | null>(null);
  const [showOverlays, setShowOverlays] = useState(true);
  const [loadingSymbols, setLoadingSymbols] = useState(true);
  const [loadingChart, setLoadingChart] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchScan()
      .then((scan) => {
        const syms = scan.signals.map((s) => s.symbol);
        setSymbols(syms);
        if (syms.length > 0) setSelectedSymbol(syms[0]);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load"),
      )
      .finally(() => setLoadingSymbols(false));
  }, []);

  const loadChart = useCallback((sym: string) => {
    if (!sym) return;
    setLoadingChart(true);
    Promise.all([fetchOHLCV(sym, 90), fetchIndicators(sym)])
      .then(([ohlcv, ind]) => {
        setChartData(ohlcv.data);
        setIndicators(ind);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load chart"),
      )
      .finally(() => setLoadingChart(false));
  }, []);

  useEffect(() => {
    if (selectedSymbol) loadChart(selectedSymbol);
  }, [selectedSymbol, loadChart]);

  return (
    <Box component="section" id="charts" sx={{ mb: 6 }}>
      <SectionHeader
        number="04"
        title="价格走势"
        subtitle="Price Charts (90 days)"
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {loadingSymbols && (
        <Skeleton variant="rounded" height={48} sx={{ mb: 2 }} />
      )}

      {symbols.length > 0 && (
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            mb: 2,
            flexWrap: "wrap",
            gap: 1,
          }}
        >
          <ToggleButtonGroup
            value={selectedSymbol}
            exclusive
            onChange={(_, val) => {
              if (val) setSelectedSymbol(val);
            }}
            sx={{ flexWrap: "wrap", gap: 0.5 }}
          >
            {symbols.map((sym) => (
              <ToggleButton key={sym} value={sym}>
                {sym}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
          <FormControlLabel
            control={
              <Switch
                checked={showOverlays}
                onChange={(e) => setShowOverlays(e.target.checked)}
                size="small"
              />
            }
            label={
              <Typography
                variant="caption"
                sx={{ fontFamily: "var(--font-geist-mono)", fontSize: "0.7rem" }}
              >
                SMA / VWAP
              </Typography>
            }
          />
        </Box>
      )}

      {loadingChart && <Skeleton variant="rounded" height={400} />}

      {!loadingChart && chartData.length > 0 && selectedSymbol && (
        <CandlestickChart
          symbol={selectedSymbol}
          data={chartData}
          indicators={indicators}
          showOverlays={showOverlays}
        />
      )}

      {!loadingChart && !loadingSymbols && chartData.length === 0 && !error && (
        <Alert severity="info">暂无图表数据</Alert>
      )}
    </Box>
  );
}
