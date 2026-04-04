"use client";

import { useState, useCallback } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import Skeleton from "@mui/material/Skeleton";
import Alert from "@mui/material/Alert";
import Grid from "@mui/material/Grid";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Table from "@mui/material/Table";
import TableHead from "@mui/material/TableHead";
import TableBody from "@mui/material/TableBody";
import TableRow from "@mui/material/TableRow";
import TableCell from "@mui/material/TableCell";
import SectionHeader from "@/components/SectionHeader";
import { useThemeMode } from "@/components/ThemeProvider";
import { fetchPutCallRatio } from "@/lib/api";
import type {
  PutCallRatioResponse,
  PCRStrikePoint,
  PCRTermPoint,
} from "@/lib/types";

const GREEN = "#36bb80";
const RED = "#ff7134";
const BLUE = "#3b89ff";
const YELLOW = "#fdbc2a";

const THRESHOLDS = [
  { value: 0.45, label: "极度贪婪", color: GREEN },
  { value: 0.55, label: "高度贪婪", color: "#6dd9a8" },
  { value: 0.7, label: "中性低", color: YELLOW },
  { value: 0.85, label: "中性高", color: "#e8a820" },
  { value: 1.0, label: "高度恐惧", color: "#ff9a5c" },
  { value: 1.15, label: "极度恐惧", color: RED },
];

function fmtNum(value: number, decimals = 2): string {
  return value.toFixed(decimals);
}

function fmtVol(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return String(value);
}

