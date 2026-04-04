"use client";

import { useState, useEffect, useCallback } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import Skeleton from "@mui/material/Skeleton";
import Alert from "@mui/material/Alert";
import Grid from "@mui/material/Grid";
import TextField from "@mui/material/TextField";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import IconButton from "@mui/material/IconButton";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogActions from "@mui/material/DialogActions";
import DialogContentText from "@mui/material/DialogContentText";
import Table from "@mui/material/Table";
import TableHead from "@mui/material/TableHead";
import TableBody from "@mui/material/TableBody";
import TableRow from "@mui/material/TableRow";
import TableCell from "@mui/material/TableCell";
import Chip from "@mui/material/Chip";
import Accordion from "@mui/material/Accordion";
import AccordionSummary from "@mui/material/AccordionSummary";
import AccordionDetails from "@mui/material/AccordionDetails";
import Tooltip from "@mui/material/Tooltip";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import RefreshIcon from "@mui/icons-material/Refresh";
import SectionHeader from "@/components/SectionHeader";
import { useThemeMode } from "@/components/ThemeProvider";
import {
  createPosition,
  fetchPositions,
  updatePosition,
  closePosition,
  deletePosition,
  fetchPortfolioSummary,
  fetchPortfolioStrategies,
  fetchExpiringPositions,
  batchMarkExpired,
} from "@/lib/api";
import type {
  PositionCreate,
  PositionUpdate,
  PositionClose,
  PositionResponse,
  PortfolioSummaryResponse,
  StrategyGroupResponse,
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

function fmtGreek(value: number): string {
  return value.toFixed(4);
}

function daysUntil(dateStr: string): number {
  const now = new Date();
  const exp = new Date(dateStr);
  const diff = exp.getTime() - now.getTime();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function pnlColor(value: number): string {
  if (value > 0) return GREEN;
  if (value < 0) return RED;
  return "text.primary";
}

function statusChipColor(
  status: "open" | "closed" | "expired",
): "success" | "default" | "warning" {
  if (status === "open") return "success";
  if (status === "expired") return "warning";
  return "default";
}

interface SummaryCardProps {
  label: string;
  sublabel: string;
  value: string;
  sub?: string;
  color?: string;
  loading?: boolean;
}

function SummaryCard({
  label,
  sublabel,
  value,
  sub,
  color,
  loading,
}: SummaryCardProps) {
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
              fontSize: "1.25rem",
              color: color ?? "text.primary",
            }}
          >
            {value}
          </Typography>
        )}
        {sub && !loading && (
          <Typography
            variant="caption"
            sx={{ color: "text.secondary", fontFamily: "var(--font-geist-mono)" }}
          >
            {sub}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

interface GreekCardProps {
  label: string;
  sublabel: string;
  value: number;
  loading?: boolean;
}

function GreekCard({ label, sublabel, value, loading }: GreekCardProps) {
  const color =
    label === "Theta"
      ? value < 0
        ? RED
        : GREEN
      : label === "Delta"
        ? value > 0
          ? GREEN
          : value < 0
            ? RED
            : "text.primary"
        : "text.primary";

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
          <Skeleton variant="text" width={60} height={32} />
        ) : (
          <Typography
            variant="h6"
            sx={{
              fontFamily: "var(--font-geist-mono)",
              fontWeight: 700,
              fontSize: "1.1rem",
              color,
            }}
          >
            {fmtGreek(value)}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

const EMPTY_CREATE: PositionCreate = {
  symbol: "",
  option_type: "call",
  strike: 0,
  expiration: "",
  quantity: 1,
  entry_price: 0,
  entry_date: "",
  entry_commission: 0,
  strategy_name: "",
  tags: "",
  notes: "",
};

const EMPTY_CLOSE: PositionClose = {
  exit_price: 0,
  exit_commission: 0,
  exit_date: "",
};

export default function PositionsPage() {
  const { mode } = useThemeMode();

  const [summary, setSummary] = useState<PortfolioSummaryResponse | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const [positions, setPositions] = useState<PositionResponse[]>([]);
  const [positionsLoading, setPositionsLoading] = useState(true);
  const [positionsError, setPositionsError] = useState<string | null>(null);

  const [strategies, setStrategies] = useState<StrategyGroupResponse[]>([]);
  const [strategiesLoading, setStrategiesLoading] = useState(true);

  const [expiring, setExpiring] = useState<PositionResponse[]>([]);
  const [expiringLoading, setExpiringLoading] = useState(true);

  const [filterStatus, setFilterStatus] = useState<string>("open");
  const [filterSymbol, setFilterSymbol] = useState<string>("");
  const [filterStrategy, setFilterStrategy] = useState<string>("");

  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [createForm, setCreateForm] = useState<PositionCreate>(EMPTY_CREATE);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [closeDialogOpen, setCloseDialogOpen] = useState(false);
  const [closeTarget, setCloseTarget] = useState<PositionResponse | null>(null);
  const [closeForm, setCloseForm] = useState<PositionClose>(EMPTY_CLOSE);
  const [closeLoading, setCloseLoading] = useState(false);
  const [closeError, setCloseError] = useState<string | null>(null);

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<PositionResponse | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<PositionResponse | null>(null);
  const [editForm, setEditForm] = useState<PositionUpdate>({});
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const [batchLoading, setBatchLoading] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const loadSummary = useCallback(() => {
    setSummaryLoading(true);
    setSummaryError(null);
    fetchPortfolioSummary()
      .then(setSummary)
      .catch((e: unknown) =>
        setSummaryError(e instanceof Error ? e.message : "Failed to load summary"),
      )
      .finally(() => setSummaryLoading(false));
  }, []);

  const loadPositions = useCallback(() => {
    setPositionsLoading(true);
    setPositionsError(null);
    const params: { status?: string; symbol?: string; strategy?: string } = {};
    if (filterStatus && filterStatus !== "all") params.status = filterStatus;
    if (filterSymbol.trim()) params.symbol = filterSymbol.trim().toUpperCase();
    if (filterStrategy.trim()) params.strategy = filterStrategy.trim();
    fetchPositions(params)
      .then(setPositions)
      .catch((e: unknown) =>
        setPositionsError(e instanceof Error ? e.message : "Failed to load positions"),
      )
      .finally(() => setPositionsLoading(false));
  }, [filterStatus, filterSymbol, filterStrategy]);

  const loadStrategies = useCallback(() => {
    setStrategiesLoading(true);
    fetchPortfolioStrategies()
      .then(setStrategies)
      .catch(() => setStrategies([]))
      .finally(() => setStrategiesLoading(false));
  }, []);

  const loadExpiring = useCallback(() => {
    setExpiringLoading(true);
    fetchExpiringPositions(7)
      .then(setExpiring)
      .catch(() => setExpiring([]))
      .finally(() => setExpiringLoading(false));
  }, []);

  const refreshAll = useCallback(() => {
    loadSummary();
    loadPositions();
    loadStrategies();
    loadExpiring();
  }, [loadSummary, loadPositions, loadStrategies, loadExpiring]);

  useEffect(() => {
    loadSummary();
    loadStrategies();
    loadExpiring();
  }, [loadSummary, loadStrategies, loadExpiring]);

  useEffect(() => {
    loadPositions();
  }, [loadPositions]);

  function handleCreateSubmit() {
    setCreateLoading(true);
    setCreateError(null);
    const payload: PositionCreate = {
      ...createForm,
      symbol: createForm.symbol.trim().toUpperCase(),
      entry_date: createForm.entry_date || undefined,
      strategy_name: createForm.strategy_name || undefined,
      tags: createForm.tags || undefined,
      notes: createForm.notes || undefined,
    };
    createPosition(payload)
      .then(() => {
        setAddDialogOpen(false);
        setCreateForm(EMPTY_CREATE);
        refreshAll();
      })
      .catch((e: unknown) =>
        setCreateError(e instanceof Error ? e.message : "Failed to create position"),
      )
      .finally(() => setCreateLoading(false));
  }

  function handleCloseSubmit() {
    if (!closeTarget) return;
    setCloseLoading(true);
    setCloseError(null);
    const payload: PositionClose = {
      exit_price: closeForm.exit_price,
      exit_commission: closeForm.exit_commission || undefined,
      exit_date: closeForm.exit_date || undefined,
    };
    closePosition(closeTarget.id, payload)
      .then(() => {
        setCloseDialogOpen(false);
        setCloseTarget(null);
        setCloseForm(EMPTY_CLOSE);
        refreshAll();
      })
      .catch((e: unknown) =>
        setCloseError(e instanceof Error ? e.message : "Failed to close position"),
      )
      .finally(() => setCloseLoading(false));
  }

  function handleDeleteConfirm() {
    if (!deleteTarget) return;
    setDeleteLoading(true);
    deletePosition(deleteTarget.id)
      .then(() => {
        setDeleteDialogOpen(false);
        setDeleteTarget(null);
        refreshAll();
      })
      .catch((e: unknown) =>
        setGlobalError(e instanceof Error ? e.message : "Failed to delete position"),
      )
      .finally(() => setDeleteLoading(false));
  }

  function handleEditSubmit() {
    if (!editTarget) return;
    setEditLoading(true);
    setEditError(null);
    updatePosition(editTarget.id, editForm)
      .then(() => {
        setEditDialogOpen(false);
        setEditTarget(null);
        setEditForm({});
        refreshAll();
      })
      .catch((e: unknown) =>
        setEditError(e instanceof Error ? e.message : "Failed to update position"),
      )
      .finally(() => setEditLoading(false));
  }

  function handleBatchMarkExpired() {
    setBatchLoading(true);
    batchMarkExpired()
      .then((res) => {
        setGlobalError(null);
        if (res.marked_expired > 0) refreshAll();
      })
      .catch((e: unknown) =>
        setGlobalError(e instanceof Error ? e.message : "Failed to mark expired"),
      )
      .finally(() => setBatchLoading(false));
  }

  function openCloseDialog(pos: PositionResponse) {
    setCloseTarget(pos);
    setCloseForm(EMPTY_CLOSE);
    setCloseError(null);
    setCloseDialogOpen(true);
  }

  function openDeleteDialog(pos: PositionResponse) {
    setDeleteTarget(pos);
    setDeleteDialogOpen(true);
  }

  function openEditDialog(pos: PositionResponse) {
    setEditTarget(pos);
    setEditForm({
      notes: pos.notes,
      tags: pos.tags,
      strategy_name: pos.strategy_name ?? "",
      entry_price: pos.entry_price,
      entry_commission: pos.entry_commission,
      quantity: pos.quantity,
    });
    setEditError(null);
    setEditDialogOpen(true);
  }

  const cardBg = mode === "dark" ? "#111827" : "#f9fafb";

  return (
    <Box sx={{ px: 4, py: 3, maxWidth: 1600, mx: "auto" }}>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          mb: 3,
        }}
      >
        <Box>
          <Typography
            variant="h5"
            sx={{ fontWeight: 800, fontSize: "1.4rem", mb: 0.25 }}
          >
            持仓管理
          </Typography>
          <Typography variant="body2" sx={{ color: "text.secondary" }}>
            Position Management
          </Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 1 }}>
          <Tooltip title="批量标记到期 / Batch mark expired" arrow>
            <span>
              <Button
                variant="outlined"
                size="small"
                onClick={handleBatchMarkExpired}
                disabled={batchLoading}
                sx={{ fontSize: "0.75rem" }}
              >
                {batchLoading ? "处理中..." : "标记到期"}
              </Button>
            </span>
          </Tooltip>
          <Tooltip title="刷新数据 / Refresh all" arrow>
            <IconButton onClick={refreshAll} size="small">
              <RefreshIcon sx={{ fontSize: "1.1rem" }} />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            size="small"
            onClick={() => {
              setCreateForm(EMPTY_CREATE);
              setCreateError(null);
              setAddDialogOpen(true);
            }}
            sx={{ bgcolor: BLUE, "&:hover": { bgcolor: "#2a6fd4" } }}
          >
            新增持仓
          </Button>
        </Box>
      </Box>

      {globalError && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setGlobalError(null)}>
          {globalError}
        </Alert>
      )}

      <Box component="section" id="portfolio-summary" sx={{ mb: 6 }}>
        <SectionHeader number="01" title="总览" subtitle="Portfolio Summary" />
        {summaryError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {summaryError}
          </Alert>
        )}
        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <SummaryCard
              label="总持仓数"
              sublabel="Total Positions"
              value={summary ? String(summary.total_positions) : "—"}
              sub={
                summary
                  ? `开仓 ${summary.open_positions} · 已平 ${summary.closed_positions} · 到期 ${summary.expired_positions}`
                  : undefined
              }
              loading={summaryLoading}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <SummaryCard
              label="未实现盈亏"
              sublabel="Unrealized P&L"
              value={summary ? fmtMoney(summary.total_unrealized_pnl) : "—"}
              color={
                summary
                  ? summary.total_unrealized_pnl >= 0
                    ? GREEN
                    : RED
                  : undefined
              }
              loading={summaryLoading}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <SummaryCard
              label="已实现盈亏"
              sublabel="Realized P&L"
              value={summary ? fmtMoney(summary.total_realized_pnl) : "—"}
              color={
                summary
                  ? summary.total_realized_pnl >= 0
                    ? GREEN
                    : RED
                  : undefined
              }
              loading={summaryLoading}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <SummaryCard
              label="总成本"
              sublabel="Total Cost"
              value={summary ? fmtMoney(summary.total_cost) : "—"}
              loading={summaryLoading}
            />
          </Grid>
        </Grid>
      </Box>

      <Box component="section" id="portfolio-greeks" sx={{ mb: 6 }}>
        <SectionHeader
          number="02"
          title="组合希腊值"
          subtitle="Portfolio Greeks"
        />
        <Grid container spacing={2}>
          {(["Delta", "Gamma", "Theta", "Vega", "Rho"] as const).map((g) => {
            const key = g.toLowerCase() as "delta" | "gamma" | "theta" | "vega" | "rho";
            return (
              <Grid key={g} size={{ xs: 6, sm: 4, md: 2.4 }}>
                <GreekCard
                  label={g}
                  sublabel={g}
                  value={summary ? summary.greeks[key] : 0}
                  loading={summaryLoading}
                />
              </Grid>
            );
          })}
        </Grid>
      </Box>

      <Box component="section" id="expiration-alerts" sx={{ mb: 6 }}>
        <SectionHeader
          number="03"
          title="到期预警"
          subtitle="Expiration Alerts (7 days)"
        />
        {expiringLoading ? (
          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
            {["a", "b", "c"].map((k) => (
              <Skeleton key={k} variant="rounded" width={200} height={72} />
            ))}
          </Box>
        ) : expiring.length === 0 ? (
          <Card sx={{ bgcolor: cardBg }}>
            <CardContent>
              <Typography variant="body2" sx={{ color: "text.secondary" }}>
                无到期预警 / No upcoming expirations within 7 days
              </Typography>
            </CardContent>
          </Card>
        ) : (
          <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap" }}>
            {expiring.map((pos) => {
              const days = daysUntil(pos.expiration);
              const alertColor = days <= 3 ? RED : YELLOW;
              return (
                <Card
                  key={pos.id}
                  sx={{
                    borderLeft: `3px solid ${alertColor}`,
                    minWidth: 180,
                  }}
                >
                  <CardContent sx={{ pb: "12px !important", pt: "12px !important" }}>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                        mb: 0.5,
                      }}
                    >
                      <Typography
                        sx={{
                          fontFamily: "var(--font-geist-mono)",
                          fontWeight: 700,
                          fontSize: "0.9rem",
                        }}
                      >
                        {pos.symbol}
                      </Typography>
                      <Chip
                        label={pos.option_type.toUpperCase()}
                        size="small"
                        sx={{
                          height: 18,
                          fontSize: "0.6rem",
                          bgcolor:
                            pos.option_type === "call"
                              ? "rgba(59,137,255,0.15)"
                              : "rgba(255,113,52,0.15)",
                          color:
                            pos.option_type === "call" ? BLUE : RED,
                        }}
                      />
                    </Box>
                    <Typography
                      variant="caption"
                      sx={{
                        fontFamily: "var(--font-geist-mono)",
                        color: "text.secondary",
                        display: "block",
                      }}
                    >
                      ${pos.strike} · {pos.expiration}
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{
                        fontFamily: "var(--font-geist-mono)",
                        color: alertColor,
                        fontWeight: 700,
                      }}
                    >
                      {days <= 0 ? "今日到期" : `${days}天后到期`}
                    </Typography>
                  </CardContent>
                </Card>
              );
            })}
          </Box>
        )}
      </Box>

      <Box component="section" id="positions-table" sx={{ mb: 6 }}>
        <SectionHeader number="04" title="持仓列表" subtitle="Positions" />

        <Box sx={{ display: "flex", gap: 1.5, mb: 2, flexWrap: "wrap" }}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>状态 Status</InputLabel>
            <Select
              value={filterStatus}
              label="状态 Status"
              onChange={(e) => setFilterStatus(e.target.value)}
            >
              <MenuItem value="all">全部 All</MenuItem>
              <MenuItem value="open">开仓 Open</MenuItem>
              <MenuItem value="closed">已平 Closed</MenuItem>
              <MenuItem value="expired">到期 Expired</MenuItem>
            </Select>
          </FormControl>
          <TextField
            size="small"
            label="标的 Symbol"
            value={filterSymbol}
            onChange={(e) => setFilterSymbol(e.target.value)}
            sx={{ width: 120 }}
          />
          <TextField
            size="small"
            label="策略 Strategy"
            value={filterStrategy}
            onChange={(e) => setFilterStrategy(e.target.value)}
            sx={{ width: 160 }}
          />
          <Button
            variant="outlined"
            size="small"
            onClick={loadPositions}
            sx={{ alignSelf: "center" }}
          >
            查询
          </Button>
        </Box>

        {positionsError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {positionsError}
          </Alert>
        )}

        {positionsLoading ? (
          <Box>
            {[1, 2, 3, 4].map((n) => (
              <Skeleton key={n} variant="rounded" height={44} sx={{ mb: 0.5 }} />
            ))}
          </Box>
        ) : positions.length === 0 ? (
          <Card sx={{ bgcolor: cardBg }}>
            <CardContent>
              <Typography variant="body2" sx={{ color: "text.secondary" }}>
                暂无持仓记录 / No positions found
              </Typography>
            </CardContent>
          </Card>
        ) : (
          <Box sx={{ overflowX: "auto" }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700, whiteSpace: "nowrap" }}>
                    标的 Symbol
                  </TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>类型 Type</TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontWeight: 700, fontFamily: "var(--font-geist-mono)" }}
                  >
                    行权价 Strike
                  </TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>到期日 Expiration</TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontWeight: 700, fontFamily: "var(--font-geist-mono)" }}
                  >
                    数量 Qty
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontWeight: 700, fontFamily: "var(--font-geist-mono)" }}
                  >
                    开仓价 Entry
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{ fontWeight: 700, fontFamily: "var(--font-geist-mono)" }}
                  >
                    盈亏 P&L
                  </TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>状态 Status</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>策略</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    操作
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {positions.map((pos) => {
                  const pnl =
                    pos.status === "open"
                      ? pos.unrealized_pnl
                      : pos.realized_pnl;
                  return (
                    <TableRow
                      key={pos.id}
                      hover
                      sx={{
                        "&:last-child td": { border: 0 },
                      }}
                    >
                      <TableCell
                        sx={{
                          fontFamily: "var(--font-geist-mono)",
                          fontWeight: 700,
                        }}
                      >
                        {pos.symbol}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={pos.option_type.toUpperCase()}
                          size="small"
                          sx={{
                            height: 20,
                            fontSize: "0.65rem",
                            bgcolor:
                              pos.option_type === "call"
                                ? "rgba(59,137,255,0.12)"
                                : "rgba(255,113,52,0.12)",
                            color:
                              pos.option_type === "call" ? BLUE : RED,
                          }}
                        />
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontFamily: "var(--font-geist-mono)" }}
                      >
                        ${pos.strike}
                      </TableCell>
                      <TableCell
                        sx={{ fontFamily: "var(--font-geist-mono)", fontSize: "0.8rem" }}
                      >
                        {pos.expiration}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          fontFamily: "var(--font-geist-mono)",
                          color: pos.quantity > 0 ? GREEN : RED,
                          fontWeight: 600,
                        }}
                      >
                        {pos.quantity > 0 ? "+" : ""}
                        {pos.quantity}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontFamily: "var(--font-geist-mono)" }}
                      >
                        ${pos.entry_price.toFixed(2)}
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          variant="body2"
                          sx={{
                            fontFamily: "var(--font-geist-mono)",
                            color: pnl != null ? pnlColor(pnl) : "text.secondary",
                            fontWeight: pnl != null ? 600 : 400,
                          }}
                        >
                          {pnl != null
                            ? `${pnl >= 0 ? "+" : ""}${fmtMoney(pnl)}`
                            : "—"}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={
                            pos.status === "open"
                              ? "开仓"
                              : pos.status === "closed"
                                ? "已平"
                                : "到期"
                          }
                          size="small"
                          color={statusChipColor(pos.status)}
                          sx={{ height: 20, fontSize: "0.65rem" }}
                        />
                      </TableCell>
                      <TableCell
                        sx={{ fontSize: "0.75rem", color: "text.secondary" }}
                      >
                        {pos.strategy_name ?? "—"}
                      </TableCell>
                      <TableCell align="right">
                        <Box
                          sx={{
                            display: "flex",
                            gap: 0.25,
                            justifyContent: "flex-end",
                          }}
                        >
                          <Tooltip title="编辑 Edit" arrow>
                            <IconButton
                              size="small"
                              onClick={() => openEditDialog(pos)}
                              sx={{ color: "text.secondary" }}
                            >
                              <EditOutlinedIcon sx={{ fontSize: "0.9rem" }} />
                            </IconButton>
                          </Tooltip>
                          {pos.status === "open" && (
                            <Tooltip title="平仓 Close" arrow>
                              <IconButton
                                size="small"
                                onClick={() => openCloseDialog(pos)}
                                sx={{ color: GREEN }}
                              >
                                <CloseIcon sx={{ fontSize: "0.9rem" }} />
                              </IconButton>
                            </Tooltip>
                          )}
                          <Tooltip title="删除 Delete" arrow>
                            <IconButton
                              size="small"
                              onClick={() => openDeleteDialog(pos)}
                              sx={{ color: RED }}
                            >
                              <DeleteOutlineIcon sx={{ fontSize: "0.9rem" }} />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Box>
        )}
      </Box>

      <Box component="section" id="strategy-groups" sx={{ mb: 6 }}>
        <SectionHeader number="05" title="策略分组" subtitle="Strategy Groups" />
        {strategiesLoading ? (
          <Box>
            {[1, 2].map((n) => (
              <Skeleton key={n} variant="rounded" height={56} sx={{ mb: 1 }} />
            ))}
          </Box>
        ) : strategies.length === 0 ? (
          <Card sx={{ bgcolor: cardBg }}>
            <CardContent>
              <Typography variant="body2" sx={{ color: "text.secondary" }}>
                暂无策略分组 / No strategy groups found
              </Typography>
            </CardContent>
          </Card>
        ) : (
          <Box>
            {strategies.map((group) => (
              <Accordion
                key={group.strategy_name}
                disableGutters
                sx={{ mb: 1, "&:before": { display: "none" } }}
              >
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 2,
                      flex: 1,
                      flexWrap: "wrap",
                    }}
                  >
                    <Typography sx={{ fontWeight: 700, minWidth: 120 }}>
                      {group.strategy_name || "未命名策略"}
                    </Typography>
                    <Box sx={{ display: "flex", gap: 1.5 }}>
                      <Typography variant="caption" sx={{ color: "text.secondary" }}>
                        持仓{" "}
                        <strong style={{ color: "inherit" }}>
                          {group.position_count}
                        </strong>
                      </Typography>
                      <Typography variant="caption" sx={{ color: "text.secondary" }}>
                        开仓{" "}
                        <strong style={{ color: GREEN }}>{group.open_count}</strong>
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{
                          fontFamily: "var(--font-geist-mono)",
                          color:
                            group.total_realized_pnl >= 0 ? GREEN : RED,
                          fontWeight: 700,
                        }}
                      >
                        {group.total_realized_pnl >= 0 ? "+" : ""}
                        {fmtMoney(group.total_realized_pnl)}
                      </Typography>
                    </Box>
                  </Box>
                </AccordionSummary>
                <AccordionDetails sx={{ p: 0 }}>
                  <Divider />
                  <Box sx={{ overflowX: "auto" }}>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell sx={{ fontWeight: 700, fontSize: "0.75rem" }}>
                            Symbol
                          </TableCell>
                          <TableCell sx={{ fontWeight: 700, fontSize: "0.75rem" }}>
                            Type
                          </TableCell>
                          <TableCell
                            align="right"
                            sx={{ fontWeight: 700, fontSize: "0.75rem" }}
                          >
                            Strike
                          </TableCell>
                          <TableCell sx={{ fontWeight: 700, fontSize: "0.75rem" }}>
                            Expiration
                          </TableCell>
                          <TableCell
                            align="right"
                            sx={{ fontWeight: 700, fontSize: "0.75rem" }}
                          >
                            Qty
                          </TableCell>
                          <TableCell sx={{ fontWeight: 700, fontSize: "0.75rem" }}>
                            Status
                          </TableCell>
                          <TableCell
                            align="right"
                            sx={{ fontWeight: 700, fontSize: "0.75rem" }}
                          >
                            P&L
                          </TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {group.positions.map((pos) => {
                          const pnl =
                            pos.status === "open"
                              ? pos.unrealized_pnl
                              : pos.realized_pnl;
                          return (
                            <TableRow key={pos.id} hover>
                              <TableCell
                                sx={{
                                  fontFamily: "var(--font-geist-mono)",
                                  fontWeight: 600,
                                  fontSize: "0.8rem",
                                }}
                              >
                                {pos.symbol}
                              </TableCell>
                              <TableCell sx={{ fontSize: "0.8rem" }}>
                                {pos.option_type.toUpperCase()}
                              </TableCell>
                              <TableCell
                                align="right"
                                sx={{
                                  fontFamily: "var(--font-geist-mono)",
                                  fontSize: "0.8rem",
                                }}
                              >
                                ${pos.strike}
                              </TableCell>
                              <TableCell
                                sx={{
                                  fontFamily: "var(--font-geist-mono)",
                                  fontSize: "0.8rem",
                                }}
                              >
                                {pos.expiration}
                              </TableCell>
                              <TableCell
                                align="right"
                                sx={{
                                  fontFamily: "var(--font-geist-mono)",
                                  fontSize: "0.8rem",
                                  color: pos.quantity > 0 ? GREEN : RED,
                                }}
                              >
                                {pos.quantity > 0 ? "+" : ""}
                                {pos.quantity}
                              </TableCell>
                              <TableCell sx={{ fontSize: "0.8rem" }}>
                                <Chip
                                  label={
                                    pos.status === "open"
                                      ? "开仓"
                                      : pos.status === "closed"
                                        ? "已平"
                                        : "到期"
                                  }
                                  size="small"
                                  color={statusChipColor(pos.status)}
                                  sx={{ height: 18, fontSize: "0.6rem" }}
                                />
                              </TableCell>
                              <TableCell align="right">
                                <Typography
                                  variant="caption"
                                  sx={{
                                    fontFamily: "var(--font-geist-mono)",
                                    color:
                                      pnl != null
                                        ? pnlColor(pnl)
                                        : "text.secondary",
                                    fontWeight: pnl != null ? 600 : 400,
                                  }}
                                >
                                  {pnl != null
                                    ? `${pnl >= 0 ? "+" : ""}${fmtMoney(pnl)}`
                                    : "—"}
                                </Typography>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </Box>
                </AccordionDetails>
              </Accordion>
            ))}
          </Box>
        )}
      </Box>

      <Dialog
        open={addDialogOpen}
        onClose={() => setAddDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700 }}>
          新增持仓
          <Typography variant="caption" sx={{ ml: 1, color: "text.secondary" }}>
            Add Position
          </Typography>
        </DialogTitle>
        <DialogContent dividers>
          {createError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {createError}
            </Alert>
          )}
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                size="small"
                label="标的 Symbol"
                required
                value={createForm.symbol}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, symbol: e.target.value }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControl fullWidth size="small">
                <InputLabel>类型 Type</InputLabel>
                <Select
                  value={createForm.option_type}
                  label="类型 Type"
                  onChange={(e) =>
                    setCreateForm((f) => ({
                      ...f,
                      option_type: e.target.value as "call" | "put",
                    }))
                  }
                >
                  <MenuItem value="call">Call</MenuItem>
                  <MenuItem value="put">Put</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                size="small"
                label="行权价 Strike"
                type="number"
                required
                value={createForm.strike || ""}
                onChange={(e) =>
                  setCreateForm((f) => ({
                    ...f,
                    strike: parseFloat(e.target.value) || 0,
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                size="small"
                label="到期日 Expiration (YYYY-MM-DD)"
                required
                value={createForm.expiration}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, expiration: e.target.value }))
                }
                placeholder="2026-06-20"
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                size="small"
                label="数量 Quantity (+ long / - short)"
                type="number"
                required
                value={createForm.quantity || ""}
                onChange={(e) =>
                  setCreateForm((f) => ({
                    ...f,
                    quantity: parseInt(e.target.value, 10) || 0,
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                size="small"
                label="开仓价 Entry Price"
                type="number"
                required
                value={createForm.entry_price || ""}
                onChange={(e) =>
                  setCreateForm((f) => ({
                    ...f,
                    entry_price: parseFloat(e.target.value) || 0,
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                size="small"
                label="开仓日期 Entry Date (optional)"
                value={createForm.entry_date ?? ""}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, entry_date: e.target.value }))
                }
                placeholder="2026-04-01"
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                size="small"
                label="手续费 Commission (optional)"
                type="number"
                value={createForm.entry_commission ?? ""}
                onChange={(e) =>
                  setCreateForm((f) => ({
                    ...f,
                    entry_commission: parseFloat(e.target.value) || 0,
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <TextField
                fullWidth
                size="small"
                label="策略名称 Strategy Name (optional)"
                value={createForm.strategy_name ?? ""}
                onChange={(e) =>
                  setCreateForm((f) => ({
                    ...f,
                    strategy_name: e.target.value,
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <TextField
                fullWidth
                size="small"
                label="标签 Tags (optional)"
                value={createForm.tags ?? ""}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, tags: e.target.value }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <TextField
                fullWidth
                size="small"
                multiline
                rows={2}
                label="备注 Notes (optional)"
                value={createForm.notes ?? ""}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, notes: e.target.value }))
                }
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setAddDialogOpen(false)}>取消 Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreateSubmit}
            disabled={
              createLoading ||
              !createForm.symbol ||
              !createForm.expiration ||
              createForm.strike <= 0 ||
              createForm.entry_price <= 0
            }
            sx={{ bgcolor: BLUE, "&:hover": { bgcolor: "#2a6fd4" } }}
          >
            {createLoading ? "提交中..." : "确认新增"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={closeDialogOpen}
        onClose={() => setCloseDialogOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700 }}>
          平仓确认
          <Typography variant="caption" sx={{ ml: 1, color: "text.secondary" }}>
            Close Position
          </Typography>
        </DialogTitle>
        <DialogContent dividers>
          {closeError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {closeError}
            </Alert>
          )}
          {closeTarget && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" sx={{ color: "text.secondary", mb: 0.5 }}>
                {closeTarget.symbol} {closeTarget.option_type.toUpperCase()} $
                {closeTarget.strike} · {closeTarget.expiration}
              </Typography>
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                开仓价: ${closeTarget.entry_price.toFixed(2)} · 数量:{" "}
                {closeTarget.quantity}
              </Typography>
            </Box>
          )}
          <Grid container spacing={2}>
            <Grid size={{ xs: 12 }}>
              <TextField
                fullWidth
                size="small"
                label="平仓价 Exit Price"
                type="number"
                required
                value={closeForm.exit_price || ""}
                onChange={(e) =>
                  setCloseForm((f) => ({
                    ...f,
                    exit_price: parseFloat(e.target.value) || 0,
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <TextField
                fullWidth
                size="small"
                label="手续费 Commission (optional)"
                type="number"
                value={closeForm.exit_commission ?? ""}
                onChange={(e) =>
                  setCloseForm((f) => ({
                    ...f,
                    exit_commission: parseFloat(e.target.value) || 0,
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <TextField
                fullWidth
                size="small"
                label="平仓日期 Exit Date (optional)"
                value={closeForm.exit_date ?? ""}
                onChange={(e) =>
                  setCloseForm((f) => ({ ...f, exit_date: e.target.value }))
                }
                placeholder="2026-04-15"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setCloseDialogOpen(false)}>取消 Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCloseSubmit}
            disabled={closeLoading || closeForm.exit_price <= 0}
            color="success"
          >
            {closeLoading ? "处理中..." : "确认平仓"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700, color: RED }}>
          删除持仓
          <Typography variant="caption" sx={{ ml: 1, color: "text.secondary" }}>
            Delete Position
          </Typography>
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            {deleteTarget
              ? `确定要删除 ${deleteTarget.symbol} ${deleteTarget.option_type.toUpperCase()} $${deleteTarget.strike} · ${deleteTarget.expiration} 的持仓记录吗？此操作不可撤销。`
              : "确定要删除此持仓记录吗？"}
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setDeleteDialogOpen(false)}>取消 Cancel</Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleDeleteConfirm}
            disabled={deleteLoading}
          >
            {deleteLoading ? "删除中..." : "确认删除"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700 }}>
          编辑持仓
          <Typography variant="caption" sx={{ ml: 1, color: "text.secondary" }}>
            Edit Position
          </Typography>
        </DialogTitle>
        <DialogContent dividers>
          {editError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {editError}
            </Alert>
          )}
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                size="small"
                label="开仓价 Entry Price"
                type="number"
                value={editForm.entry_price ?? ""}
                onChange={(e) =>
                  setEditForm((f) => ({
                    ...f,
                    entry_price: parseFloat(e.target.value) || undefined,
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                size="small"
                label="手续费 Commission"
                type="number"
                value={editForm.entry_commission ?? ""}
                onChange={(e) =>
                  setEditForm((f) => ({
                    ...f,
                    entry_commission: parseFloat(e.target.value) || undefined,
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                size="small"
                label="数量 Quantity"
                type="number"
                value={editForm.quantity ?? ""}
                onChange={(e) =>
                  setEditForm((f) => ({
                    ...f,
                    quantity: parseInt(e.target.value, 10) || undefined,
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                size="small"
                label="策略名称 Strategy Name"
                value={editForm.strategy_name ?? ""}
                onChange={(e) =>
                  setEditForm((f) => ({
                    ...f,
                    strategy_name: e.target.value,
                  }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <TextField
                fullWidth
                size="small"
                label="标签 Tags"
                value={editForm.tags ?? ""}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, tags: e.target.value }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <TextField
                fullWidth
                size="small"
                multiline
                rows={2}
                label="备注 Notes"
                value={editForm.notes ?? ""}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, notes: e.target.value }))
                }
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setEditDialogOpen(false)}>取消 Cancel</Button>
          <Button
            variant="contained"
            onClick={handleEditSubmit}
            disabled={editLoading}
            sx={{ bgcolor: BLUE, "&:hover": { bgcolor: "#2a6fd4" } }}
          >
            {editLoading ? "保存中..." : "保存修改"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
