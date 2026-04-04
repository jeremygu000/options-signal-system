"use client";

import { useState, useCallback, useEffect, useRef } from "react";
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
import Autocomplete from "@mui/material/Autocomplete";
import CircularProgress from "@mui/material/CircularProgress";
import SectionHeader from "@/components/SectionHeader";
import { useThemeMode } from "@/components/ThemeProvider";
import { fetchFundamentalAnalysis, searchSymbols } from "@/lib/api";
import type { SymbolMeta } from "@/lib/types";
import type {
  FundamentalAnalysisResponse,
  ValuationMetrics,
  AnalystRating,
  PriceTarget,
  EarningsSurprise,
  UpgradeDowngrade,
  ShortInterest,
  IncomeHighlights,
} from "@/lib/types";

const GREEN = "#36bb80";
const RED = "#ff7134";
const BLUE = "#3b89ff";
const YELLOW = "#fdbc2a";

function fmtMoney(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function fmtLargeNumber(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}${(abs / 1e3).toFixed(2)}K`;
  return `${sign}${abs.toFixed(2)}`;
}

function fmtPct(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

function fmtNum(value: number, decimals = 2): string {
  return value.toFixed(decimals);
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

function recKeyColor(key: string): string {
  if (key === "strong_buy") return GREEN;
  if (key === "buy") return "#6dd9a8";
  if (key === "hold") return YELLOW;
  if (key === "sell") return "#ff9a5c";
  if (key === "strong_sell") return RED;
  return "text.primary";
}

interface ValuationSectionProps {
  data: FundamentalAnalysisResponse;
  loading: boolean;
}

function ValuationSection({ data, loading }: ValuationSectionProps) {
  const v: ValuationMetrics = data.valuation;

  const cards: { label: string; sublabel: string; value: string }[] = [
    {
      label: "市值",
      sublabel: "Market Cap",
      value: fmtLargeNumber(v.market_cap),
    },
    {
      label: "市盈率 (TTM)",
      sublabel: "Trailing P/E",
      value: v.trailing_pe ? fmtNum(v.trailing_pe) : "—",
    },
    {
      label: "市盈率 (Forward)",
      sublabel: "Forward P/E",
      value: v.forward_pe ? fmtNum(v.forward_pe) : "—",
    },
    {
      label: "每股收益 (TTM)",
      sublabel: "Trailing EPS",
      value: v.trailing_eps ? fmtNum(v.trailing_eps) : "—",
    },
    {
      label: "每股收益 (Forward)",
      sublabel: "Forward EPS",
      value: v.forward_eps ? fmtNum(v.forward_eps) : "—",
    },
    {
      label: "市净率",
      sublabel: "Price / Book",
      value: v.price_to_book ? fmtNum(v.price_to_book) : "—",
    },
    {
      label: "市销率",
      sublabel: "Price / Sales",
      value: v.price_to_sales ? fmtNum(v.price_to_sales) : "—",
    },
    {
      label: "PEG",
      sublabel: "PEG Ratio",
      value: v.peg_ratio ? fmtNum(v.peg_ratio) : "—",
    },
    {
      label: "企业价值",
      sublabel: "Enterprise Value",
      value: fmtLargeNumber(v.enterprise_value),
    },
    {
      label: "EV/EBITDA",
      sublabel: "EV / EBITDA",
      value: v.ev_to_ebitda ? fmtNum(v.ev_to_ebitda) : "—",
    },
    {
      label: "股息收益率",
      sublabel: "Dividend Yield",
      value: v.dividend_yield ? fmtPct(v.dividend_yield) : "—",
    },
    {
      label: "Beta",
      sublabel: "Beta",
      value: v.beta ? fmtNum(v.beta) : "—",
    },
  ];

  return (
    <Box component="section" id="valuation" sx={{ mb: 6 }}>
      <SectionHeader
        number="01"
        title="估值概览"
        subtitle="Valuation Overview"
      />

      <Box
        sx={{
          display: "flex",
          alignItems: "baseline",
          gap: 1.5,
          mb: 3,
          flexWrap: "wrap",
        }}
      >
        {loading ? (
          <Skeleton variant="text" width={120} height={44} />
        ) : (
          <>
            <Typography
              sx={{
                fontFamily: "var(--font-geist-mono)",
                fontWeight: 800,
                fontSize: "2rem",
                color: BLUE,
              }}
            >
              {fmtMoney(data.spot_price)}
            </Typography>
            <Typography variant="body2" sx={{ color: "text.secondary" }}>
              {data.currency}
            </Typography>
            <Chip
              label={data.symbol}
              size="small"
              sx={{
                bgcolor: "rgba(59,137,255,0.12)",
                color: BLUE,
                fontFamily: "var(--font-geist-mono)",
                fontWeight: 700,
              }}
            />
          </>
        )}
      </Box>

      <Grid container spacing={2}>
        {cards.map((c) => (
          <Grid key={c.sublabel} size={{ xs: 6, sm: 4, md: 3, lg: 2 }}>
            <StatCard
              label={c.label}
              sublabel={c.sublabel}
              value={c.value}
              loading={loading}
            />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}

interface AnalystRatingSectionProps {
  data: AnalystRating;
  loading: boolean;
}

function AnalystRatingSection({ data, loading }: AnalystRatingSectionProps) {
  const total = data.number_of_analysts || 1;
  const segments: {
    key: string;
    label: string;
    count: number;
    color: string;
  }[] = [
    {
      key: "strong_buy",
      label: "Strong Buy",
      count: data.strong_buy,
      color: GREEN,
    },
    { key: "buy", label: "Buy", count: data.buy, color: "#6dd9a8" },
    { key: "hold", label: "Hold", count: data.hold, color: YELLOW },
    { key: "sell", label: "Sell", count: data.sell, color: "#ff9a5c" },
    {
      key: "strong_sell",
      label: "Strong Sell",
      count: data.strong_sell,
      color: RED,
    },
  ];

  return (
    <Box component="section" id="analyst-ratings" sx={{ mb: 6 }}>
      <SectionHeader
        number="02"
        title="分析师评级"
        subtitle="Analyst Ratings"
      />

      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 2,
          mb: 3,
          flexWrap: "wrap",
        }}
      >
        {loading ? (
          <Skeleton variant="rounded" width={160} height={40} />
        ) : (
          <>
            <Chip
              label={data.recommendation_key.replace("_", " ").toUpperCase()}
              sx={{
                bgcolor: recKeyColor(data.recommendation_key),
                color: "#fff",
                fontWeight: 800,
                fontSize: "0.9rem",
                height: 40,
                px: 1,
                borderRadius: "8px",
              }}
            />
            <Box>
              <Typography
                variant="caption"
                sx={{ color: "text.secondary", display: "block" }}
              >
                Mean Score
              </Typography>
              <Typography
                sx={{
                  fontFamily: "var(--font-geist-mono)",
                  fontWeight: 700,
                  fontSize: "1.2rem",
                }}
              >
                {fmtNum(data.recommendation_mean)}
              </Typography>
            </Box>
            <Box>
              <Typography
                variant="caption"
                sx={{ color: "text.secondary", display: "block" }}
              >
                Analysts
              </Typography>
              <Typography
                sx={{
                  fontFamily: "var(--font-geist-mono)",
                  fontWeight: 700,
                  fontSize: "1.2rem",
                }}
              >
                {data.number_of_analysts}
              </Typography>
            </Box>
          </>
        )}
      </Box>

      {loading ? (
        <Skeleton variant="rounded" height={28} sx={{ borderRadius: 1 }} />
      ) : (
        <>
          <Box
            sx={{
              display: "flex",
              flexDirection: "row",
              height: 28,
              borderRadius: 1,
              overflow: "hidden",
              mb: 1,
            }}
          >
            {segments.map((seg) => {
              const pct = (seg.count / total) * 100;
              if (pct <= 0) return null;
              return (
                <Box
                  key={seg.key}
                  sx={{
                    width: `${pct}%`,
                    bgcolor: seg.color,
                    transition: "width 0.4s ease",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {pct > 8 && (
                    <Typography
                      sx={{
                        fontSize: "0.65rem",
                        fontWeight: 700,
                        color: "#fff",
                        lineHeight: 1,
                      }}
                    >
                      {seg.count}
                    </Typography>
                  )}
                </Box>
              );
            })}
          </Box>
          <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
            {segments.map((seg) => (
              <Box
                key={seg.key}
                sx={{ display: "flex", alignItems: "center", gap: 0.5 }}
              >
                <Box
                  sx={{
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    bgcolor: seg.color,
                  }}
                />
                <Typography variant="caption" sx={{ color: "text.secondary" }}>
                  {seg.label}{" "}
                  <strong style={{ color: seg.color }}>{seg.count}</strong>
                </Typography>
              </Box>
            ))}
          </Box>
        </>
      )}
    </Box>
  );
}

interface PriceTargetSectionProps {
  data: PriceTarget;
  spotPrice: number;
  loading: boolean;
}

function PriceTargetSection({
  data,
  spotPrice,
  loading,
}: PriceTargetSectionProps) {
  const range = data.high - data.low;
  const spotPct = range > 0 ? ((spotPrice - data.low) / range) * 100 : 50;
  const meanPct = range > 0 ? ((data.mean - data.low) / range) * 100 : 50;
  const clampedSpot = Math.max(0, Math.min(100, spotPct));
  const clampedMean = Math.max(0, Math.min(100, meanPct));

  return (
    <Box component="section" id="price-targets" sx={{ mb: 6 }}>
      <SectionHeader number="03" title="目标价" subtitle="Price Targets" />

      <Grid container spacing={2} sx={{ mb: 3 }}>
        {(
          [
            {
              label: "当前价",
              sublabel: "Current",
              value: fmtMoney(data.current),
            },
            {
              label: "目标低价",
              sublabel: "Low Target",
              value: fmtMoney(data.low),
            },
            {
              label: "目标均价",
              sublabel: "Mean Target",
              value: fmtMoney(data.mean),
            },
            {
              label: "目标中位数",
              sublabel: "Median Target",
              value: fmtMoney(data.median),
            },
            {
              label: "目标高价",
              sublabel: "High Target",
              value: fmtMoney(data.high),
            },
            {
              label: "分析师数",
              sublabel: "Analysts",
              value: String(data.number_of_analysts),
            },
          ] as { label: string; sublabel: string; value: string }[]
        ).map((c) => (
          <Grid key={c.sublabel} size={{ xs: 6, sm: 4, md: 2 }}>
            <StatCard
              label={c.label}
              sublabel={c.sublabel}
              value={c.value}
              loading={loading}
            />
          </Grid>
        ))}
      </Grid>

      {!loading && range > 0 && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="body2" sx={{ fontWeight: 700, mb: 2 }}>
              价格区间 · Price Range
            </Typography>
            <Box sx={{ position: "relative", height: 48 }}>
              <Box
                sx={{
                  position: "absolute",
                  top: "50%",
                  left: 0,
                  right: 0,
                  height: 8,
                  transform: "translateY(-50%)",
                  borderRadius: 1,
                  background: `linear-gradient(to right, ${RED}, ${YELLOW}, ${GREEN})`,
                }}
              />
              <Box
                sx={{
                  position: "absolute",
                  top: "50%",
                  left: `${clampedMean}%`,
                  transform: "translate(-50%, -50%)",
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  bgcolor: BLUE,
                  border: "2px solid #fff",
                  boxShadow: `0 0 0 2px ${BLUE}`,
                }}
              />
              <Box
                sx={{
                  position: "absolute",
                  top: "50%",
                  left: `${clampedSpot}%`,
                  transform: "translate(-50%, -50%)",
                  width: 18,
                  height: 18,
                  borderRadius: "50%",
                  bgcolor: YELLOW,
                  border: "2px solid #fff",
                  boxShadow: `0 0 0 2px ${YELLOW}`,
                }}
              />
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
                sx={{
                  fontFamily: "var(--font-geist-mono)",
                  color: RED,
                }}
              >
                Low {fmtMoney(data.low)}
              </Typography>
              <Box sx={{ display: "flex", gap: 2 }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                  <Box
                    sx={{
                      width: 10,
                      height: 10,
                      borderRadius: "50%",
                      bgcolor: YELLOW,
                    }}
                  />
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary" }}
                  >
                    Current {fmtMoney(spotPrice)}
                  </Typography>
                </Box>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                  <Box
                    sx={{
                      width: 10,
                      height: 10,
                      borderRadius: "50%",
                      bgcolor: BLUE,
                    }}
                  />
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary" }}
                  >
                    Mean {fmtMoney(data.mean)}
                  </Typography>
                </Box>
              </Box>
              <Typography
                variant="caption"
                sx={{
                  fontFamily: "var(--font-geist-mono)",
                  color: GREEN,
                }}
              >
                High {fmtMoney(data.high)}
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}

interface EarningsSurpriseSectionProps {
  data: EarningsSurprise[];
  nextEarningsDate: string | null;
  loading: boolean;
}

function EarningsSurpriseSection({
  data,
  nextEarningsDate,
  loading,
}: EarningsSurpriseSectionProps) {
  return (
    <Box component="section" id="earnings-surprises" sx={{ mb: 6 }}>
      <SectionHeader
        number="04"
        title="财报惊喜"
        subtitle="Earnings Surprises"
      />

      {nextEarningsDate && !loading && (
        <Box sx={{ mb: 2 }}>
          <Chip
            label={`下次财报: ${nextEarningsDate}`}
            size="small"
            sx={{
              bgcolor: "rgba(59,137,255,0.12)",
              color: BLUE,
              fontFamily: "var(--font-geist-mono)",
              fontWeight: 700,
            }}
          />
        </Box>
      )}

      {loading ? (
        <Box>
          {[1, 2, 3, 4].map((n) => (
            <Skeleton key={n} variant="rounded" height={44} sx={{ mb: 0.5 }} />
          ))}
        </Box>
      ) : data.length === 0 ? (
        <Alert severity="info">
          暂无财报惊喜数据 · No earnings data available
        </Alert>
      ) : (
        <Box sx={{ overflowX: "auto" }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>日期 Date</TableCell>
                <TableCell
                  align="right"
                  sx={{ fontWeight: 700, fontFamily: "var(--font-geist-mono)" }}
                >
                  EPS 预期
                </TableCell>
                <TableCell
                  align="right"
                  sx={{ fontWeight: 700, fontFamily: "var(--font-geist-mono)" }}
                >
                  EPS 实际
                </TableCell>
                <TableCell
                  align="right"
                  sx={{ fontWeight: 700, fontFamily: "var(--font-geist-mono)" }}
                >
                  惊喜 %
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.map((row: EarningsSurprise) => (
                <TableRow
                  key={row.date}
                  hover
                  sx={{ "&:last-child td": { border: 0 } }}
                >
                  <TableCell
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontSize: "0.8rem",
                    }}
                  >
                    {row.date}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontSize: "0.8rem",
                    }}
                  >
                    {fmtNum(row.eps_estimate)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontSize: "0.8rem",
                      color: row.eps_actual >= row.eps_estimate ? GREEN : RED,
                      fontWeight: 600,
                    }}
                  >
                    {fmtNum(row.eps_actual)}
                  </TableCell>
                  <TableCell align="right">
                    <Typography
                      variant="body2"
                      sx={{
                        fontFamily: "var(--font-geist-mono)",
                        fontSize: "0.8rem",
                        color: row.surprise_pct >= 0 ? GREEN : RED,
                        fontWeight: 700,
                      }}
                    >
                      {row.surprise_pct >= 0 ? "+" : ""}
                      {fmtNum(row.surprise_pct, 2)}%
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}
    </Box>
  );
}

interface UpgradeDowngradeSectionProps {
  data: UpgradeDowngrade[];
  loading: boolean;
}

function UpgradeDowngradeSection({
  data,
  loading,
}: UpgradeDowngradeSectionProps) {
  function actionColor(action: string): string {
    const lower = action.toLowerCase();
    if (lower.includes("upgrade") || lower === "up") return GREEN;
    if (lower.includes("downgrade") || lower === "down") return RED;
    return "text.primary";
  }

  return (
    <Box component="section" id="upgrades-downgrades" sx={{ mb: 6 }}>
      <SectionHeader
        number="05"
        title="评级变动"
        subtitle="Upgrades & Downgrades"
      />

      {loading ? (
        <Box>
          {[1, 2, 3, 4].map((n) => (
            <Skeleton key={n} variant="rounded" height={44} sx={{ mb: 0.5 }} />
          ))}
        </Box>
      ) : data.length === 0 ? (
        <Alert severity="info">
          暂无评级变动数据 · No upgrade/downgrade data available
        </Alert>
      ) : (
        <Box sx={{ overflowX: "auto" }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>日期 Date</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>机构 Firm</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>动作 Action</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>原评级 From</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>新评级 To</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.map((row: UpgradeDowngrade) => (
                <TableRow
                  key={`${row.date}-${row.firm}-${row.action}-${row.to_grade}`}
                  hover
                  sx={{ "&:last-child td": { border: 0 } }}
                >
                  <TableCell
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontSize: "0.8rem",
                    }}
                  >
                    {row.date}
                  </TableCell>
                  <TableCell sx={{ fontSize: "0.8rem" }}>{row.firm}</TableCell>
                  <TableCell>
                    <Typography
                      variant="body2"
                      sx={{
                        fontSize: "0.8rem",
                        fontWeight: 700,
                        color: actionColor(row.action),
                      }}
                    >
                      {row.action}
                    </Typography>
                  </TableCell>
                  <TableCell
                    sx={{ fontSize: "0.8rem", color: "text.secondary" }}
                  >
                    {row.from_grade || "—"}
                  </TableCell>
                  <TableCell sx={{ fontSize: "0.8rem", fontWeight: 600 }}>
                    {row.to_grade || "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}
    </Box>
  );
}

interface ShortInterestSectionProps {
  data: ShortInterest;
  loading: boolean;
}

function ShortInterestSection({ data, loading }: ShortInterestSectionProps) {
  return (
    <Box component="section" id="short-interest" sx={{ mb: 6 }}>
      <SectionHeader number="06" title="做空数据" subtitle="Short Interest" />
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 4 }}>
          <StatCard
            label="空头比率"
            sublabel="Short Ratio (Days to Cover)"
            value={data.short_ratio ? fmtNum(data.short_ratio) : "—"}
            loading={loading}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <StatCard
            label="空头占流通比"
            sublabel="Short % of Float"
            value={
              data.short_pct_of_float ? fmtPct(data.short_pct_of_float) : "—"
            }
            loading={loading}
            color={
              !loading && data.short_pct_of_float > 0.15
                ? RED
                : !loading && data.short_pct_of_float > 0.05
                  ? YELLOW
                  : undefined
            }
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <StatCard
            label="做空股数"
            sublabel="Shares Short"
            value={data.shares_short ? fmtLargeNumber(data.shares_short) : "—"}
            loading={loading}
          />
        </Grid>
      </Grid>
    </Box>
  );
}

interface IncomeSectionProps {
  data: IncomeHighlights;
  loading: boolean;
}

function IncomeSection({ data, loading }: IncomeSectionProps) {
  const cards: {
    label: string;
    sublabel: string;
    value: string;
    color?: string;
  }[] = [
    {
      label: "营收",
      sublabel: "Revenue",
      value: fmtLargeNumber(data.revenue),
    },
    {
      label: "营收增长",
      sublabel: "Revenue Growth",
      value: data.revenue_growth ? fmtPct(data.revenue_growth) : "—",
      color: data.revenue_growth >= 0 ? GREEN : RED,
    },
    {
      label: "毛利率",
      sublabel: "Gross Margin",
      value: data.gross_margin ? fmtPct(data.gross_margin) : "—",
      color:
        data.gross_margin >= 0.4
          ? GREEN
          : data.gross_margin < 0.2
            ? RED
            : undefined,
    },
    {
      label: "营业利润率",
      sublabel: "Operating Margin",
      value: data.operating_margin ? fmtPct(data.operating_margin) : "—",
      color: data.operating_margin >= 0 ? GREEN : RED,
    },
    {
      label: "净利润率",
      sublabel: "Profit Margin",
      value: data.profit_margin ? fmtPct(data.profit_margin) : "—",
      color: data.profit_margin >= 0 ? GREEN : RED,
    },
    {
      label: "盈利增长",
      sublabel: "Earnings Growth",
      value: data.earnings_growth ? fmtPct(data.earnings_growth) : "—",
      color: data.earnings_growth >= 0 ? GREEN : RED,
    },
  ];

  return (
    <Box component="section" id="income-highlights" sx={{ mb: 6 }}>
      <SectionHeader
        number="07"
        title="收入亮点"
        subtitle="Income Highlights"
      />
      <Grid container spacing={2}>
        {cards.map((c) => (
          <Grid key={c.sublabel} size={{ xs: 6, sm: 4, md: 2 }}>
            <StatCard
              label={c.label}
              sublabel={c.sublabel}
              value={c.value}
              color={c.color}
              loading={loading}
            />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}

export default function FundamentalsPage() {
  const { mode } = useThemeMode();
  const [symbolInput, setSymbolInput] = useState("AAPL");
  const [data, setData] = useState<FundamentalAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [options, setOptions] = useState<SymbolMeta[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleInputChange = useCallback(
    (_event: React.SyntheticEvent, value: string) => {
      const upper = value.toUpperCase();
      setSymbolInput(upper);

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

  const cardBg = mode === "dark" ? "#111827" : "#f9fafb";

  const handleFetch = useCallback(() => {
    const sym = symbolInput.trim().toUpperCase();
    if (!sym) return;
    setLoading(true);
    setError(null);
    fetchFundamentalAnalysis(sym)
      .then((res) => {
        if (res.error) {
          setError(res.error);
        }
        setData(res);
      })
      .catch((e: unknown) =>
        setError(
          e instanceof Error ? e.message : "Failed to load fundamentals",
        ),
      )
      .finally(() => setLoading(false));
  }, [symbolInput]);

  const empty: FundamentalAnalysisResponse = {
    symbol: "",
    spot_price: 0,
    currency: "USD",
    valuation: {
      market_cap: 0,
      trailing_pe: 0,
      forward_pe: 0,
      trailing_eps: 0,
      forward_eps: 0,
      price_to_book: 0,
      price_to_sales: 0,
      peg_ratio: 0,
      enterprise_value: 0,
      ev_to_ebitda: 0,
      dividend_yield: 0,
      beta: 0,
    },
    analyst_rating: {
      recommendation_key: "hold",
      recommendation_mean: 0,
      strong_buy: 0,
      buy: 0,
      hold: 0,
      sell: 0,
      strong_sell: 0,
      number_of_analysts: 0,
    },
    price_target: {
      current: 0,
      low: 0,
      high: 0,
      mean: 0,
      median: 0,
      number_of_analysts: 0,
    },
    short_interest: {
      short_ratio: 0,
      short_pct_of_float: 0,
      shares_short: 0,
    },
    income: {
      revenue: 0,
      revenue_growth: 0,
      gross_margin: 0,
      operating_margin: 0,
      profit_margin: 0,
      earnings_growth: 0,
    },
    earnings_surprises: [],
    upgrades_downgrades: [],
    next_earnings_date: null,
    error: null,
  };

  const displayData = data ?? empty;

  return (
    <Box sx={{ px: 4, py: 3, maxWidth: 1600, mx: "auto" }}>
      <Box sx={{ mb: 3 }}>
        <Typography
          variant="h5"
          sx={{ fontWeight: 800, fontSize: "1.4rem", mb: 0.25 }}
        >
          基本面分析
        </Typography>
        <Typography variant="body2" sx={{ color: "text.secondary" }}>
          Fundamentals Analysis
        </Typography>
      </Box>

      <Card sx={{ mb: 4, bgcolor: cardBg }}>
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
              inputValue={symbolInput}
              onInputChange={handleInputChange}
              onChange={(_event, value) => {
                if (value && typeof value !== "string") {
                  setSymbolInput(value.symbol);
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
                      handleFetch();
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
              onClick={handleFetch}
              disabled={loading || !symbolInput.trim()}
              sx={{
                bgcolor: BLUE,
                fontWeight: 700,
                "&:hover": { bgcolor: "#2a6fd4" },
              }}
            >
              {loading ? "加载中..." : "查询"}
            </Button>
          </Box>
        </CardContent>
      </Card>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {!data && !loading && (
        <Box
          sx={{
            textAlign: "center",
            py: 8,
            color: "text.secondary",
          }}
        >
          <Typography
            variant="body1"
            sx={{ fontFamily: "var(--font-geist-mono)" }}
          >
            输入标的代码并点击查询 · Enter a symbol and click 查询
          </Typography>
        </Box>
      )}

      {(data || loading) && (
        <>
          <ValuationSection data={displayData} loading={loading} />
          <AnalystRatingSection
            data={displayData.analyst_rating}
            loading={loading}
          />
          <PriceTargetSection
            data={displayData.price_target}
            spotPrice={displayData.spot_price}
            loading={loading}
          />
          <EarningsSurpriseSection
            data={displayData.earnings_surprises}
            nextEarningsDate={displayData.next_earnings_date}
            loading={loading}
          />
          <UpgradeDowngradeSection
            data={displayData.upgrades_downgrades}
            loading={loading}
          />
          <ShortInterestSection
            data={displayData.short_interest}
            loading={loading}
          />
          <IncomeSection data={displayData.income} loading={loading} />
        </>
      )}
    </Box>
  );
}
