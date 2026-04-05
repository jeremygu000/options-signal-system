"use client";

import { useState, useEffect, useCallback } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import Skeleton from "@mui/material/Skeleton";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Grid from "@mui/material/Grid";
import LinearProgress from "@mui/material/LinearProgress";
import Tooltip from "@mui/material/Tooltip";
import Divider from "@mui/material/Divider";
import SectionHeader from "@/components/SectionHeader";
import {
  fetchMLStatus,
  fetchMLRegime,
  fetchEnhancedSignals,
  triggerTraining,
} from "@/lib/api";
import type {
  EnhancedSignal,
  MLRegimeResponse,
  TrainingStatusResponse,
} from "@/lib/types";

const REFRESH_INTERVAL_MS = 30_000;

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

function probColor(key: string): string {
  if (key === "risk_on") return "#36bb80";
  if (key === "neutral") return "#f5a623";
  return "#e53935";
}

function probLabel(key: string): string {
  if (key === "risk_on") return "风险偏好";
  if (key === "neutral") return "中性";
  return "规避风险";
}

function signalLevelColor(level: string): "error" | "warning" | "default" {
  if (level === "强信号") return "error";
  if (level === "观察信号") return "warning";
  return "default";
}

function biasColor(bias: string): string {
  return bias === "逢高做空" ? "#ff7134" : "#36bb80";
}

function ModelStatusDot({ available }: { available: boolean }) {
  return (
    <Box
      component="span"
      sx={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: "50%",
        bgcolor: available ? "success.main" : "text.disabled",
        mr: 0.75,
        verticalAlign: "middle",
      }}
    />
  );
}

function TrainingStatusCard({
  status,
  onTrain,
  training,
  trainError,
  trainSuccess,
}: {
  status: TrainingStatusResponse | null;
  onTrain: () => void;
  training: boolean;
  trainError: string | null;
  trainSuccess: boolean;
}) {
  return (
    <Card sx={{ height: "100%" }}>
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
          模型训练
        </Typography>

        {status ? (
          <>
            <Box
              sx={{
                display: "flex",
                flexDirection: "column",
                gap: 0.75,
                mb: 2,
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center" }}>
                <ModelStatusDot available={status.regime_model_available} />
                <Typography variant="body2" sx={{ fontSize: "0.8rem" }}>
                  环境模型
                </Typography>
                <Chip
                  label={status.regime_model_available ? "可用" : "未训练"}
                  size="small"
                  color={status.regime_model_available ? "success" : "default"}
                  sx={{ ml: "auto", height: 20, fontSize: "0.65rem" }}
                />
              </Box>
              <Box sx={{ display: "flex", alignItems: "center" }}>
                <ModelStatusDot available={status.scorer_model_available} />
                <Typography variant="body2" sx={{ fontSize: "0.8rem" }}>
                  评分模型
                </Typography>
                <Chip
                  label={status.scorer_model_available ? "可用" : "未训练"}
                  size="small"
                  color={status.scorer_model_available ? "success" : "default"}
                  sx={{ ml: "auto", height: 20, fontSize: "0.65rem" }}
                />
              </Box>
            </Box>

            {status.last_trained && (
              <Typography
                variant="caption"
                sx={{
                  display: "block",
                  mb: 1,
                  color: "text.secondary",
                  fontFamily: "var(--font-geist-mono)",
                  fontSize: "0.65rem",
                }}
              >
                上次训练: {new Date(status.last_trained).toLocaleString()}
              </Typography>
            )}

            {status.symbols_trained.length > 0 && (
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mb: 2 }}>
                {status.symbols_trained.map((sym) => (
                  <Chip
                    key={sym}
                    label={sym}
                    size="small"
                    variant="outlined"
                    sx={{
                      height: 20,
                      fontSize: "0.65rem",
                      fontFamily: "var(--font-geist-mono)",
                    }}
                  />
                ))}
              </Box>
            )}

            {status.error && (
              <Alert
                severity="error"
                sx={{ mb: 1.5, py: 0.5, fontSize: "0.75rem" }}
              >
                {status.error}
              </Alert>
            )}
          </>
        ) : (
          <Box sx={{ mb: 2 }}>
            <Skeleton height={24} sx={{ mb: 0.5 }} />
            <Skeleton height={24} sx={{ mb: 0.5 }} />
            <Skeleton height={16} width="60%" />
          </Box>
        )}

        {trainError && (
          <Alert
            severity="error"
            sx={{ mb: 1.5, py: 0.5, fontSize: "0.75rem" }}
          >
            {trainError}
          </Alert>
        )}
        {trainSuccess && (
          <Alert
            severity="success"
            sx={{ mb: 1.5, py: 0.5, fontSize: "0.75rem" }}
          >
            训练完成
          </Alert>
        )}

        <Button
          variant="outlined"
          size="small"
          onClick={onTrain}
          disabled={training}
          fullWidth
          sx={{ fontSize: "0.75rem", textTransform: "none" }}
        >
          {training ? "训练中…" : "Train Models"}
        </Button>
        {training && <LinearProgress sx={{ mt: 1, borderRadius: 1 }} />}
      </CardContent>
    </Card>
  );
}

