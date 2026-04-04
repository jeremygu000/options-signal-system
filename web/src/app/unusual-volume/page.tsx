"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import Skeleton from "@mui/material/Skeleton";
import Alert from "@mui/material/Alert";
import Grid from "@mui/material/Grid";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import Autocomplete from "@mui/material/Autocomplete";
import CircularProgress from "@mui/material/CircularProgress";
import Chip from "@mui/material/Chip";
import Table from "@mui/material/Table";
import TableHead from "@mui/material/TableHead";
import TableBody from "@mui/material/TableBody";
import TableRow from "@mui/material/TableRow";
import TableCell from "@mui/material/TableCell";
import SectionHeader from "@/components/SectionHeader";
import { fetchUnusualVolume, searchSymbols } from "@/lib/api";
import type { UnusualVolumeResponse, SymbolMeta } from "@/lib/types";

const GREEN = "#36bb80";
const RED = "#ff7134";
const BLUE = "#3b89ff";
const YELLOW = "#fdbc2a";
const PURPLE = "#b07aff";

function fmtMoney(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

function fmtNum(v: number, d = 0): string {
  return v.toLocaleString("en-US", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

function fmtPct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function scoreColor(score: number): string {
  if (score >= 9) return RED;
  if (score >= 6) return "#ff9a5c";
  if (score >= 3) return YELLOW;
  return GREEN;
}

function sizeColor(cat: string): string {
  if (cat === "whale") return PURPLE;
  if (cat === "large") return RED;
  if (cat === "institutional") return YELLOW;
  return "default";
}

function voiColor(ratio: number): string {
  if (ratio >= 5.0) return RED;
  if (ratio >= 3.0) return YELLOW;
  return "text.primary";
}

function patternColor(pattern: string): string {
  if (pattern === "call_only" || pattern === "call_heavy") return GREEN;
  if (pattern === "put_only" || pattern === "put_heavy") return RED;
  if (pattern === "balanced") return BLUE;
  return "text.secondary";
}

interface StatCardProps {
  label: string;
  sublabel: string;
  value: string;
  color?: string;
  loading?: boolean;
}

function StatCard({ label, sublabel, value, color, loading }: StatCardProps) {
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
        {loading ? (
          <Skeleton variant="text" width={80} height={32} />
        ) : (
          <Typography
            variant="h6"
            sx={{
              fontFamily: "var(--font-geist-mono)",
              fontWeight: 700,
              fontSize: "1.1rem",
              color: color ?? "text.primary",
            }}
          >
            {value}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

function OverviewSection({
  data,
  loading,
}: {
  data: UnusualVolumeResponse;
  loading: boolean;
}) {
  const sc = scoreColor(data.score);
  return (
    <Box component="section" id="overview" sx={{ mb: 6 }}>
      <SectionHeader number="01" title="异常概览" subtitle="Overview" />

      <Card sx={{ mb: 3 }}>
        <CardContent
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            py: 4,
          }}
        >
          {loading ? (
            <Skeleton variant="text" width={120} height={64} />
          ) : (
            <>
              <Typography
                sx={{
                  fontFamily: "var(--font-geist-mono)",
                  fontWeight: 800,
                  fontSize: "3.5rem",
                  color: sc,
                  lineHeight: 1,
                }}
              >
                {data.score}
              </Typography>
              <Typography
                variant="caption"
                sx={{ color: "text.secondary", mt: 0.5 }}
              >
                / 10
              </Typography>
              <Chip
                label={data.signal.replace(/_/g, " ").toUpperCase()}
                sx={{
                  mt: 1.5,
                  bgcolor: `${sc}22`,
                  color: sc,
                  fontWeight: 700,
                  fontSize: "0.85rem",
                }}
              />
              {data.signal_description && (
                <Typography
                  variant="body2"
                  sx={{ color: "text.secondary", mt: 1, textAlign: "center" }}
                >
                  {data.signal_description}
                </Typography>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Grid container spacing={2}>
        {[
          {
            label: "现价",
            sublabel: "Spot Price",
            value: `$${data.spot_price.toFixed(2)}`,
          },
          {
            label: "扫描合约数",
            sublabel: "Contracts Scanned",
            value: fmtNum(data.total_contracts_scanned),
          },
          {
            label: "异常行权价数",
            sublabel: "Unusual Strikes",
            value: String(data.unusual_strikes_found),
            color: data.unusual_strikes_found > 0 ? YELLOW : undefined,
          },
          {
            label: "异常总权利金",
            sublabel: "Unusual Premium",
            value: fmtMoney(data.total_unusual_premium),
            color: data.total_unusual_premium > 250_000 ? RED : undefined,
          },
          {
            label: "到期日数",
            sublabel: "Expirations Scanned",
            value: String(data.expirations_scanned),
          },
          {
            label: "评分",
            sublabel: "Score",
            value: `${data.score} / 10`,
            color: sc,
          },
        ].map((c) => (
          <Grid key={c.sublabel} size={{ xs: 6, sm: 4, md: 2 }}>
            <StatCard {...c} loading={loading} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}

function ClusterSection({
  data,
  loading,
}: {
  data: UnusualVolumeResponse;
  loading: boolean;
}) {
  const cluster = data.cluster;
  return (
    <Box component="section" id="cluster" sx={{ mb: 6 }}>
      <SectionHeader number="02" title="聚合分析" subtitle="Cluster Analysis" />

      {loading ? (
        <Skeleton variant="rectangular" height={120} />
      ) : !cluster || !cluster.is_clustered ? (
        <Card>
          <CardContent sx={{ textAlign: "center", py: 4 }}>
            <Typography variant="body1" sx={{ color: "text.secondary" }}>
              无聚合模式 — No clustering detected
            </Typography>
          </CardContent>
        </Card>
      ) : (
        <>
          <Box sx={{ mb: 2, display: "flex", alignItems: "center", gap: 1.5 }}>
            <Typography variant="body2" sx={{ color: "text.secondary" }}>
              Pattern:
            </Typography>
            <Chip
              label={cluster.pattern.replace(/_/g, " ").toUpperCase()}
              sx={{
                bgcolor: `${patternColor(cluster.pattern)}22`,
                color: patternColor(cluster.pattern),
                fontWeight: 700,
              }}
            />
          </Box>
          <Grid container spacing={2}>
            {[
              {
                label: "看涨异常数",
                sublabel: "Call Count",
                value: String(cluster.unusual_call_count),
                color: GREEN,
              },
              {
                label: "看跌异常数",
                sublabel: "Put Count",
                value: String(cluster.unusual_put_count),
                color: RED,
              },
              {
                label: "总权利金",
                sublabel: "Total Premium",
                value: fmtMoney(cluster.total_premium),
              },
              {
                label: "总合约数",
                sublabel: "Total Contracts",
                value: fmtNum(cluster.total_contracts),
              },
            ].map((c) => (
              <Grid key={c.sublabel} size={{ xs: 6, sm: 3 }}>
                <StatCard {...c} loading={false} />
              </Grid>
            ))}
          </Grid>
        </>
      )}
    </Box>
  );
}

function StrikesSection({
  data,
  loading,
}: {
  data: UnusualVolumeResponse;
  loading: boolean;
}) {
  const sorted = useMemo(
    () => data.strikes.toSorted((a, b) => b.voi_ratio - a.voi_ratio),
    [data.strikes],
  );

  return (
    <Box component="section" id="strikes" sx={{ mb: 6 }}>
      <SectionHeader
        number="03"
        title="异常行权价"
        subtitle="Unusual Strikes"
      />

      {loading ? (
        <Skeleton variant="rectangular" height={300} />
      ) : sorted.length === 0 ? (
        <Card>
          <CardContent sx={{ textAlign: "center", py: 4 }}>
            <Typography variant="body1" sx={{ color: "text.secondary" }}>
              未发现异常行权价
            </Typography>
          </CardContent>
        </Card>
      ) : (
        <Card sx={{ overflowX: "auto" }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Exp</TableCell>
                <TableCell align="right">DTE</TableCell>
                <TableCell align="right">Strike</TableCell>
                <TableCell>Type</TableCell>
                <TableCell align="right">Volume</TableCell>
                <TableCell align="right">OI</TableCell>
                <TableCell align="right">V/OI</TableCell>
                <TableCell align="right">Bid</TableCell>
                <TableCell align="right">Ask</TableCell>
                <TableCell align="right">Mid</TableCell>
                <TableCell align="right">IV</TableCell>
                <TableCell align="right">Premium</TableCell>
                <TableCell align="right">Moneyness</TableCell>
                <TableCell>Size</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sorted.map((s) => (
                <TableRow
                  key={`${s.expiration}-${s.strike}-${s.option_type}`}
                  sx={{
                    bgcolor: s.voi_ratio >= 5.0 ? `${RED}0a` : "transparent",
                  }}
                >
                  <TableCell sx={{ whiteSpace: "nowrap" }}>
                    {s.expiration}
                  </TableCell>
                  <TableCell align="right">{s.dte_days}</TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontFamily: "var(--font-geist-mono)" }}
                  >
                    {s.strike.toFixed(1)}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={s.option_type.toUpperCase()}
                      size="small"
                      sx={{
                        bgcolor:
                          s.option_type === "call" ? `${GREEN}22` : `${RED}22`,
                        color: s.option_type === "call" ? GREEN : RED,
                        fontWeight: 700,
                        fontSize: "0.7rem",
                      }}
                    />
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontFamily: "var(--font-geist-mono)" }}
                  >
                    {fmtNum(s.volume)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontFamily: "var(--font-geist-mono)" }}
                  >
                    {fmtNum(s.open_interest)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 700,
                      color: voiColor(s.voi_ratio),
                    }}
                  >
                    {s.voi_ratio.toFixed(1)}x
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontFamily: "var(--font-geist-mono)" }}
                  >
                    {s.bid.toFixed(2)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontFamily: "var(--font-geist-mono)" }}
                  >
                    {s.ask.toFixed(2)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontFamily: "var(--font-geist-mono)" }}
                  >
                    {s.mid_price.toFixed(2)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontFamily: "var(--font-geist-mono)" }}
                  >
                    {fmtPct(s.implied_volatility)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontFamily: "var(--font-geist-mono)" }}
                  >
                    {fmtMoney(s.premium)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontFamily: "var(--font-geist-mono)" }}
                  >
                    {fmtPct(s.moneyness)}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={s.size_category}
                      size="small"
                      sx={{
                        bgcolor:
                          sizeColor(s.size_category) === "default"
                            ? undefined
                            : `${sizeColor(s.size_category)}22`,
                        color:
                          sizeColor(s.size_category) === "default"
                            ? "text.secondary"
                            : sizeColor(s.size_category),
                        fontWeight: 600,
                        fontSize: "0.7rem",
                      }}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </Box>
  );
}

function ChartSection({
  data,
  loading,
}: {
  data: UnusualVolumeResponse;
  loading: boolean;
}) {
  const sorted = useMemo(
    () => data.strikes.toSorted((a, b) => a.strike - b.strike),
    [data.strikes],
  );

  if (loading) {
    return (
      <Box component="section" id="chart" sx={{ mb: 6 }}>
        <SectionHeader
          number="04"
          title="V/OI 分布"
          subtitle="V/OI Distribution"
        />
        <Skeleton variant="rectangular" height={260} />
      </Box>
    );
  }

  if (sorted.length === 0) return null;

  const maxVoi = Math.max(...sorted.map((s) => s.voi_ratio), 6);
  const W = 800;
  const H = 240;
  const PAD_L = 50;
  const PAD_R = 20;
  const PAD_T = 20;
  const PAD_B = 50;
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;
  const barW = Math.max(6, Math.min(30, plotW / sorted.length - 4));

  return (
    <Box component="section" id="chart" sx={{ mb: 6 }}>
      <SectionHeader
        number="04"
        title="V/OI 分布"
        subtitle="V/OI Distribution"
      />
      <Card>
        <CardContent>
          <Box sx={{ overflowX: "auto" }}>
            <svg
              viewBox={`0 0 ${W} ${H}`}
              width="100%"
              style={{ maxHeight: 300 }}
            >
              <line
                x1={PAD_L}
                y1={PAD_T + plotH - (3.0 / maxVoi) * plotH}
                x2={W - PAD_R}
                y2={PAD_T + plotH - (3.0 / maxVoi) * plotH}
                stroke={YELLOW}
                strokeWidth={1}
                strokeDasharray="6 3"
              />
              <text
                x={PAD_L - 4}
                y={PAD_T + plotH - (3.0 / maxVoi) * plotH + 4}
                textAnchor="end"
                fill={YELLOW}
                fontSize={10}
              >
                3.0
              </text>
              {maxVoi >= 5.0 && (
                <>
                  <line
                    x1={PAD_L}
                    y1={PAD_T + plotH - (5.0 / maxVoi) * plotH}
                    x2={W - PAD_R}
                    y2={PAD_T + plotH - (5.0 / maxVoi) * plotH}
                    stroke={RED}
                    strokeWidth={1}
                    strokeDasharray="6 3"
                  />
                  <text
                    x={PAD_L - 4}
                    y={PAD_T + plotH - (5.0 / maxVoi) * plotH + 4}
                    textAnchor="end"
                    fill={RED}
                    fontSize={10}
                  >
                    5.0
                  </text>
                </>
              )}
              {sorted.map((s, i) => {
                const x =
                  PAD_L +
                  (i / sorted.length) * plotW +
                  plotW / sorted.length / 2;
                const barH = (s.voi_ratio / maxVoi) * plotH;
                const barColor = s.option_type === "call" ? GREEN : RED;
                return (
                  <g key={`${s.expiration}-${s.strike}-${s.option_type}`}>
                    <rect
                      x={x - barW / 2}
                      y={PAD_T + plotH - barH}
                      width={barW}
                      height={barH}
                      fill={barColor}
                      opacity={0.8}
                      rx={2}
                    />
                    <text
                      x={x}
                      y={H - PAD_B + 14}
                      textAnchor="middle"
                      fill="currentColor"
                      fontSize={8}
                      opacity={0.6}
                      transform={`rotate(-45 ${x} ${H - PAD_B + 14})`}
                    >
                      {s.strike}
                    </text>
                  </g>
                );
              })}
              <line
                x1={PAD_L}
                y1={PAD_T}
                x2={PAD_L}
                y2={PAD_T + plotH}
                stroke="currentColor"
                strokeWidth={1}
                opacity={0.2}
              />
              <line
                x1={PAD_L}
                y1={PAD_T + plotH}
                x2={W - PAD_R}
                y2={PAD_T + plotH}
                stroke="currentColor"
                strokeWidth={1}
                opacity={0.2}
              />
            </svg>
          </Box>
          <Box
            sx={{
              display: "flex",
              justifyContent: "center",
              gap: 3,
              mt: 1,
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Box
                sx={{
                  width: 12,
                  height: 12,
                  bgcolor: GREEN,
                  borderRadius: 0.5,
                }}
              />
              <Typography variant="caption">Call</Typography>
            </Box>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Box
                sx={{
                  width: 12,
                  height: 12,
                  bgcolor: RED,
                  borderRadius: 0.5,
                }}
              />
              <Typography variant="caption">Put</Typography>
            </Box>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}

function CompareSection({
  data,
  loading,
}: {
  data: UnusualVolumeResponse;
  loading: boolean;
}) {
  const callStrikes = useMemo(
    () => data.strikes.filter((s) => s.option_type === "call"),
    [data.strikes],
  );
  const putStrikes = useMemo(
    () => data.strikes.filter((s) => s.option_type === "put"),
    [data.strikes],
  );

  const callVol = callStrikes.reduce((a, s) => a + s.volume, 0);
  const putVol = putStrikes.reduce((a, s) => a + s.volume, 0);
  const callPrem = callStrikes.reduce((a, s) => a + s.premium, 0);
  const putPrem = putStrikes.reduce((a, s) => a + s.premium, 0);
  const callAvgVoi =
    callStrikes.length > 0
      ? callStrikes.reduce((a, s) => a + s.voi_ratio, 0) / callStrikes.length
      : 0;
  const putAvgVoi =
    putStrikes.length > 0
      ? putStrikes.reduce((a, s) => a + s.voi_ratio, 0) / putStrikes.length
      : 0;

  const dominant =
    callPrem > putPrem ? "CALL" : putPrem > callPrem ? "PUT" : "BALANCED";
  const domColor =
    dominant === "CALL" ? GREEN : dominant === "PUT" ? RED : BLUE;

  return (
    <Box component="section" id="compare" sx={{ mb: 6 }}>
      <SectionHeader
        number="05"
        title="期权类型对比"
        subtitle="Call vs Put Comparison"
      />

      {loading ? (
        <Skeleton variant="rectangular" height={160} />
      ) : (
        <>
          <Box sx={{ textAlign: "center", mb: 2 }}>
            <Chip
              label={`${dominant} DOMINANT`}
              sx={{
                bgcolor: `${domColor}22`,
                color: domColor,
                fontWeight: 700,
                fontSize: "0.85rem",
              }}
            />
          </Box>
          <Grid container spacing={3}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Card
                sx={{
                  borderTop: `3px solid ${GREEN}`,
                }}
              >
                <CardContent>
                  <Typography
                    variant="h6"
                    sx={{ fontWeight: 700, color: GREEN, mb: 2 }}
                  >
                    CALL
                  </Typography>
                  <Grid container spacing={1}>
                    {[
                      {
                        label: "异常数",
                        value: String(callStrikes.length),
                      },
                      {
                        label: "总成交量",
                        value: fmtNum(callVol),
                      },
                      {
                        label: "总权利金",
                        value: fmtMoney(callPrem),
                      },
                      {
                        label: "平均 V/OI",
                        value: callAvgVoi.toFixed(1) + "x",
                      },
                    ].map((item) => (
                      <Grid key={`call-${item.label}`} size={6}>
                        <Typography
                          variant="caption"
                          sx={{ color: "text.secondary" }}
                        >
                          {item.label}
                        </Typography>
                        <Typography
                          sx={{
                            fontFamily: "var(--font-geist-mono)",
                            fontWeight: 700,
                          }}
                        >
                          {item.value}
                        </Typography>
                      </Grid>
                    ))}
                  </Grid>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Card
                sx={{
                  borderTop: `3px solid ${RED}`,
                }}
              >
                <CardContent>
                  <Typography
                    variant="h6"
                    sx={{ fontWeight: 700, color: RED, mb: 2 }}
                  >
                    PUT
                  </Typography>
                  <Grid container spacing={1}>
                    {[
                      {
                        label: "异常数",
                        value: String(putStrikes.length),
                      },
                      {
                        label: "总成交量",
                        value: fmtNum(putVol),
                      },
                      {
                        label: "总权利金",
                        value: fmtMoney(putPrem),
                      },
                      {
                        label: "平均 V/OI",
                        value: putAvgVoi.toFixed(1) + "x",
                      },
                    ].map((item) => (
                      <Grid key={`put-${item.label}`} size={6}>
                        <Typography
                          variant="caption"
                          sx={{ color: "text.secondary" }}
                        >
                          {item.label}
                        </Typography>
                        <Typography
                          sx={{
                            fontFamily: "var(--font-geist-mono)",
                            fontWeight: 700,
                          }}
                        >
                          {item.value}
                        </Typography>
                      </Grid>
                    ))}
                  </Grid>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </>
      )}
    </Box>
  );
}

function GuideSection() {
  const guides = [
    {
      title: "V/OI Ratio",
      desc: "Volume/Open Interest 比率。大于 3.0 为异常活跃，大于 5.0 为高度异常，可能代表知情交易。",
    },
    {
      title: "Size Categories",
      desc: "Retail (<100), Institutional (500+), Large (1,000+), Whale (5,000+)。大单尤其值得关注。",
    },
    {
      title: "Clustering",
      desc: "同一到期日出现 3+ 异常行权价，表明可能存在协调交易行为或大资金集中布局。",
    },
    {
      title: "Signal Scoring",
      desc: "0-10 综合评分：基于成交量权重、权利金权重、聚合模式、鲸鱼单存在、高 V/OI 比率五项因子。",
    },
  ];

  return (
    <Box component="section" id="guide" sx={{ mb: 6 }}>
      <SectionHeader
        number="06"
        title="解读说明"
        subtitle="Interpretation Guide"
      />
      <Grid container spacing={2}>
        {guides.map((g) => (
          <Grid key={g.title} size={{ xs: 12, sm: 6 }}>
            <Card sx={{ height: "100%" }}>
              <CardContent>
                <Typography
                  variant="body2"
                  sx={{ fontWeight: 700, mb: 1, color: BLUE }}
                >
                  {g.title}
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ color: "text.secondary", lineHeight: 1.6 }}
                >
                  {g.desc}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}

const EMPTY: UnusualVolumeResponse = {
  symbol: "",
  spot_price: 0,
  total_contracts_scanned: 0,
  unusual_strikes_found: 0,
  total_unusual_premium: 0,
  signal: "neutral",
  signal_description: "",
  score: 0,
  strikes: [],
  cluster: null,
  expirations_scanned: 0,
  error: null,
};

export default function UnusualVolumePage() {
  const [symbol, setSymbol] = useState("AAPL");
  const [input, setInput] = useState("AAPL");
  const [data, setData] = useState<UnusualVolumeResponse>(EMPTY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [options, setOptions] = useState<SymbolMeta[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (sym: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchUnusualVolume(sym);
      setData(res);
      if (res.error) setError(res.error);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSubmit = useCallback(() => {
    const s = input.trim().toUpperCase();
    if (!s) return;
    setSymbol(s);
    load(s);
  }, [input, load]);

  const handleInputChange = useCallback(
    (_event: React.SyntheticEvent, value: string) => {
      const upper = value.toUpperCase();
      setInput(upper);

      if (debounceRef.current) clearTimeout(debounceRef.current);

      if (!upper.trim()) {
        setOptions([]);
        return;
      }

      debounceRef.current = setTimeout(() => {
        setSearchLoading(true);
        searchSymbols({ query: upper, limit: 20, sort_by: "volume" })
          .then((res) => setOptions(res.items))
          .catch(() => setOptions([]))
          .finally(() => setSearchLoading(false));
      }, 250);
    },
    [],
  );

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  return (
    <Box sx={{ maxWidth: 1100, mx: "auto" }}>
      <Box sx={{ mb: 3 }}>
        <Typography
          variant="h5"
          sx={{ fontWeight: 800, fontSize: "1.4rem", mb: 0.25 }}
        >
          异常成交量
        </Typography>
        <Typography variant="body2" sx={{ color: "text.secondary" }}>
          Unusual Volume · {symbol}
        </Typography>
      </Box>

      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Box
            sx={{
              display: "flex",
              gap: 1.5,
              alignItems: "center",
              flexWrap: "wrap",
            }}
          >
            <Autocomplete
              freeSolo
              options={options}
              getOptionLabel={(opt) =>
                typeof opt === "string" ? opt : opt.symbol
              }
              inputValue={input}
              onInputChange={handleInputChange}
              onChange={(_event, value) => {
                if (value && typeof value !== "string") {
                  setInput(value.symbol);
                }
              }}
              loading={searchLoading}
              filterOptions={(x) => x}
              renderOption={(props, opt) => {
                const meta = opt as SymbolMeta;
                return (
                  <Box component="li" {...props} key={meta.symbol}>
                    <Typography
                      variant="body2"
                      sx={{
                        fontFamily: "var(--font-geist-mono)",
                        fontWeight: 700,
                      }}
                    >
                      {meta.symbol}
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{ ml: 1, color: "text.secondary" }}
                    >
                      ${meta.last_close.toFixed(2)} ·{" "}
                      {meta.avg_volume >= 1e6
                        ? `${(meta.avg_volume / 1e6).toFixed(1)}M vol`
                        : `${(meta.avg_volume / 1e3).toFixed(0)}K vol`}
                    </Typography>
                  </Box>
                );
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  size="small"
                  label="标的 Symbol"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleSubmit();
                    }
                  }}
                  sx={{ width: 280 }}
                  slotProps={{
                    htmlInput: {
                      ...params.inputProps,
                      style: {
                        fontFamily: "var(--font-geist-mono)",
                        fontWeight: 700,
                      },
                    },
                    input: {
                      ...params.InputProps,
                      endAdornment: (
                        <>
                          {searchLoading ? (
                            <CircularProgress color="inherit" size={18} />
                          ) : null}
                          {params.InputProps.endAdornment}
                        </>
                      ),
                    },
                  }}
                />
              )}
              sx={{ flex: "0 0 auto" }}
            />
            <Button
              variant="contained"
              onClick={handleSubmit}
              disabled={loading || !input.trim()}
              sx={{
                fontWeight: 700,
              }}
            >
              {loading ? "加载中..." : "查询"}
            </Button>
          </Box>
        </CardContent>
      </Card>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <OverviewSection data={data} loading={loading} />
      <ClusterSection data={data} loading={loading} />
      <StrikesSection data={data} loading={loading} />
      <ChartSection data={data} loading={loading} />
      <CompareSection data={data} loading={loading} />
      <GuideSection />
    </Box>
  );
}
