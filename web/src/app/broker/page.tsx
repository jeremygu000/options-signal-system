"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
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
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import IconButton from "@mui/material/IconButton";
import Table from "@mui/material/Table";
import TableHead from "@mui/material/TableHead";
import TableBody from "@mui/material/TableBody";
import TableRow from "@mui/material/TableRow";
import TableCell from "@mui/material/TableCell";
import Chip from "@mui/material/Chip";
import Tabs from "@mui/material/Tabs";
import Tab from "@mui/material/Tab";
import Tooltip from "@mui/material/Tooltip";
import RefreshIcon from "@mui/icons-material/Refresh";
import CloseIcon from "@mui/icons-material/Close";
import SectionHeader from "@/components/SectionHeader";
import { useThemeMode } from "@/components/ThemeProvider";
import {
  fetchBrokerAccount,
  submitOrder,
  fetchBrokerOrders,
  cancelOrder,
  cancelAllOrders,
  fetchBrokerPositions,
  closeBrokerPosition,
  closeAllBrokerPositions,
  fetchPortfolioHistory,
} from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import type {
  AccountInfoResponse,
  OrderResponse,
  BrokerPositionResponse,
  CreateOrderRequest,
  OrderSide,
  OrderType,
  TimeInForce,
  PortfolioHistoryResponse,
} from "@/lib/types";

const GREEN = "#36bb80";
const RED = "#ff7134";
const BLUE = "#3b89ff";
const YELLOW = "#fdbc2a";

