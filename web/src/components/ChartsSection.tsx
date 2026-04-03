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
import SectionHeader from "@/components/SectionHeader";
import { fetchScan, fetchOHLCV } from "@/lib/api";
import type { OHLCVBar } from "@/lib/types";
import { useThemeMode } from "./ThemeProvider";

interface CandlestickChartProps {
  symbol: string;
  data: OHLCVBar[];
}

function CandlestickChart({ symbol, data }: CandlestickChartProps) {
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
        height: 320,
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
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mode captured via closure; adding it causes infinite re-renders
  }, [data, symbol]);

  return (
    <Card>
      <CardContent>
        <Typography
          variant="subtitle2"
          sx={{
            fontWeight: 700,
            fontFamily: "var(--font-geist-mono)",
            mb: 1.5,
          }}
        >
          {symbol}
        </Typography>
        <Box ref={containerRef} sx={{ width: "100%", minHeight: 320 }} />
      </CardContent>
    </Card>
  );
}

export default function ChartsSection() {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [chartData, setChartData] = useState<OHLCVBar[]>([]);
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
    fetchOHLCV(sym, 90)
      .then(setChartData)
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
        <ToggleButtonGroup
          value={selectedSymbol}
          exclusive
          onChange={(_, val) => {
            if (val) setSelectedSymbol(val);
          }}
          sx={{ mb: 2, flexWrap: "wrap", gap: 0.5 }}
        >
          {symbols.map((sym) => (
            <ToggleButton key={sym} value={sym}>
              {sym}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      )}

      {loadingChart && <Skeleton variant="rounded" height={360} />}

      {!loadingChart && chartData.length > 0 && selectedSymbol && (
        <CandlestickChart symbol={selectedSymbol} data={chartData} />
      )}

      {!loadingChart && !loadingSymbols && chartData.length === 0 && !error && (
        <Alert severity="info">暂无图表数据</Alert>
      )}
    </Box>
  );
}