function MLRegimeCard({ regime }: { regime: MLRegimeResponse | null }) {
  const PROB_KEYS = ["risk_on", "neutral", "risk_off"] as const;

  return (
    <Card sx={{ height: "100%" }}>
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
          ML 市场环境
        </Typography>

        {regime ? (
          <>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
              <Chip
                label={regimeLabel(regime.regime)}
                color={regimeColor(regime.regime)}
                sx={{ fontWeight: 700, fontSize: "0.78rem", height: 28 }}
              />
              <Chip
                label={regime.source === "ml_hmm" ? "ML-HMM" : "规则"}
                size="small"
                variant="outlined"
                sx={{ height: 22, fontSize: "0.65rem" }}
              />
            </Box>

            <Box sx={{ display: "flex", flexDirection: "column", gap: 1.25 }}>
              {PROB_KEYS.map((key) => {
                const val = regime.probabilities[key] ?? 0;
                const pct = Math.round(val * 100);
                return (
                  <Box key={key}>
                    <Box
                      sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        mb: 0.4,
                      }}
                    >
                      <Typography
                        variant="caption"
                        sx={{ fontSize: "0.7rem", color: "text.secondary" }}
                      >
                        {probLabel(key)}
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{
                          fontSize: "0.7rem",
                          fontFamily: "var(--font-geist-mono)",
                          color: probColor(key),
                          fontWeight: 600,
                        }}
                      >
                        {pct}%
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={pct}
                      sx={{
                        height: 6,
                        borderRadius: 3,
                        bgcolor: "action.hover",
                        "& .MuiLinearProgress-bar": {
                          bgcolor: probColor(key),
                          borderRadius: 3,
                        },
                      }}
                    />
                  </Box>
                );
              })}
            </Box>
          </>
        ) : (
          <>
            <Skeleton height={28} width={160} sx={{ mb: 1.5 }} />
            <Skeleton height={16} sx={{ mb: 0.5 }} />
            <Skeleton height={16} sx={{ mb: 0.5 }} />
            <Skeleton height={16} />
          </>
        )}
      </CardContent>
    </Card>
  );
}