const fmtMoney = (v: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(v);

function pnlColor(v: number): string {
  if (v > 0) return GREEN;
  if (v < 0) return RED;
  return "inherit";
}

function orderStatusColor(
  status: string,
): "success" | "warning" | "error" | "default" {
  if (status === "filled") return "success";
  if (
    status === "new" ||
    status === "accepted" ||
    status === "partially_filled"
  )
    return "warning";
  if (status === "canceled" || status === "expired" || status === "rejected")
    return "error";
  return "default";
}

function fmtTs(ts: string | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const EMPTY_ORDER: CreateOrderRequest = {
  symbol: "",
  side: "buy",
  order_type: "market",
  time_in_force: "day",
  qty: 1,
  notional: null,
  limit_price: null,
  stop_price: null,
};

type HistoryPeriod = "1D" | "1W" | "1M" | "3M";

const PERIOD_CONFIG: Record<
  HistoryPeriod,
  { period: string; timeframe: string }
> = {
  "1D": { period: "1D", timeframe: "5Min" },
  "1W": { period: "1W", timeframe: "1H" },
  "1M": { period: "1M", timeframe: "1D" },
  "3M": { period: "3M", timeframe: "1D" },
};

interface AccountCardProps {
  label: string;
  sublabel: string;
  value: string;
  color?: string;
  loading?: boolean;
}

function AccountCard({
  label,
  sublabel,
  value,
  color,
  loading,
}: AccountCardProps) {
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
          <Skeleton variant="text" width={100} height={32} />
        ) : (
          <Typography
            variant="h6"
            sx={{
              fontFamily: "var(--font-geist-mono)",
              fontWeight: 700,
              fontSize: "1.2rem",
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

export default function BrokerPage() {
  const { mode } = useThemeMode();
  const cardBg = mode === "dark" ? "#111827" : "#f9fafb";

  const [account, setAccount] = useState<AccountInfoResponse | null>(null);
  const [accountLoading, setAccountLoading] = useState(true);
  const [accountError, setAccountError] = useState<string | null>(null);

  const [positions, setPositions] = useState<BrokerPositionResponse[]>([]);
  const [positionsLoading, setPositionsLoading] = useState(true);
  const [positionsError, setPositionsError] = useState<string | null>(null);
  const [closingSymbol, setClosingSymbol] = useState<string | null>(null);
  const [closeAllLoading, setCloseAllLoading] = useState(false);

  const [orders, setOrders] = useState<OrderResponse[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(true);
  const [ordersError, setOrdersError] = useState<string | null>(null);
  const [orderTab, setOrderTab] = useState<"open" | "closed" | "all">("open");
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [cancelAllLoading, setCancelAllLoading] = useState(false);

  const [orderForm, setOrderForm] = useState<CreateOrderRequest>(EMPTY_ORDER);
  const [orderSubmitting, setOrderSubmitting] = useState(false);
  const [orderSuccess, setOrderSuccess] = useState<string | null>(null);
  const [orderError, setOrderError] = useState<string | null>(null);

  const [historyPeriod, setHistoryPeriod] = useState<HistoryPeriod>("1M");
  const [history, setHistory] = useState<PortfolioHistoryResponse | null>(null);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const [globalError, setGlobalError] = useState<string | null>(null);

  const loadAccount = useCallback(() => {
    setAccountLoading(true);
    setAccountError(null);
    fetchBrokerAccount()
      .then(setAccount)
      .catch((e: unknown) =>
        setAccountError(
          e instanceof Error ? e.message : "Failed to load account",
        ),
      )
      .finally(() => setAccountLoading(false));
  }, []);

  const loadPositions = useCallback(() => {
    setPositionsLoading(true);
    setPositionsError(null);
    fetchBrokerPositions()
      .then(setPositions)
      .catch((e: unknown) =>
        setPositionsError(
          e instanceof Error ? e.message : "Failed to load positions",
        ),
      )
      .finally(() => setPositionsLoading(false));
  }, []);

  const loadOrders = useCallback(() => {
    setOrdersLoading(true);
    setOrdersError(null);
    const statusParam =
      orderTab === "open"
        ? "open"
        : orderTab === "closed"
          ? "closed"
          : undefined;
    fetchBrokerOrders({ status: statusParam, limit: 100 })
      .then(setOrders)
      .catch((e: unknown) =>
        setOrdersError(
          e instanceof Error ? e.message : "Failed to load orders",
        ),
      )
      .finally(() => setOrdersLoading(false));
  }, [orderTab]);

  const loadHistory = useCallback(() => {
    setHistoryLoading(true);
    setHistoryError(null);
    const cfg = PERIOD_CONFIG[historyPeriod];
    fetchPortfolioHistory({
      period: cfg.period,
      timeframe: cfg.timeframe,
      extended_hours: false,
    })
      .then(setHistory)
      .catch((e: unknown) =>
        setHistoryError(
          e instanceof Error ? e.message : "Failed to load portfolio history",
        ),
      )
      .finally(() => setHistoryLoading(false));
  }, [historyPeriod]);

  const refreshAll = useCallback(() => {
    loadAccount();
    loadPositions();
    loadOrders();
  }, [loadAccount, loadPositions, loadOrders]);

  useEffect(() => {
    loadAccount();
    loadPositions();
  }, [loadAccount, loadPositions]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const { channelData } = useWebSocket(["broker"]);

  useEffect(() => {
    const pushed = channelData.broker as
      | {
          account: AccountInfoResponse;
          positions: BrokerPositionResponse[];
          orders: OrderResponse[];
        }
      | null
      | undefined;
    if (pushed) {
      setAccount(pushed.account);
      setAccountLoading(false);
      setPositions(pushed.positions);
      setPositionsLoading(false);
      setOrders(pushed.orders);
      setOrdersLoading(false);
    }
  }, [channelData.broker]);

  function handleOrderSubmit() {
    setOrderSubmitting(true);
    setOrderError(null);
    setOrderSuccess(null);
    const payload: CreateOrderRequest = {
      ...orderForm,
      symbol: orderForm.symbol.trim().toUpperCase(),
      limit_price:
        orderForm.order_type === "limit" ||
        orderForm.order_type === "stop_limit"
          ? orderForm.limit_price
          : null,
      stop_price:
        orderForm.order_type === "stop" || orderForm.order_type === "stop_limit"
          ? orderForm.stop_price
          : null,
    };
    submitOrder(payload)
      .then((order) => {
        setOrderSuccess(
          `Order submitted: ${order.id.slice(0, 8)}… (${order.status})`,
        );
        setOrderForm(EMPTY_ORDER);
        loadOrders();
      })
      .catch((e: unknown) =>
        setOrderError(
          e instanceof Error ? e.message : "Order submission failed",
        ),
      )
      .finally(() => setOrderSubmitting(false));
  }

  function handleCancelOrder(orderId: string) {
    setCancellingId(orderId);
    cancelOrder(orderId)
      .then(() => loadOrders())
      .catch((e: unknown) =>
        setGlobalError(
          e instanceof Error ? e.message : "Failed to cancel order",
        ),
      )
      .finally(() => setCancellingId(null));
  }

  function handleCancelAll() {
    setCancelAllLoading(true);
    cancelAllOrders()
      .then(() => loadOrders())
      .catch((e: unknown) =>
        setGlobalError(
          e instanceof Error ? e.message : "Failed to cancel all orders",
        ),
      )
      .finally(() => setCancelAllLoading(false));
  }

  function handleClosePosition(symbol: string) {
    setClosingSymbol(symbol);
    closeBrokerPosition(symbol)
      .then(() => {
        loadPositions();
        loadAccount();
      })
      .catch((e: unknown) =>
        setGlobalError(
          e instanceof Error ? e.message : `Failed to close ${symbol}`,
        ),
      )
      .finally(() => setClosingSymbol(null));
  }

  function handleCloseAll() {
    setCloseAllLoading(true);
    closeAllBrokerPositions()
      .then(() => {
        loadPositions();
        loadAccount();
      })
      .catch((e: unknown) =>
        setGlobalError(
          e instanceof Error ? e.message : "Failed to close all positions",
        ),
      )
      .finally(() => setCloseAllLoading(false));
  }

  const showLimitPrice =
    orderForm.order_type === "limit" || orderForm.order_type === "stop_limit";
  const showStopPrice =
    orderForm.order_type === "stop" || orderForm.order_type === "stop_limit";

  const svgChart = useMemo(() => {
    if (!history || history.equity.length < 2) return null;
    const equities = history.equity.filter((v) => v != null && v > 0);
    if (equities.length < 2) return null;
    const W = 900;
    const H = 200;
    const pad = { t: 16, r: 16, b: 32, l: 72 };
    const minV = Math.min(...equities);
    const maxV = Math.max(...equities);
    const range = maxV - minV || 1;
    const xs = equities.map(
      (_, i) => pad.l + (i / (equities.length - 1)) * (W - pad.l - pad.r),
    );
    const ys = equities.map(
      (v) => pad.t + (1 - (v - minV) / range) * (H - pad.t - pad.b),
    );
    const d = xs
      .map(
        (x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${ys[i].toFixed(1)}`,
      )
      .join(" ");
    const lastV = equities[equities.length - 1];
    const firstV = equities[0];
    const lineColor = lastV >= firstV ? GREEN : RED;
    const fillId = `fill-${historyPeriod}`;
    return { W, H, d, lineColor, fillId, xs, ys, minV, maxV, pad, equities };
  }, [history, historyPeriod]);

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
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <Typography
              variant="h5"
              sx={{ fontWeight: 800, fontSize: "1.4rem" }}
            >
              券商交易台
            </Typography>
            <Chip
              label="Paper Trading"
              size="small"
              sx={{
                bgcolor: "rgba(253,188,42,0.15)",
                color: YELLOW,
                fontWeight: 700,
                fontSize: "0.7rem",
                height: 22,
                border: `1px solid rgba(253,188,42,0.3)`,
              }}
            />
          </Box>
          <Typography
            variant="body2"
            sx={{ color: "text.secondary", mt: 0.25 }}
          >
            Broker Dashboard · Alpaca Paper Trading
          </Typography>
        </Box>
        <Tooltip title="刷新所有数据 / Refresh all" arrow>
          <IconButton onClick={refreshAll} size="small">
            <RefreshIcon sx={{ fontSize: "1.1rem" }} />
          </IconButton>
        </Tooltip>
      </Box>

      {globalError && (
        <Alert
          severity="error"
          sx={{ mb: 2 }}
          onClose={() => setGlobalError(null)}
        >
          {globalError}
        </Alert>
      )}

      {/* ── 01 Account Overview ──────────────────────────── */}
      <Box component="section" sx={{ mb: 6 }}>
        <SectionHeader
          number="01"
          title="账户概览"
          subtitle="Account Overview"
        />
        {accountError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {accountError}
          </Alert>
        )}
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 6, md: 2 }}>
            <AccountCard
              label="现金"
              sublabel="Cash"
              value={account ? fmtMoney(account.cash) : "—"}
              loading={accountLoading}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 2 }}>
            <AccountCard
              label="账户净值"
              sublabel="Equity"
              value={account ? fmtMoney(account.equity) : "—"}
              color={BLUE}
              loading={accountLoading}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 2 }}>
            <AccountCard
              label="组合价值"
              sublabel="Portfolio Value"
              value={account ? fmtMoney(account.portfolio_value) : "—"}
              loading={accountLoading}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 2 }}>
            <AccountCard
              label="购买力"
              sublabel="Buying Power"
              value={account ? fmtMoney(account.buying_power) : "—"}
              color={GREEN}
              loading={accountLoading}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 2 }}>
            <AccountCard
              label="多头市值"
              sublabel="Long Market Value"
              value={account ? fmtMoney(account.long_market_value) : "—"}
              loading={accountLoading}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 2 }}>
            <AccountCard
              label="空头市值"
              sublabel="Short Market Value"
              value={account ? fmtMoney(account.short_market_value) : "—"}
              loading={accountLoading}
            />
          </Grid>
        </Grid>
        {account && (
          <Box sx={{ mt: 1.5, display: "flex", gap: 1.5 }}>
            <Chip
              label={account.pattern_day_trader ? "PDT 账户" : "非 PDT"}
              size="small"
              sx={{
                height: 20,
                fontSize: "0.65rem",
                bgcolor: account.pattern_day_trader
                  ? "rgba(255,113,52,0.12)"
                  : "rgba(54,187,128,0.12)",
                color: account.pattern_day_trader ? RED : GREEN,
              }}
            />
            <Chip
              label={`状态: ${account.status}`}
              size="small"
              sx={{
                height: 20,
                fontSize: "0.65rem",
                bgcolor: "rgba(59,137,255,0.1)",
                color: BLUE,
              }}
            />
            <Chip
              label={account.currency}
              size="small"
              sx={{
                height: 20,
                fontSize: "0.65rem",
                bgcolor: "rgba(253,188,42,0.1)",
                color: YELLOW,
              }}
            />
          </Box>
        )}
      </Box>

      {/* ── 02 Submit Order ──────────────────────────────── */}
      <Box component="section" sx={{ mb: 6 }}>
        <SectionHeader number="02" title="下单" subtitle="Submit Order" />
        <Card>
          <CardContent>
            {orderSuccess && (
              <Alert
                severity="success"
                sx={{ mb: 2 }}
                onClose={() => setOrderSuccess(null)}
              >
                {orderSuccess}
              </Alert>
            )}
            {orderError && (
              <Alert
                severity="error"
                sx={{ mb: 2 }}
                onClose={() => setOrderError(null)}
              >
                {orderError}
              </Alert>
            )}
            <Grid container spacing={2} alignItems="flex-end">
              <Grid size={{ xs: 12, sm: 6, md: 2 }}>
                <TextField
                  fullWidth
                  size="small"
                  label="标的 Symbol"
                  required
                  value={orderForm.symbol}
                  onChange={(e) =>
                    setOrderForm((f) => ({ ...f, symbol: e.target.value }))
                  }
                  placeholder="AAPL"
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 2 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>方向 Side</InputLabel>
                  <Select
                    value={orderForm.side}
                    label="方向 Side"
                    onChange={(e) =>
                      setOrderForm((f) => ({
                        ...f,
                        side: e.target.value as OrderSide,
                      }))
                    }
                  >
                    <MenuItem value="buy">
                      <Typography sx={{ color: GREEN, fontWeight: 600 }}>
                        Buy 买入
                      </Typography>
                    </MenuItem>
                    <MenuItem value="sell">
                      <Typography sx={{ color: RED, fontWeight: 600 }}>
                        Sell 卖出
                      </Typography>
                    </MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 2 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>类型 Type</InputLabel>
                  <Select
                    value={orderForm.order_type}
                    label="类型 Type"
                    onChange={(e) =>
                      setOrderForm((f) => ({
                        ...f,
                        order_type: e.target.value as OrderType,
                      }))
                    }
                  >
                    <MenuItem value="market">Market 市价</MenuItem>
                    <MenuItem value="limit">Limit 限价</MenuItem>
                    <MenuItem value="stop">Stop 止损</MenuItem>
                    <MenuItem value="stop_limit">Stop Limit 止损限价</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 1.5 }}>
                <TextField
                  fullWidth
                  size="small"
                  label="数量 Qty"
                  type="number"
                  required
                  value={orderForm.qty ?? ""}
                  onChange={(e) =>
                    setOrderForm((f) => ({
                      ...f,
                      qty: parseFloat(e.target.value) || null,
                    }))
                  }
                />
              </Grid>
              {showLimitPrice && (
                <Grid size={{ xs: 12, sm: 6, md: 1.5 }}>
                  <TextField
                    fullWidth
                    size="small"
                    label="限价 Limit $"
                    type="number"
                    value={orderForm.limit_price ?? ""}
                    onChange={(e) =>
                      setOrderForm((f) => ({
                        ...f,
                        limit_price: parseFloat(e.target.value) || null,
                      }))
                    }
                  />
                </Grid>
              )}
              {showStopPrice && (
                <Grid size={{ xs: 12, sm: 6, md: 1.5 }}>
                  <TextField
                    fullWidth
                    size="small"
                    label="止损价 Stop $"
                    type="number"
                    value={orderForm.stop_price ?? ""}
                    onChange={(e) =>
                      setOrderForm((f) => ({
                        ...f,
                        stop_price: parseFloat(e.target.value) || null,
                      }))
                    }
                  />
                </Grid>
              )}
              <Grid size={{ xs: 12, sm: 6, md: 2 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>有效期 TIF</InputLabel>
                  <Select
                    value={orderForm.time_in_force}
                    label="有效期 TIF"
                    onChange={(e) =>
                      setOrderForm((f) => ({
                        ...f,
                        time_in_force: e.target.value as TimeInForce,
                      }))
                    }
                  >
                    <MenuItem value="day">Day 当日</MenuItem>
                    <MenuItem value="gtc">GTC 长期有效</MenuItem>
                    <MenuItem value="ioc">IOC 立即成交</MenuItem>
                    <MenuItem value="fok">FOK 全部成交</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 2 }}>
                <Button
                  fullWidth
                  variant="contained"
                  disabled={
                    orderSubmitting ||
                    !orderForm.symbol.trim() ||
                    !orderForm.qty
                  }
                  onClick={handleOrderSubmit}
                  sx={{
                    bgcolor: orderForm.side === "buy" ? GREEN : RED,
                    "&:hover": {
                      bgcolor: orderForm.side === "buy" ? "#2da06c" : "#d45e20",
                    },
                    fontWeight: 700,
                  }}
                >
                  {orderSubmitting
                    ? "提交中…"
                    : orderForm.side === "buy"
                      ? "买入下单"
                      : "卖出下单"}
                </Button>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      </Box>

      {/* ── 03 Positions ─────────────────────────────────── */}
      <Box component="section" sx={{ mb: 6 }}>
        <Box
          sx={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            mb: 0,
          }}
        >
          <SectionHeader number="03" title="持仓" subtitle="Positions" />
          <Button
            variant="outlined"
            size="small"
            color="error"
            onClick={handleCloseAll}
            disabled={closeAllLoading || positions.length === 0}
            sx={{ mt: 0.25, fontSize: "0.75rem", flexShrink: 0 }}
          >
            {closeAllLoading ? "平仓中…" : "全部平仓 Close All"}
          </Button>
        </Box>
        {positionsError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {positionsError}
          </Alert>
        )}
        {positionsLoading ? (
          <Box>
            {[1, 2, 3].map((n) => (
              <Skeleton
                key={n}
                variant="rounded"
                height={44}
                sx={{ mb: 0.5 }}
              />
            ))}
          </Box>
        ) : positions.length === 0 ? (
          <Card sx={{ bgcolor: cardBg }}>
            <CardContent>
              <Typography variant="body2" sx={{ color: "text.secondary" }}>
                暂无持仓 / No open positions
              </Typography>
            </CardContent>
          </Card>
        ) : (
          <Box sx={{ overflowX: "auto" }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Symbol</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    Qty
                  </TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Side</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    Avg Entry
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    Current Price
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    Market Value
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    Unrealized P&L
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    P&L %
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    操作
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {positions.map((pos) => {
                  const pnl = pos.unrealized_pl
                    ? parseFloat(pos.unrealized_pl)
                    : null;
                  const pnlPct = pos.unrealized_plpc
                    ? parseFloat(pos.unrealized_plpc) * 100
                    : null;
                  const mv = pos.market_value
                    ? parseFloat(pos.market_value)
                    : null;
                  const entry = pos.avg_entry_price
                    ? parseFloat(pos.avg_entry_price)
                    : null;
                  const curr = pos.current_price
                    ? parseFloat(pos.current_price)
                    : null;
                  return (
                    <TableRow
                      key={pos.symbol}
                      hover
                      sx={{ "&:last-child td": { border: 0 } }}
                    >
                      <TableCell
                        sx={{
                          fontFamily: "var(--font-geist-mono)",
                          fontWeight: 700,
                        }}
                      >
                        {pos.symbol}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontFamily: "var(--font-geist-mono)" }}
                      >
                        {pos.qty}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={pos.side.toUpperCase()}
                          size="small"
                          sx={{
                            height: 20,
                            fontSize: "0.65rem",
                            bgcolor:
                              pos.side === "long"
                                ? "rgba(54,187,128,0.12)"
                                : "rgba(255,113,52,0.12)",
                            color: pos.side === "long" ? GREEN : RED,
                          }}
                        />
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontFamily: "var(--font-geist-mono)" }}
                      >
                        {entry != null ? fmtMoney(entry) : "—"}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontFamily: "var(--font-geist-mono)" }}
                      >
                        {curr != null ? fmtMoney(curr) : "—"}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontFamily: "var(--font-geist-mono)" }}
                      >
                        {mv != null ? fmtMoney(mv) : "—"}
                      </TableCell>
                      <TableCell align="right">
                        {pnl != null ? (
                          <Typography
                            variant="body2"
                            sx={{
                              fontFamily: "var(--font-geist-mono)",
                              fontWeight: 600,
                              color: pnlColor(pnl),
                            }}
                          >
                            {pnl >= 0 ? "+" : ""}
                            {fmtMoney(pnl)}
                          </Typography>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell align="right">
                        {pnlPct != null ? (
                          <Typography
                            variant="body2"
                            sx={{
                              fontFamily: "var(--font-geist-mono)",
                              fontWeight: 600,
                              color: pnlColor(pnlPct),
                            }}
                          >
                            {pnlPct >= 0 ? "+" : ""}
                            {pnlPct.toFixed(2)}%
                          </Typography>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell align="right">
                        <Tooltip title={`平仓 ${pos.symbol}`} arrow>
                          <span>
                            <IconButton
                              size="small"
                              onClick={() => handleClosePosition(pos.symbol)}
                              disabled={closingSymbol === pos.symbol}
                              sx={{ color: RED }}
                            >
                              <CloseIcon sx={{ fontSize: "0.9rem" }} />
                            </IconButton>
                          </span>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Box>
        )}
      </Box>

      {/* ── 04 Orders ────────────────────────────────────── */}
      <Box component="section" sx={{ mb: 6 }}>
        <Box
          sx={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            mb: 0,
          }}
        >
          <SectionHeader number="04" title="订单" subtitle="Orders" />
          {orderTab === "open" && (
            <Button
              variant="outlined"
              size="small"
              color="error"
              onClick={handleCancelAll}
              disabled={cancelAllLoading}
              sx={{ mt: 0.25, fontSize: "0.75rem", flexShrink: 0 }}
            >
              {cancelAllLoading ? "撤单中…" : "全部撤单 Cancel All"}
            </Button>
          )}
        </Box>

        <Tabs
          value={orderTab}
          onChange={(_e, v: "open" | "closed" | "all") => setOrderTab(v)}
          sx={{ mb: 2, minHeight: 36 }}
          TabIndicatorProps={{ style: { backgroundColor: BLUE } }}
        >
          <Tab
            value="open"
            label="Open 待成交"
            sx={{ minHeight: 36, fontSize: "0.8rem" }}
          />
          <Tab
            value="closed"
            label="Closed 已完成"
            sx={{ minHeight: 36, fontSize: "0.8rem" }}
          />
          <Tab
            value="all"
            label="All 全部"
            sx={{ minHeight: 36, fontSize: "0.8rem" }}
          />
        </Tabs>

        {ordersError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {ordersError}
          </Alert>
        )}

        {ordersLoading ? (
          <Box>
            {[1, 2, 3].map((n) => (
              <Skeleton
                key={n}
                variant="rounded"
                height={44}
                sx={{ mb: 0.5 }}
              />
            ))}
          </Box>
        ) : orders.length === 0 ? (
          <Card sx={{ bgcolor: cardBg }}>
            <CardContent>
              <Typography variant="body2" sx={{ color: "text.secondary" }}>
                暂无订单 / No orders found
              </Typography>
            </CardContent>
          </Card>
        ) : (
          <Box sx={{ overflowX: "auto" }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Symbol</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Side</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Type</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    Qty
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    Limit $
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    Stop $
                  </TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Submitted</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    Filled Qty
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    Filled $
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    操作
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {orders.map((order) => {
                  const isOpen =
                    order.status === "new" ||
                    order.status === "accepted" ||
                    order.status === "partially_filled" ||
                    order.status === "pending_new" ||
                    order.status === "pending_cancel" ||
                    order.status === "pending_replace";
                  return (
                    <TableRow
                      key={order.id}
                      hover
                      sx={{ "&:last-child td": { border: 0 } }}
                    >
                      <TableCell
                        sx={{
                          fontFamily: "var(--font-geist-mono)",
                          fontWeight: 700,
                        }}
                      >
                        {order.symbol}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={order.side.toUpperCase()}
                          size="small"
                          sx={{
                            height: 20,
                            fontSize: "0.65rem",
                            bgcolor:
                              order.side === "buy"
                                ? "rgba(54,187,128,0.12)"
                                : "rgba(255,113,52,0.12)",
                            color: order.side === "buy" ? GREEN : RED,
                          }}
                        />
                      </TableCell>
                      <TableCell sx={{ fontSize: "0.8rem" }}>
                        {order.order_type}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontFamily: "var(--font-geist-mono)" }}
                      >
                        {order.qty ?? "—"}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontFamily: "var(--font-geist-mono)" }}
                      >
                        {order.limit_price
                          ? `$${parseFloat(order.limit_price).toFixed(2)}`
                          : "—"}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontFamily: "var(--font-geist-mono)" }}
                      >
                        {order.stop_price
                          ? `$${parseFloat(order.stop_price).toFixed(2)}`
                          : "—"}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={order.status}
                          size="small"
                          color={orderStatusColor(order.status)}
                          sx={{ height: 20, fontSize: "0.6rem" }}
                        />
                      </TableCell>
                      <TableCell
                        sx={{
                          fontSize: "0.75rem",
                          color: "text.secondary",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {fmtTs(order.submitted_at)}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontFamily: "var(--font-geist-mono)" }}
                      >
                        {order.filled_qty ?? "—"}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontFamily: "var(--font-geist-mono)" }}
                      >
                        {order.filled_avg_price
                          ? `$${parseFloat(order.filled_avg_price).toFixed(2)}`
                          : "—"}
                      </TableCell>
                      <TableCell align="right">
                        {isOpen && (
                          <Tooltip title="撤单 Cancel" arrow>
                            <span>
                              <IconButton
                                size="small"
                                onClick={() => handleCancelOrder(order.id)}
                                disabled={cancellingId === order.id}
                                sx={{ color: RED }}
                              >
                                <CloseIcon sx={{ fontSize: "0.9rem" }} />
                              </IconButton>
                            </span>
                          </Tooltip>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Box>
        )}
      </Box>

      {/* ── 05 Portfolio History ─────────────────────────── */}
      <Box component="section" sx={{ mb: 6 }}>
        <SectionHeader
          number="05"
          title="权益曲线"
          subtitle="Portfolio History"
        />

        <Box sx={{ display: "flex", gap: 1, mb: 2 }}>
          {(["1D", "1W", "1M", "3M"] as HistoryPeriod[]).map((p) => (
            <Button
              key={p}
              size="small"
              variant={historyPeriod === p ? "contained" : "outlined"}
              onClick={() => setHistoryPeriod(p)}
              sx={{
                minWidth: 48,
                fontSize: "0.75rem",
                ...(historyPeriod === p && { bgcolor: BLUE }),
              }}
            >
              {p}
            </Button>
          ))}
        </Box>

        {historyError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {historyError}
          </Alert>
        )}

        <Card>
          <CardContent>
            {historyLoading ? (
              <Skeleton variant="rounded" height={220} />
            ) : !svgChart ? (
              <Typography
                variant="body2"
                sx={{ color: "text.secondary", py: 4, textAlign: "center" }}
              >
                暂无数据 / No portfolio history data available
              </Typography>
            ) : (
              <Box>
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    mb: 1,
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      color: "text.secondary",
                    }}
                  >
                    {fmtMoney(svgChart.minV)}
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      fontWeight: 700,
                      color: svgChart.lineColor,
                    }}
                  >
                    {fmtMoney(svgChart.equities[svgChart.equities.length - 1])}
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{
                      fontFamily: "var(--font-geist-mono)",
                      color: "text.secondary",
                    }}
                  >
                    {fmtMoney(svgChart.maxV)}
                  </Typography>
                </Box>
                <Box sx={{ width: "100%", overflowX: "auto" }}>
                  <svg
                    viewBox={`0 0 ${svgChart.W} ${svgChart.H}`}
                    width="100%"
                    style={{ display: "block" }}
                  >
                    <defs>
                      <linearGradient
                        id={svgChart.fillId}
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="0%"
                          stopColor={svgChart.lineColor}
                          stopOpacity={0.25}
                        />
                        <stop
                          offset="100%"
                          stopColor={svgChart.lineColor}
                          stopOpacity={0}
                        />
                      </linearGradient>
                    </defs>
                    <path
                      d={`${svgChart.d} L${svgChart.xs[svgChart.xs.length - 1].toFixed(1)},${(svgChart.H - svgChart.pad.b).toFixed(1)} L${svgChart.xs[0].toFixed(1)},${(svgChart.H - svgChart.pad.b).toFixed(1)} Z`}
                      fill={`url(#${svgChart.fillId})`}
                    />
                    <path
                      d={svgChart.d}
                      fill="none"
                      stroke={svgChart.lineColor}
                      strokeWidth={2}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </Box>
                {history && history.profit_loss.length > 0 && (
                  <Box
                    sx={{
                      display: "flex",
                      gap: 3,
                      mt: 1.5,
                      flexWrap: "wrap",
                    }}
                  >
                    <Box>
                      <Typography
                        variant="caption"
                        sx={{ color: "text.secondary" }}
                      >
                        Base Value
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{
                          fontFamily: "var(--font-geist-mono)",
                          fontWeight: 600,
                        }}
                      >
                        {fmtMoney(history.base_value)}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography
                        variant="caption"
                        sx={{ color: "text.secondary" }}
                      >
                        Total P&L
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{
                          fontFamily: "var(--font-geist-mono)",
                          fontWeight: 700,
                          color: pnlColor(
                            history.profit_loss[history.profit_loss.length - 1],
                          ),
                        }}
                      >
                        {fmtMoney(
                          history.profit_loss[history.profit_loss.length - 1],
                        )}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography
                        variant="caption"
                        sx={{ color: "text.secondary" }}
                      >
                        P&L %
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{
                          fontFamily: "var(--font-geist-mono)",
                          fontWeight: 700,
                          color: pnlColor(
                            history.profit_loss_pct[
                              history.profit_loss_pct.length - 1
                            ],
                          ),
                        }}
                      >
                        {(
                          history.profit_loss_pct[
                            history.profit_loss_pct.length - 1
                          ] * 100
                        ).toFixed(2)}
                        %
                      </Typography>
                    </Box>
                    <Box>
                      <Typography
                        variant="caption"
                        sx={{ color: "text.secondary" }}
                      >
                        Data Points
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{
                          fontFamily: "var(--font-geist-mono)",
                          fontWeight: 600,
                        }}
                      >
                        {history.equity.length}
                      </Typography>
                    </Box>
                  </Box>
                )}
              </Box>
            )}
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
