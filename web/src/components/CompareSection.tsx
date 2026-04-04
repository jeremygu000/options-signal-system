"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import Skeleton from "@mui/material/Skeleton";
import Alert from "@mui/material/Alert";
import Chip from "@mui/material/Chip";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import SectionHeader from "@/components/SectionHeader";
import {
  fetchCompare,
  fetchSymbols,
  fetchActiveWatchlistSymbols,
} from "@/lib/api";
import type { CompareResponse, SymbolInfo } from "@/lib/types";
import { useThemeMode } from "./ThemeProvider";

const FALLBACK_TICKERS = ["QQQ", "USO", "XOM", "XLE", "CRM"];
const PALETTE = [
  "#3b89ff",
  "#36bb80",
  "#ff7134",
  "#fdbc2a",
  "#a78bfa",
  "#f472b6",
  "#38bdf8",
  "#fb923c",
  "#34d399",
  "#e879f9",
];

function CompareChart({
  data,
  tickers,
}: {
  data: CompareResponse;
  tickers: string[];
}) {
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
        const idx = tickers.indexOf(ticker);
        const color = PALETTE[idx >= 0 ? idx % PALETTE.length : 0];
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
  }, [data, mode, tickers]);

  return <Box ref={containerRef} sx={{ width: "100%", minHeight: 360 }} />;
}

export default function CompareSection() {
  const [_allSymbols, setAllSymbols] = useState<SymbolInfo[]>([]);
  const [selectedTickers, setSelectedTickers] =
    useState<string[]>(FALLBACK_TICKERS);
  const [data, setData] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addInput, setAddInput] = useState("");

  useEffect(() => {
    fetchSymbols()
      .then(setAllSymbols)
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchActiveWatchlistSymbols()
      .then((symbols) => {
        if (symbols.length > 0) {
          setSelectedTickers(symbols.slice(0, 10));
        }
      })
      .catch(() => {});
  }, []);

  const loadCompare = useCallback((tickers: string[]) => {
    if (tickers.length === 0) return;
    setLoading(true);
    setError(null);
    fetchCompare(tickers.join(","), 90)
      .then(setData)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load"),
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadCompare(selectedTickers);
  }, [selectedTickers, loadCompare]);

  const handleAdd = () => {
    const sym = addInput.trim().toUpperCase();
    if (sym && !selectedTickers.includes(sym) && selectedTickers.length < 10) {
      setSelectedTickers((prev) => [...prev, sym]);
      setAddInput("");
    }
  };

  const handleRemove = (ticker: string) => {
    setSelectedTickers((prev) => prev.filter((t) => t !== ticker));
  };

  return (
    <Box component="section" id="compare" sx={{ mb: 6 }}>
      <SectionHeader
        number="05"
        title="价格对比"
        subtitle="Price Comparison (Normalized)"
      />

      <Box
        sx={{
          mb: 2,
          display: "flex",
          gap: 1,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        {selectedTickers.map((ticker, idx) => (
          <Chip
            key={ticker}
            label={ticker}
            onDelete={() => handleRemove(ticker)}
            sx={{
              fontFamily: "var(--font-geist-mono)",
              fontWeight: 600,
              borderLeft: `3px solid ${PALETTE[idx % PALETTE.length]}`,
            }}
          />
        ))}
        {selectedTickers.length < 10 && (
          <Box sx={{ display: "flex", gap: 0.5, alignItems: "center" }}>
            <TextField
              size="small"
              value={addInput}
              onChange={(e) => setAddInput(e.target.value.toUpperCase())}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleAdd();
              }}
              placeholder="Add ticker"
              slotProps={{
                htmlInput: {
                  style: {
                    fontFamily: "var(--font-geist-mono)",
                    fontSize: "0.8rem",
                    padding: "4px 8px",
                  },
                },
              }}
              sx={{ width: 100 }}
            />
            <Button
              size="small"
              variant="outlined"
              onClick={handleAdd}
              disabled={!addInput.trim()}
              sx={{ minWidth: 0, px: 1.5, fontSize: "0.75rem" }}
            >
              +
            </Button>
          </Box>
        )}
        <Typography
          variant="caption"
          sx={{
            color: "text.disabled",
            fontFamily: "var(--font-geist-mono)",
            fontSize: "0.6rem",
          }}
        >
          {selectedTickers.length}/10
        </Typography>
      </Box>

      {loading && <Skeleton variant="rounded" height={400} />}
      {error && <Alert severity="error">{error}</Alert>}

      {data && !loading && (
        <Card>
          <CardContent>
            <CompareChart data={data} tickers={selectedTickers} />
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
