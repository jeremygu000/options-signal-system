"use client";

import { useState, useEffect, useCallback } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import Skeleton from "@mui/material/Skeleton";
import Alert from "@mui/material/Alert";
import Grid from "@mui/material/Grid";
import SectionHeader from "@/components/SectionHeader";
import { fetchRegime } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { MarketRegimeResult } from "@/lib/types";

function regimeColor(regime: string): "success" | "warning" | "error" {
  if (regime === "risk_on") return "success";
  if (regime === "neutral") return "warning";
  return "error";
}

function regimeLabel(regime: string): string {
  if (regime === "risk_on") return "RISK ON 风险偏好";
  if (regime === "neutral") return "NEUTRAL 中性";
  return "RISK OFF 规避风险";
}

export default function RegimeSection() {
  const [data, setData] = useState<MarketRegimeResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    fetchRegime()
      .then((res) => {
        setData(res);
        setError(null);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load"),
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const { channelData } = useWebSocket(["regime"]);

  useEffect(() => {
    const pushed = channelData.regime as MarketRegimeResult | null;
    if (pushed) {
      setData(pushed);
      setError(null);
      setLoading(false);
    }
  }, [channelData.regime]);

  return (
    <Box component="section" id="regime" sx={{ mb: 6 }}>
      <SectionHeader number="01" title="市场环境" subtitle="Market Regime" />

      {loading && (
        <Grid container spacing={2}>
          {[0, 1, 2].map((i) => (
            <Grid key={i} size={{ xs: 12, md: 4 }}>
              <Skeleton variant="rounded" height={140} />
            </Grid>
          ))}
        </Grid>
      )}

      {error && <Alert severity="error">{error}</Alert>}

      {data && (
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 4 }}>
            <Card sx={{ height: "100%" }}>
              <CardContent>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                  }}
                >
                  市场状态
                </Typography>
                <Box sx={{ mt: 1.5 }}>
                  <Chip
                    label={regimeLabel(data.regime)}
                    color={regimeColor(data.regime)}
                    sx={{ fontWeight: 700, fontSize: "0.8rem", height: 32 }}
                  />
                </Box>
                <Typography
                  variant="caption"
                  sx={{
                    display: "block",
                    mt: 1.5,
                    color: "text.secondary",
                    fontFamily: "var(--font-geist-mono)",
                    fontSize: "0.65rem",
                  }}
                >
                  {new Date(data.timestamp).toLocaleString()}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, md: 4 }}>
            <Card sx={{ height: "100%" }}>
              <CardContent>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                  }}
                >
                  QQQ 价格
                </Typography>
                <Typography
                  variant="h4"
                  sx={{
                    mt: 1,
                    fontWeight: 700,
                    fontFamily: "var(--font-geist-mono)",
                  }}
                >
                  ${data.qqq_price.toFixed(2)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, md: 4 }}>
            <Card sx={{ height: "100%" }}>
              <CardContent>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                  }}
                >
                  VIX 恐慌指数
                </Typography>
                <Typography
                  variant="h4"
                  sx={{
                    mt: 1,
                    fontWeight: 700,
                    fontFamily: "var(--font-geist-mono)",
                    color:
                      data.vix_price > 25
                        ? "error.main"
                        : data.vix_price > 18
                          ? "warning.main"
                          : "success.main",
                  }}
                >
                  {data.vix_price.toFixed(2)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12 }}>
            <Card>
              <CardContent>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    display: "block",
                    mb: 1.5,
                  }}
                >
                  判断依据
                </Typography>
                <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                  {data.reasons.map((reason) => (
                    <Typography
                      key={reason}
                      component="li"
                      variant="body2"
                      sx={{ mb: 0.5, fontSize: "0.875rem" }}
                    >
                      {reason}
                    </Typography>
                  ))}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  );
}