function signalColor(signal: string): string {
  if (signal.includes("bullish")) return GREEN;
  if (signal.includes("bearish")) return RED;
  return YELLOW;
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

function AggregateSection({
  data,
  loading,
}: {
  data: PutCallRatioResponse;
  loading: boolean;
}) {
  const sc = signalColor(data.signal);
  return (
    <Box component="section" id="aggregate" sx={{ mb: 6 }}>
      <SectionHeader number="01" title="综合比率" subtitle="Aggregate Ratios" />

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
                  fontSize: "3rem",
                  color: sc,
                  lineHeight: 1,
                }}
              >
                {fmtNum(data.pcr_volume, 3)}
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
              <Typography
                variant="body2"
                sx={{ color: "text.secondary", mt: 1, textAlign: "center" }}
              >
                {data.signal_description}
              </Typography>
            </>
          )}
        </CardContent>
      </Card>

      <Grid container spacing={2}>
        {[
          {
            label: "PCR 成交量",
            sublabel: "PCR Volume",
            value: fmtNum(data.pcr_volume, 3),
          },
          {
            label: "PCR 持仓量",
            sublabel: "PCR Open Interest",
            value: fmtNum(data.pcr_oi, 3),
          },
          {
            label: "ATM PCR 成交量",
            sublabel: "ATM PCR Volume",
            value: fmtNum(data.atm_pcr_volume, 3),
          },
          {
            label: "ATM PCR 持仓量",
            sublabel: "ATM PCR OI",
            value: fmtNum(data.atm_pcr_oi, 3),
          },
          {
            label: "看涨总成交量",
            sublabel: "Total Call Vol",
            value: fmtVol(data.total_call_volume),
          },
          {
            label: "看跌总成交量",
            sublabel: "Total Put Vol",
            value: fmtVol(data.total_put_volume),
          },
          {
            label: "看涨总持仓量",
            sublabel: "Total Call OI",
            value: fmtVol(data.total_call_oi),
          },
          {
            label: "看跌总持仓量",
            sublabel: "Total Put OI",
            value: fmtVol(data.total_put_oi),
          },
        ].map((c) => (
          <Grid key={c.sublabel} size={{ xs: 6, sm: 3 }}>
            <StatCard {...c} loading={loading} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}

function GaugeSection({
  data,
  loading,
}: {
  data: PutCallRatioResponse;
  loading: boolean;
}) {
  const { mode } = useThemeMode();
  const isDark = mode === "dark";
  const gaugeMax = 1.5;
  const pct = Math.min(data.pcr_volume / gaugeMax, 1) * 100;

  return (
    <Box component="section" id="gauge" sx={{ mb: 6 }}>
      <SectionHeader number="02" title="情绪信号" subtitle="Sentiment Signal" />

      <Card>
        <CardContent sx={{ py: 4, px: 3 }}>
          {loading ? (
            <Skeleton variant="rectangular" height={60} />
          ) : (
            <>
              <Box
                sx={{
                  position: "relative",
                  height: 32,
                  borderRadius: 2,
                  background: `linear-gradient(to right, ${GREEN}, ${YELLOW} 47%, ${YELLOW} 53%, ${RED})`,
                  mb: 1,
                }}
              >
                <Box
                  sx={{
                    position: "absolute",
                    left: `${pct}%`,
                    top: -6,
                    transform: "translateX(-50%)",
                    width: 0,
                    height: 0,
                    borderLeft: "8px solid transparent",
                    borderRight: "8px solid transparent",
                    borderTop: `10px solid ${isDark ? "#fff" : "#000"}`,
                  }}
                />
                <Box
                  sx={{
                    position: "absolute",
                    left: `${pct}%`,
                    bottom: -6,
                    transform: "translateX(-50%)",
                    width: 0,
                    height: 0,
                    borderLeft: "8px solid transparent",
                    borderRight: "8px solid transparent",
                    borderBottom: `10px solid ${isDark ? "#fff" : "#000"}`,
                  }}
                />
              </Box>

              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  position: "relative",
                  height: 36,
                  mt: 1,
                }}
              >
                {THRESHOLDS.map((t) => (
                  <Box
                    key={t.value}
                    sx={{
                      position: "absolute",
                      left: `${(t.value / gaugeMax) * 100}%`,
                      transform: "translateX(-50%)",
                      textAlign: "center",
                    }}
                  >
                    <Box
                      sx={{
                        width: 1,
                        height: 8,
                        bgcolor: isDark
                          ? "rgba(255,255,255,0.3)"
                          : "rgba(0,0,0,0.2)",
                        mx: "auto",
                        mb: 0.3,
                      }}
                    />
                    <Typography
                      variant="caption"
                      sx={{
                        fontSize: "0.6rem",
                        color: "text.secondary",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {t.value}
                    </Typography>
                  </Box>
                ))}
              </Box>

              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  mt: 1,
                }}
              >
                <Typography
                  variant="caption"
                  sx={{ color: GREEN, fontWeight: 700 }}
                >
                  ← 贪婪 (看涨)
                </Typography>
                <Typography
                  variant="caption"
                  sx={{ color: RED, fontWeight: 700 }}
                >
                  恐惧 (看跌) →
                </Typography>
              </Box>
            </>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}

function StrikeSection({
  data,
  loading,
}: {
  data: PutCallRatioResponse;
  loading: boolean;
}) {
  const strikes = data.strike_points;
  return (
    <Box component="section" id="strikes" sx={{ mb: 6 }}>
      <SectionHeader
        number="03"
        title="行权价分布"
        subtitle="Strike Distribution"
      />

      <Card sx={{ overflow: "auto" }}>
        {loading ? (
          <Skeleton variant="rectangular" height={200} sx={{ m: 2 }} />
        ) : strikes.length === 0 ? (
          <Alert severity="info" sx={{ m: 2 }}>
            无行权价数据
          </Alert>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Strike</TableCell>
                <TableCell align="right">Call Vol</TableCell>
                <TableCell align="right">Put Vol</TableCell>
                <TableCell align="right">Call OI</TableCell>
                <TableCell align="right">Put OI</TableCell>
                <TableCell align="right">PCR Vol</TableCell>
                <TableCell align="right">PCR OI</TableCell>
                <TableCell align="right">Moneyness</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {strikes.map((s: PCRStrikePoint) => {
                const isAtm = s.moneyness >= -0.05 && s.moneyness <= 0.05;
                const mc =
                  s.moneyness < -0.02
                    ? GREEN
                    : s.moneyness > 0.02
                      ? RED
                      : YELLOW;
                return (
                  <TableRow
                    key={s.strike}
                    sx={
                      isAtm
                        ? {
                            bgcolor: `${YELLOW}15`,
                          }
                        : undefined
                    }
                  >
                    <TableCell
                      sx={{
                        fontFamily: "var(--font-geist-mono)",
                        fontWeight: isAtm ? 700 : 400,
                      }}
                    >
                      {fmtNum(s.strike, 1)}
                      {isAtm && (
                        <Chip
                          label="ATM"
                          size="small"
                          sx={{
                            ml: 1,
                            height: 18,
                            fontSize: "0.6rem",
                            bgcolor: `${YELLOW}33`,
                            color: YELLOW,
                          }}
                        />
                      )}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontFamily: "var(--font-geist-mono)" }}
                    >
                      {fmtVol(s.call_volume)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontFamily: "var(--font-geist-mono)" }}
                    >
                      {fmtVol(s.put_volume)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontFamily: "var(--font-geist-mono)" }}
                    >
                      {fmtVol(s.call_oi)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontFamily: "var(--font-geist-mono)" }}
                    >
                      {fmtVol(s.put_oi)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontFamily: "var(--font-geist-mono)" }}
                    >
                      {fmtNum(s.pcr_volume, 3)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontFamily: "var(--font-geist-mono)" }}
                    >
                      {fmtNum(s.pcr_oi, 3)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{
                        fontFamily: "var(--font-geist-mono)",
                        color: mc,
                        fontWeight: 600,
                      }}
                    >
                      {fmtNum(s.moneyness, 3)}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Card>
    </Box>
  );
}

function TermSection({
  data,
  loading,
}: {
  data: PutCallRatioResponse;
  loading: boolean;
}) {
  const { mode } = useThemeMode();
  const isDark = mode === "dark";
  const terms = data.term_structure;

  const chartW = 600;
  const chartH = 200;
  const pad = { top: 20, right: 20, bottom: 30, left: 50 };
  const w = chartW - pad.left - pad.right;
  const h = chartH - pad.top - pad.bottom;

  let volPath = "";
  let oiPath = "";

  if (terms.length > 1) {
    const maxPcr = Math.max(
      ...terms.map((t: PCRTermPoint) => Math.max(t.pcr_volume, t.pcr_oi)),
      0.1,
    );
    const xStep = w / (terms.length - 1);

    terms.forEach((t: PCRTermPoint, i: number) => {
      const x = pad.left + i * xStep;
      const yVol = pad.top + h - (t.pcr_volume / maxPcr) * h;
      const yOi = pad.top + h - (t.pcr_oi / maxPcr) * h;
      volPath += i === 0 ? `M${x},${yVol}` : ` L${x},${yVol}`;
      oiPath += i === 0 ? `M${x},${yOi}` : ` L${x},${yOi}`;
    });
  }

  return (
    <Box component="section" id="term" sx={{ mb: 6 }}>
      <SectionHeader number="04" title="期限结构" subtitle="Term Structure" />

      <Card sx={{ mb: 2 }}>
        <CardContent>
          {loading ? (
            <Skeleton variant="rectangular" height={200} />
          ) : terms.length < 2 ? (
            <Alert severity="info">需要至少2个到期日绘制曲线</Alert>
          ) : (
            <>
              <Box sx={{ display: "flex", gap: 2, mb: 1 }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                  <Box
                    sx={{
                      width: 16,
                      height: 3,
                      bgcolor: BLUE,
                      borderRadius: 1,
                    }}
                  />
                  <Typography variant="caption">PCR Volume</Typography>
                </Box>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                  <Box
                    sx={{
                      width: 16,
                      height: 3,
                      bgcolor: GREEN,
                      borderRadius: 1,
                    }}
                  />
                  <Typography variant="caption">PCR OI</Typography>
                </Box>
              </Box>
              <svg
                viewBox={`0 0 ${chartW} ${chartH}`}
                style={{ width: "100%", height: "auto" }}
              >
                <line
                  x1={pad.left}
                  y1={pad.top + h}
                  x2={pad.left + w}
                  y2={pad.top + h}
                  stroke={isDark ? "#555" : "#ccc"}
                  strokeWidth={1}
                />
                <path
                  d={volPath}
                  fill="none"
                  stroke={BLUE}
                  strokeWidth={2.5}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d={oiPath}
                  fill="none"
                  stroke={GREEN}
                  strokeWidth={2.5}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {terms.map((t: PCRTermPoint, i: number) => {
                  const maxPcr = Math.max(
                    ...terms.map((p: PCRTermPoint) =>
                      Math.max(p.pcr_volume, p.pcr_oi),
                    ),
                    0.1,
                  );
                  const xStep = w / (terms.length - 1);
                  const x = pad.left + i * xStep;
                  const yVol = pad.top + h - (t.pcr_volume / maxPcr) * h;
                  const yOi = pad.top + h - (t.pcr_oi / maxPcr) * h;
                  return (
                    <g key={t.expiration}>
                      <circle cx={x} cy={yVol} r={3.5} fill={BLUE} />
                      <circle cx={x} cy={yOi} r={3.5} fill={GREEN} />
                      <text
                        x={x}
                        y={pad.top + h + 16}
                        textAnchor="middle"
                        fill={isDark ? "#aaa" : "#666"}
                        fontSize={10}
                      >
                        {t.dte_days}d
                      </text>
                    </g>
                  );
                })}
              </svg>
            </>
          )}
        </CardContent>
      </Card>

      <Card sx={{ overflow: "auto" }}>
        {terms.length === 0 ? (
          <Alert severity="info" sx={{ m: 2 }}>
            无期限结构数据
          </Alert>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Expiration</TableCell>
                <TableCell align="right">DTE</TableCell>
                <TableCell align="right">Call Vol</TableCell>
                <TableCell align="right">Put Vol</TableCell>
                <TableCell align="right">Call OI</TableCell>
                <TableCell align="right">Put OI</TableCell>
                <TableCell align="right">PCR Vol</TableCell>
                <TableCell align="right">PCR OI</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {terms.map((t: PCRTermPoint) => (
                <TableRow key={t.expiration}>
                  <TableCell sx={{ fontFamily: "var(--font-geist-mono)" }}>
                    {t.expiration}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontFamily: "var(--font-geist-mono)" }}
                  >
                    {t.dte_days}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontFamily: "var(--font-geist-mono)" }}
                  >
                    {fmtVol(t.call_volume)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontFamily: "var(--font-geist-mono)" }}
                  >
                    {fmtVol(t.put_volume)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontFamily: "var(--font-geist-mono)" }}
                  >
                    {fmtVol(t.call_oi)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontFamily: "var(--font-geist-mono)" }}
                  >
                    {fmtVol(t.put_oi)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      color: BLUE,
                      fontWeight: 600,
                    }}
                  >
                    {fmtNum(t.pcr_volume, 3)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      color: GREEN,
                      fontWeight: 600,
                    }}
                  >
                    {fmtNum(t.pcr_oi, 3)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </Box>
  );
}

