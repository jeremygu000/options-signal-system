"use client";

import { useState, useEffect } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import Typography from "@mui/material/Typography";
import Skeleton from "@mui/material/Skeleton";
import Alert from "@mui/material/Alert";
import LinearProgress from "@mui/material/LinearProgress";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TableContainer from "@mui/material/TableContainer";
import SectionHeader from "@/components/SectionHeader";
import { fetchScan, fetchIndicators } from "@/lib/api";
import type { IndicatorSnapshot } from "@/lib/types";

export default function IndicatorsSection() {
  const [indicators, setIndicators] = useState<IndicatorSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const scan = await fetchScan();
        const symbols = scan.signals.map((s) => s.symbol);
        const results = await Promise.allSettled(
          symbols.map((sym) => fetchIndicators(sym)),
        );
        const data: IndicatorSnapshot[] = [];
        for (const r of results) {
          if (r.status === "fulfilled") data.push(r.value);
        }
        setIndicators(data);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load indicators");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <Box component="section" id="indicators" sx={{ mb: 6 }}>
      <SectionHeader
        number="03"
        title="技术指标"
        subtitle="Technical Indicators"
      />

      {loading && <Skeleton variant="rounded" height={240} />}
      {error && <Alert severity="error">{error}</Alert>}

      {!loading && !error && indicators.length === 0 && (
        <Alert severity="info">暂无指标数据</Alert>
      )}

      {indicators.length > 0 && (
        <Card>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>标的</TableCell>
                  <TableCell align="right">SMA5</TableCell>
                  <TableCell align="right">SMA10</TableCell>
                  <TableCell align="right">ATR14</TableCell>
                  <TableCell align="right">VWAP</TableCell>
                  <TableCell align="right">前高</TableCell>
                  <TableCell align="right">前低</TableCell>
                  <TableCell align="right">20d高</TableCell>
                  <TableCell align="right">20d低</TableCell>
                  <TableCell sx={{ minWidth: 160 }}>区间位置</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {indicators.map((row) => (
                  <TableRow key={row.symbol}>
                    <TableCell>
                      <Typography
                        sx={{
                          fontWeight: 700,
                          fontFamily: "var(--font-geist-mono)",
                          fontSize: "0.8125rem",
                        }}
                      >
                        {row.symbol}
                      </Typography>
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontFamily: "var(--font-geist-mono)" }}
                    >
                      {(row.sma5 ?? 0).toFixed(2)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontFamily: "var(--font-geist-mono)" }}
                    >
                      {(row.sma10 ?? 0).toFixed(2)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontFamily: "var(--font-geist-mono)" }}
                    >
                      {(row.atr14 ?? 0).toFixed(2)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontFamily: "var(--font-geist-mono)" }}
                    >
                      {(row.vwap ?? 0).toFixed(2)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontFamily: "var(--font-geist-mono)" }}
                    >
                      {(row.prev_high ?? 0).toFixed(2)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontFamily: "var(--font-geist-mono)" }}
                    >
                      {(row.prev_low ?? 0).toFixed(2)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontFamily: "var(--font-geist-mono)" }}
                    >
                      {(row.rolling_high_20 ?? 0).toFixed(2)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontFamily: "var(--font-geist-mono)" }}
                    >
                      {(row.rolling_low_20 ?? 0).toFixed(2)}
                    </TableCell>
                    <TableCell>
                      <Box
                        sx={{ display: "flex", alignItems: "center", gap: 1 }}
                      >
                        <LinearProgress
                          variant="determinate"
                          value={Math.min(
                            100,
                            Math.max(0, (row.range_position ?? 0) * 100),
                          )}
                          sx={{ flex: 1, height: 6, borderRadius: 3 }}
                          color={
                            (row.range_position ?? 0) > 0.7
                              ? "error"
                              : (row.range_position ?? 0) < 0.3
                                ? "success"
                                : "warning"
                          }
                        />
                        <Typography
                          sx={{
                            fontFamily: "var(--font-geist-mono)",
                            fontSize: "0.7rem",
                            minWidth: 36,
                            textAlign: "right",
                          }}
                        >
                          {((row.range_position ?? 0) * 100).toFixed(0)}%
                        </Typography>
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Card>
      )}
    </Box>
  );
}