function EnhancedSignalCard({ signal }: { signal: EnhancedSignal }) {
  const levelColor = signalLevelColor(signal.level);
  const mlPct = Math.round(signal.ml_confidence * 100);
  const topFeatures = Object.entries(signal.feature_importance)
    .toSorted(([, a], [, b]) => b - a)
    .slice(0, 3);

  return (
    <Card
      sx={{
        height: "100%",
        borderLeft: "3px solid",
        borderLeftColor:
          signal.level === "强信号"
            ? "error.main"
            : signal.level === "观察信号"
              ? "warning.main"
              : "divider",
        transition: "box-shadow 0.2s ease, transform 0.15s ease",
        "&:hover": {
          boxShadow: "0 4px 12px rgba(0,0,0,0.12)",
          transform: "translateY(-1px)",
        },
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
              规则分数
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
              综合分数
            </Typography>
            <Typography
              sx={{
                fontWeight: 700,
                fontFamily: "var(--font-geist-mono)",
                fontSize: "0.875rem",
                color: "primary.main",
              }}
            >
              {signal.combined_score.toFixed(2)}
            </Typography>
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography
              variant="caption"
              sx={{ color: "text.secondary", display: "block" }}
            >
              ML 置信度
            </Typography>
            <Tooltip title={`ML confidence: ${mlPct}%`} arrow placement="top">
              <Chip
                label={`${mlPct}% ML`}
                size="small"
                sx={{
                  mt: 0.25,
                  height: 22,
                  fontSize: "0.7rem",
                  fontFamily: "var(--font-geist-mono)",
                  fontWeight: 700,
                  bgcolor:
                    mlPct >= 70
                      ? "success.main"
                      : mlPct >= 50
                        ? "warning.main"
                        : "text.disabled",
                  color: "#fff",
                  cursor: "default",
                }}
              />
            </Tooltip>
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography
              variant="caption"
              sx={{ color: "text.secondary", display: "block" }}
            >
              ML 环境
            </Typography>
            <Chip
              label={regimeLabel(signal.ml_regime)}
              color={regimeColor(signal.ml_regime)}
              size="small"
              sx={{
                mt: 0.25,
                height: 22,
                fontSize: "0.65rem",
                fontWeight: 600,
              }}
            />
          </Grid>
        </Grid>

        {topFeatures.length > 0 && (
          <>
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
              特征重要性 TOP 3
            </Typography>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 0.6 }}>
              {topFeatures.map(([feat, val]) => (
                <Box key={feat}>
                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "space-between",
                      mb: 0.25,
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{
                        fontSize: "0.68rem",
                        color: "text.secondary",
                        fontFamily: "var(--font-geist-mono)",
                      }}
                    >
                      {feat}
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{
                        fontSize: "0.68rem",
                        fontFamily: "var(--font-geist-mono)",
                        fontWeight: 600,
                      }}
                    >
                      {(val * 100).toFixed(1)}%
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(val * 100, 100)}
                    sx={{
                      height: 4,
                      borderRadius: 2,
                      bgcolor: "action.hover",
                      "& .MuiLinearProgress-bar": {
                        bgcolor: "primary.main",
                        borderRadius: 2,
                      },
                    }}
                  />
                </Box>
              ))}
            </Box>
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default function MLSection() {
  const [status, setStatus] = useState<TrainingStatusResponse | null>(null);
  const [regime, setRegime] = useState<MLRegimeResponse | null>(null);
  const [signals, setSignals] = useState<EnhancedSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [training, setTraining] = useState(false);
  const [trainError, setTrainError] = useState<string | null>(null);
  const [trainSuccess, setTrainSuccess] = useState(false);

  const load = useCallback((isInitial: boolean) => {
    if (isInitial) setLoading(true);
    Promise.allSettled([
      fetchMLStatus(),
      fetchMLRegime(),
      fetchEnhancedSignals(),
    ])
      .then(([statusRes, regimeRes, signalsRes]) => {
        if (statusRes.status === "fulfilled") setStatus(statusRes.value);
        if (regimeRes.status === "fulfilled") setRegime(regimeRes.value);
        if (signalsRes.status === "fulfilled") setSignals(signalsRes.value);
        setError(null);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load"),
      )
      .finally(() => {
        if (isInitial) setLoading(false);
      });
  }, []);

  useEffect(() => {
    load(true);
    const interval = setInterval(() => load(false), REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [load]);

  const handleTrain = useCallback(() => {
    setTraining(true);
    setTrainError(null);
    setTrainSuccess(false);
    triggerTraining()
      .then((res) => {
        setStatus(res);
        setTrainSuccess(true);
      })
      .catch((e: unknown) => {
        setTrainError(e instanceof Error ? e.message : "训练失败");
      })
      .finally(() => {
        setTraining(false);
      });
  }, []);

  return (
    <Box component="section" id="ml" sx={{ mb: 6 }}>
      <SectionHeader number="05" title="ML 增强" subtitle="ML Enhancement" />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Grid container spacing={2}>
          {[0, 1, 2].map((i) => (
            <Grid key={i} size={{ xs: 12, md: 4 }}>
              <Skeleton variant="rounded" height={200} />
            </Grid>
          ))}
        </Grid>
      ) : (
        <>
          <Grid container spacing={2} sx={{ mb: 4 }}>
            <Grid size={{ xs: 12, md: 4 }}>
              <TrainingStatusCard
                status={status}
                onTrain={handleTrain}
                training={training}
                trainError={trainError}
                trainSuccess={trainSuccess}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 8 }}>
              <MLRegimeCard regime={regime} />
            </Grid>
          </Grid>

          <Typography
            variant="body2"
            sx={{ mb: 1.5, fontWeight: 600, color: "text.secondary" }}
          >
            ML 增强信号{signals.length > 0 ? ` (${signals.length})` : ""}
          </Typography>

          {signals.length === 0 ? (
            <Alert severity="info">暂无 ML 增强信号数据</Alert>
          ) : (
            <Grid container spacing={2}>
              {signals.map((s) => (
                <Grid key={s.symbol} size={{ xs: 12, sm: 6, lg: 4 }}>
                  <EnhancedSignalCard signal={s} />
                </Grid>
              ))}
            </Grid>
          )}
        </>
      )}
    </Box>
  );
}