function GuideSection() {
  const items = [
    {
      title: "PCR > 1.0",
      desc: "看跌期权交易量大于看涨 → 市场偏悲观 → 反向看涨信号",
    },
    {
      title: "PCR < 0.7",
      desc: "看涨期权交易量远大于看跌 → 市场偏乐观 → 反向看跌信号",
    },
    {
      title: "ATM 加权 PCR",
      desc: "仅考虑接近现价的行权价，过滤远价位投机，信号更可靠",
    },
    {
      title: "期限结构",
      desc: "近月 PCR 反映短期情绪，远月 PCR 反映长期预期",
    },
  ];

  return (
    <Box component="section" id="guide" sx={{ mb: 6 }}>
      <SectionHeader
        number="05"
        title="解读说明"
        subtitle="Interpretation Guide"
      />
      <Grid container spacing={2}>
        {items.map((item) => (
          <Grid key={item.title} size={{ xs: 12, sm: 6 }}>
            <Card sx={{ height: "100%" }}>
              <CardContent>
                <Typography
                  variant="body1"
                  sx={{
                    fontWeight: 700,
                    fontFamily: "var(--font-geist-mono)",
                    mb: 0.5,
                  }}
                >
                  {item.title}
                </Typography>
                <Typography variant="body2" sx={{ color: "text.secondary" }}>
                  {item.desc}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}

const EMPTY: PutCallRatioResponse = {
  symbol: "",
  spot_price: 0,
  total_call_volume: 0,
  total_put_volume: 0,
  total_call_oi: 0,
  total_put_oi: 0,
  pcr_volume: 0,
  pcr_oi: 0,
  atm_pcr_volume: 0,
  atm_pcr_oi: 0,
  signal: "neutral",
  signal_description: "",
  strike_points: [],
  term_structure: [],
  expirations_analysed: 0,
  error: null,
};

export default function PutCallRatioPage() {
  const [symbol, setSymbol] = useState("AAPL");
  const [input, setInput] = useState("AAPL");
  const [data, setData] = useState<PutCallRatioResponse>(EMPTY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (sym: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchPutCallRatio(sym);
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

  return (
    <Box sx={{ maxWidth: 1100, mx: "auto" }}>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 2,
          mb: 4,
          flexWrap: "wrap",
        }}
      >
        <Typography variant="h5" sx={{ fontWeight: 800 }}>
          看跌/看涨比率
        </Typography>
        <Typography variant="body2" sx={{ color: "text.secondary" }}>
          Put/Call Ratio · {symbol}
        </Typography>
        <Box sx={{ ml: "auto", display: "flex", gap: 1 }}>
          <TextField
            size="small"
            value={input}
            onChange={(e) => setInput(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            placeholder="Symbol"
            sx={{ width: 120 }}
          />
          <Button variant="contained" size="small" onClick={handleSubmit}>
            查询
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <AggregateSection data={data} loading={loading} />
      <GaugeSection data={data} loading={loading} />
      <StrikeSection data={data} loading={loading} />
      <TermSection data={data} loading={loading} />
      <GuideSection />
    </Box>
  );
}
