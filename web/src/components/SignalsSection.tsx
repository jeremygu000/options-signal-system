"use client";

import { useState, useEffect } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import Skeleton from "@mui/material/Skeleton";
import Alert from "@mui/material/Alert";
import Grid from "@mui/material/Grid";
import Divider from "@mui/material/Divider";
import SectionHeader from "@/components/SectionHeader";
import { fetchScan } from "@/lib/api";
import type { Signal, FullScanResponse } from "@/lib/types";

function signalLevelColor(level: string): "error" | "warning" | "default" {
  if (level === "强信号") return "error";
  if (level === "观察信号") return "warning";
  return "default";
}

function biasColor(bias: string): string {
  return bias === "逢高做空" ? "#ff7134" : "#36bb80";
}

function SignalCard({ signal }: { signal: Signal }) {
  const levelColor = signalLevelColor(signal.level);

  return (
    <Card
      sx={{
        height: "100%",
        borderLeft: `3px solid`,
        borderLeftColor:
          signal.level === "强信号"
            ? "error.main"
            : signal.level === "观察信号"
              ? "warning.main"
              : "divider",
      }}
    >
      <CardContent>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            mb: 1.5,
          }}
        >
          <Box>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 700,
                fontFamily: "var(--font-geist-mono)",
                fontSize: "1rem",
              }}
            >
              {signal.symbol}
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: "text.secondary",
                fontFamily: "var(--font-geist-mono)",
                fontSize: "0.65rem",
              }}
            >
              {new Date(signal.timestamp).toLocaleDateString()}
            </Typography>
          </Box>
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-end",
              gap: 0.5,
            }}
          >
            <Chip
              label={signal.level}
              color={levelColor}
              size="small"
              sx={{ fontWeight: 700 }}
            />
            <Chip
              label={signal.bias}
              size="small"
              sx={{
                bgcolor: biasColor(signal.bias),
                color: "#fff",
                fontWeight: 600,
                fontSize: "0.7rem",
              }}
            />
          </Box>
        </Box>

        <Grid container spacing={1.5} sx={{ mb: 1.5 }}>
          <Grid size={{ xs: 6 }}>
            <Typography
              variant="caption"
              sx={{ color: "text.secondary", display: "block" }}
            >
              当前价格
            </Typography>
            <Typography
              sx={{
                fontWeight: 600,
                fontFamily: "var(--font-geist-mono)",
                fontSize: "0.875rem",
              }}
            >
              ${signal.price.toFixed(2)}
            </Typography>
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography
              variant="caption"
              sx={{ color: "text.secondary", display: "block" }}
            >
              触发价
            </Typography>
            <Typography
              sx={{
                fontWeight: 600,
                fontFamily: "var(--font-geist-mono)",
                fontSize: "0.875rem",
                color: "primary.main",
              }}
            >
              ${signal.trigger_price.toFixed(2)}
            </Typography>
          </Grid>
          <Grid size={{ xs: 6 }}>
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
                fontSize: "0.875rem",
              }}
            >
              {signal.score}
            </Typography>
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography
              variant="caption"
              sx={{ color: "text.secondary", display: "block" }}
            >
              结构
            </Typography>
            <Typography sx={{ fontWeight: 500, fontSize: "0.8rem" }}>
              {signal.option_structure || "—"}
            </Typography>
          </Grid>
        </Grid>

        {signal.option_hint && (
          <Box sx={{ mb: 1.5, p: 1, borderRadius: 1, bgcolor: "action.hover" }}>
            <Typography
              variant="caption"
              sx={{ color: "text.secondary", display: "block", mb: 0.25 }}
            >
              期权建议
            </Typography>
            <Typography variant="body2" sx={{ fontSize: "0.8rem" }}>
              {signal.option_hint}
            </Typography>
          </Box>
        )}

        <Divider sx={{ mb: 1 }} />
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
          逻辑依据
        </Typography>
        <Box component="ul" sx={{ m: 0, pl: 2 }}>
          {signal.rationale.map((r) => (
            <Typography
              key={r}
              component="li"
              variant="body2"
              sx={{ fontSize: "0.775rem", mb: 0.25, color: "text.secondary" }}
            >
              {r}
            </Typography>
          ))}
        </Box>
      </CardContent>
    </Card>
  );
}

export default function SignalsSection() {
  const [data, setData] = useState<FullScanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchScan()
      .then(setData)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load"),
      )
      .finally(() => setLoading(false));
  }, []);

  const signals = data?.signals ?? [];
  const strongSignals = signals.filter((s) => s.level === "强信号");
  const watchSignals = signals.filter((s) => s.level === "观察信号");
  const noSignals = signals.filter((s) => s.level === "无信号");

  return (
    <Box component="section" id="signals" sx={{ mb: 6 }}>
      <SectionHeader number="02" title="交易信号" subtitle="Signal Dashboard" />

      {loading && (
        <Grid container spacing={2}>
          {[0, 1, 2, 3].map((i) => (
            <Grid key={i} size={{ xs: 12, sm: 6, lg: 4 }}>
              <Skeleton variant="rounded" height={280} />
            </Grid>
          ))}
        </Grid>
      )}

      {error && <Alert severity="error">{error}</Alert>}

      {!loading && !error && signals.length === 0 && (
        <Alert severity="info">暂无交易信号数据</Alert>
      )}

      {signals.length > 0 && (
        <>
          {strongSignals.length > 0 && (
            <Box sx={{ mb: 3 }}>
              <Typography
                variant="body2"
                sx={{ mb: 1.5, fontWeight: 600, color: "error.main" }}
              >
                强信号 ({strongSignals.length})
              </Typography>
              <Grid container spacing={2}>
                {strongSignals.map((s) => (
                  <Grid key={s.symbol} size={{ xs: 12, sm: 6, lg: 4 }}>
                    <SignalCard signal={s} />
                  </Grid>
                ))}
              </Grid>
            </Box>
          )}

          {watchSignals.length > 0 && (
            <Box sx={{ mb: 3 }}>
              <Typography
                variant="body2"
                sx={{ mb: 1.5, fontWeight: 600, color: "warning.main" }}
              >
                观察信号 ({watchSignals.length})
              </Typography>
              <Grid container spacing={2}>
                {watchSignals.map((s) => (
                  <Grid key={s.symbol} size={{ xs: 12, sm: 6, lg: 4 }}>
                    <SignalCard signal={s} />
                  </Grid>
                ))}
              </Grid>
            </Box>
          )}

          {noSignals.length > 0 && (
            <Box>
              <Typography
                variant="body2"
                sx={{ mb: 1.5, fontWeight: 600, color: "text.secondary" }}
              >
                无信号 ({noSignals.length})
              </Typography>
              <Grid container spacing={2}>
                {noSignals.map((s) => (
                  <Grid key={s.symbol} size={{ xs: 12, sm: 6, lg: 4 }}>
                    <SignalCard signal={s} />
                  </Grid>
                ))}
              </Grid>
            </Box>
          )}
        </>
      )}
    </Box>
  );
}
