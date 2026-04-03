"use client";

import { useState, useEffect, useRef } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import Skeleton from "@mui/material/Skeleton";
import Alert from "@mui/material/Alert";
import SectionHeader from "@/components/SectionHeader";
import { fetchCompare } from "@/lib/api";
import type { CompareResponse } from "@/lib/types";
import { useThemeMode } from "./ThemeProvider";

const COMPARE_TICKERS = "QQQ,USO,XOM,XLE,CRM";

const TICKER_COLORS: Record<string, string> = {
  QQQ: "#3b89ff",
  USO: "#36bb80",
  XOM: "#ff7134",
  XLE: "#fdbc2a",
  CRM: "#a78bfa",
};

function CompareChart({ data }: { data: CompareResponse }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { mode } = useThemeMode();

  useEffect(() => {
    if (!containerRef.current) return;

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
        rightPriceScale: {
          borderColor: gridColor,
          scaleMargins: { top: 0.05, bottom: 0.05 },
        },
        timeScale: {
          borderColor: gridColor,
          timeVisible: true,
        },
      });

      for (const [ticker, points] of Object.entries(data)) {
        if (!points || points.length === 0) continue;
        const color = TICKER_COLORS[ticker] ?? "#8899aa";
        const series = chart.addSeries(lc.LineSeries, {
          color,
          lineWidth: 2,
          title: ticker,
          priceFormat: {
            type: "price" as const,
            precision: 4,
            minMove: 0.0001,
          },
        });
        series.setData(
          points.map((p) => ({
            time: p.date as import("lightweight-charts").Time,
            value: p.close,
          })),
        );
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
  }, [data, mode]);

  return <Box ref={containerRef} sx={{ width: "100%", minHeight: 360 }} />;
}

export default function CompareSection() {
  const [data, setData] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCompare(COMPARE_TICKERS, 90)
      .then(setData)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load"),
      )
      .finally(() => setLoading(false));
  }, []);

  return (
    <Box component="section" id="compare" sx={{ mb: 6 }}>
      <SectionHeader
        number="05"
        title="价格对比"
        subtitle="Price Comparison (Normalized)"
      />

      {loading && <Skeleton variant="rounded" height={400} />}
      {error && <Alert severity="error">{error}</Alert>}

      {data && (
        <Card>
          <CardContent>
            <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap", mb: 2 }}>
              {COMPARE_TICKERS.split(",").map((ticker) => (
                <Box
                  key={ticker}
                  sx={{ display: "flex", alignItems: "center", gap: 0.5 }}
                >
                  <Box
                    sx={{
                      width: 12,
                      height: 3,
                      borderRadius: "2px",
                      bgcolor: TICKER_COLORS[ticker] ?? "#8899aa",
                    }}
                  />
                  <Typography
                    variant="caption"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 600,
                    }}
                  >
                    {ticker}
                  </Typography>
                </Box>
              ))}
            </Box>
            <CompareChart data={data} />
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
