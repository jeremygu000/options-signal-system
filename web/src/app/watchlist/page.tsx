"use client";

import { useState, useEffect, useCallback } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import CardActions from "@mui/material/CardActions";
import Typography from "@mui/material/Typography";
import Skeleton from "@mui/material/Skeleton";
import Alert from "@mui/material/Alert";
import Grid from "@mui/material/Grid";
import Button from "@mui/material/Button";
import IconButton from "@mui/material/IconButton";
import TextField from "@mui/material/TextField";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
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
import Collapse from "@mui/material/Collapse";
import AddIcon from "@mui/icons-material/Add";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import StarIcon from "@mui/icons-material/Star";
import StarBorderIcon from "@mui/icons-material/StarBorder";
import SectionHeader from "@/components/SectionHeader";
import {
  fetchWatchlists,
  createWatchlist,
  activateWatchlist,
  deleteWatchlist,
  addWatchlistItem,
  deleteWatchlistItem,
} from "@/lib/api";
import type { WatchlistResponse, WatchlistItemResponse } from "@/lib/types";

// ── Constants ───────────────────────────────────────────────────────

const SECTORS = [
  "Technology",
  "Finance",
  "Energy",
  "Healthcare",
  "Consumer",
  "ETF",
  "Other",
];

const BIAS_OPTIONS = ["auto", "short", "long"];

const SECTOR_COLORS: Record<string, string> = {
  Technology: "#3b89ff",
  Finance: "#36bb80",
  Energy: "#ff7134",
  Healthcare: "#a78bfa",
  Consumer: "#f472b6",
  ETF: "#fdbc2a",
  Other: "#94a3b8",
};

const BIAS_COLORS: Record<string, string> = {
  auto: "#94a3b8",
  short: "#ff7134",
  long: "#36bb80",
};

// ── Component ───────────────────────────────────────────────────────

export default function WatchlistPage() {
  const [watchlists, setWatchlists] = useState<WatchlistResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Expanded watchlist card
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  // Delete dialog
  const [deleteTarget, setDeleteTarget] = useState<WatchlistResponse | null>(
    null,
  );
  const [deleting, setDeleting] = useState(false);

  // Add item form
  const [addSymbol, setAddSymbol] = useState("");
  const [addSector, setAddSector] = useState("Other");
  const [addBias, setAddBias] = useState("auto");
  const [adding, setAdding] = useState(false);

  // ── Data loading ────────────────────────────────────────────────

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await fetchWatchlists();
      setWatchlists(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load watchlists");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // ── Actions ─────────────────────────────────────────────────────

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await createWatchlist({
        name: newName.trim(),
        description: newDesc.trim(),
      });
      setCreateOpen(false);
      setNewName("");
      setNewDesc("");
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create");
    } finally {
      setCreating(false);
    }
  };

  const handleActivate = async (id: string) => {
    try {
      await activateWatchlist(id);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to activate");
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteWatchlist(deleteTarget.id);
      setDeleteTarget(null);
      if (expandedId === deleteTarget.id) setExpandedId(null);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete");
    } finally {
      setDeleting(false);
    }
  };

  const handleAddItem = async (watchlistId: string) => {
    const sym = addSymbol.trim().toUpperCase();
    if (!sym) return;
    setAdding(true);
    try {
      await addWatchlistItem(watchlistId, {
        symbol: sym,
        sector: addSector,
        bias: addBias,
      });
      setAddSymbol("");
      setAddSector("Other");
      setAddBias("auto");
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to add item");
    } finally {
      setAdding(false);
    }
  };

  const handleDeleteItem = async (itemId: string) => {
    try {
      await deleteWatchlistItem(itemId);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete item");
    }
  };

  // ── Grouped items by sector ─────────────────────────────────────

  function groupBySector(
    items: WatchlistItemResponse[],
  ): Record<string, WatchlistItemResponse[]> {
    const groups: Record<string, WatchlistItemResponse[]> = {};
    for (const item of items) {
      const key = item.sector || "Other";
      if (!groups[key]) groups[key] = [];
      groups[key].push(item);
    }
    return groups;
  }

  // ── Render ──────────────────────────────────────────────────────

  return (
    <Box sx={{ px: 4, py: 3 }}>
      <SectionHeader
        number="WL"
        title="自选列表"
        subtitle="Watchlist Management"
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Toolbar */}
      <Box sx={{ display: "flex", justifyContent: "flex-end", mb: 2 }}>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setCreateOpen(true)}
          size="small"
        >
          新建列表
        </Button>
      </Box>

      {/* Loading skeleton */}
      {loading && (
        <Grid container spacing={2}>
          {["a", "b", "c"].map((k) => (
            <Grid key={k} size={{ xs: 12, md: 6, lg: 4 }}>
              <Skeleton variant="rounded" height={140} />
            </Grid>
          ))}
        </Grid>
      )}

      {/* Empty state */}
      {!loading && watchlists.length === 0 && (
        <Alert severity="info">
          暂无自选列表。点击「新建列表」创建第一个。
        </Alert>
      )}

      {/* Watchlist cards */}
      {!loading && watchlists.length > 0 && (
        <Grid container spacing={2}>
          {watchlists.map((wl) => {
            const isExpanded = expandedId === wl.id;
            const grouped = groupBySector(wl.items);

            return (
              <Grid key={wl.id} size={{ xs: 12 }}>
                <Card
                  variant="outlined"
                  sx={{
                    borderColor: wl.is_active ? "success.main" : "divider",
                    borderWidth: wl.is_active ? 2 : 1,
                  }}
                >
                  <CardContent sx={{ pb: 0 }}>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                        mb: 0.5,
                      }}
                    >
                      <Typography variant="h6" sx={{ fontWeight: 700 }}>
                        {wl.name}
                      </Typography>
                      {wl.is_active && (
                        <Chip
                          label="Active"
                          size="small"
                          color="success"
                          icon={<CheckCircleIcon />}
                        />
                      )}
                      <Typography
                        variant="caption"
                        sx={{ color: "text.secondary", ml: "auto" }}
                      >
                        {wl.items.length} symbols
                      </Typography>
                    </Box>
                    {wl.description && (
                      <Typography
                        variant="body2"
                        sx={{ color: "text.secondary", mb: 1 }}
                      >
                        {wl.description}
                      </Typography>
                    )}

                    {/* Symbol chips preview (collapsed) */}
                    {!isExpanded && wl.items.length > 0 && (
                      <Box
                        sx={{
                          display: "flex",
                          gap: 0.5,
                          flexWrap: "wrap",
                          mt: 1,
                        }}
                      >
                        {wl.items.slice(0, 15).map((item) => (
                          <Chip
                            key={item.id}
                            label={item.symbol}
                            size="small"
                            sx={{
                              fontFamily: "var(--font-geist-mono)",
                              fontWeight: 600,
                              fontSize: "0.7rem",
                              borderLeft: `3px solid ${SECTOR_COLORS[item.sector] ?? SECTOR_COLORS.Other}`,
                            }}
                          />
                        ))}
                        {wl.items.length > 15 && (
                          <Chip
                            label={`+${wl.items.length - 15}`}
                            size="small"
                            variant="outlined"
                            sx={{ fontSize: "0.7rem" }}
                          />
                        )}
                      </Box>
                    )}
                  </CardContent>

                  <CardActions sx={{ px: 2, pb: 1.5, pt: 0.5 }}>
                    {!wl.is_active && (
                      <Button
                        size="small"
                        startIcon={<StarBorderIcon />}
                        onClick={() => handleActivate(wl.id)}
                      >
                        激活
                      </Button>
                    )}
                    {wl.is_active && (
                      <Button
                        size="small"
                        disabled
                        startIcon={<StarIcon />}
                        color="success"
                      >
                        当前激活
                      </Button>
                    )}
                    <Button
                      size="small"
                      onClick={() => setExpandedId(isExpanded ? null : wl.id)}
                      endIcon={
                        isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />
                      }
                    >
                      {isExpanded ? "收起" : "展开"}
                    </Button>
                    <Box sx={{ flexGrow: 1 }} />
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => setDeleteTarget(wl)}
                    >
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </CardActions>

                  {/* Expanded detail */}
                  <Collapse in={isExpanded}>
                    <Box sx={{ px: 2, pb: 2 }}>
                      {/* Items table */}
                      {wl.items.length > 0 ? (
                        <Table size="small">
                          <TableHead>
                            <TableRow>
                              <TableCell sx={{ fontWeight: 700 }}>
                                Symbol
                              </TableCell>
                              <TableCell sx={{ fontWeight: 700 }}>
                                Sector
                              </TableCell>
                              <TableCell sx={{ fontWeight: 700 }}>
                                Bias
                              </TableCell>
                              <TableCell align="right" sx={{ fontWeight: 700 }}>
                                操作
                              </TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {Object.entries(grouped).map(([sector, items]) =>
                              items.map((item, idx) => (
                                <TableRow key={item.id}>
                                  <TableCell
                                    sx={{
                                      fontFamily: "var(--font-geist-mono)",
                                      fontWeight: 700,
                                    }}
                                  >
                                    {item.symbol}
                                  </TableCell>
                                  <TableCell>
                                    {idx === 0 ? (
                                      <Chip
                                        label={sector}
                                        size="small"
                                        sx={{
                                          bgcolor:
                                            SECTOR_COLORS[sector] ??
                                            SECTOR_COLORS.Other,
                                          color: "#fff",
                                          fontWeight: 600,
                                          fontSize: "0.7rem",
                                        }}
                                      />
                                    ) : (
                                      <Typography
                                        variant="caption"
                                        sx={{ color: "text.disabled" }}
                                      >
                                        {sector}
                                      </Typography>
                                    )}
                                  </TableCell>
                                  <TableCell>
                                    <Chip
                                      label={item.bias}
                                      size="small"
                                      variant="outlined"
                                      sx={{
                                        borderColor:
                                          BIAS_COLORS[item.bias] ??
                                          BIAS_COLORS.auto,
                                        color:
                                          BIAS_COLORS[item.bias] ??
                                          BIAS_COLORS.auto,
                                        fontWeight: 600,
                                        fontSize: "0.7rem",
                                      }}
                                    />
                                  </TableCell>
                                  <TableCell align="right">
                                    <IconButton
                                      size="small"
                                      color="error"
                                      onClick={() => handleDeleteItem(item.id)}
                                    >
                                      <DeleteOutlineIcon fontSize="small" />
                                    </IconButton>
                                  </TableCell>
                                </TableRow>
                              )),
                            )}
                          </TableBody>
                        </Table>
                      ) : (
                        <Typography
                          variant="body2"
                          sx={{ color: "text.secondary", py: 2 }}
                        >
                          暂无标的，使用下方表单添加。
                        </Typography>
                      )}

                      {/* Add item form */}
                      <Box
                        sx={{
                          display: "flex",
                          gap: 1,
                          mt: 2,
                          alignItems: "center",
                          flexWrap: "wrap",
                        }}
                      >
                        <TextField
                          size="small"
                          label="Symbol"
                          value={addSymbol}
                          onChange={(e) =>
                            setAddSymbol(e.target.value.toUpperCase())
                          }
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleAddItem(wl.id);
                          }}
                          sx={{
                            width: 120,
                            "& input": {
                              fontFamily: "var(--font-geist-mono)",
                              fontWeight: 700,
                            },
                          }}
                        />
                        <FormControl size="small" sx={{ minWidth: 130 }}>
                          <InputLabel>Sector</InputLabel>
                          <Select
                            value={addSector}
                            label="Sector"
                            onChange={(e) => setAddSector(e.target.value)}
                          >
                            {SECTORS.map((s) => (
                              <MenuItem key={s} value={s}>
                                {s}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                        <FormControl size="small" sx={{ minWidth: 100 }}>
                          <InputLabel>Bias</InputLabel>
                          <Select
                            value={addBias}
                            label="Bias"
                            onChange={(e) => setAddBias(e.target.value)}
                          >
                            {BIAS_OPTIONS.map((b) => (
                              <MenuItem key={b} value={b}>
                                {b}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                        <Button
                          variant="outlined"
                          size="small"
                          startIcon={<AddIcon />}
                          onClick={() => handleAddItem(wl.id)}
                          disabled={!addSymbol.trim() || adding}
                        >
                          添加
                        </Button>
                      </Box>
                    </Box>
                  </Collapse>
                </Card>
              </Grid>
            );
          })}
        </Grid>
      )}

      {/* Create dialog */}
      <Dialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>新建自选列表</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="名称"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            sx={{ mt: 1, mb: 2 }}
          />
          <TextField
            fullWidth
            label="描述（可选）"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            multiline
            rows={2}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>取消</Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={!newName.trim() || creating}
          >
            创建
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
      >
        <DialogTitle>确认删除</DialogTitle>
        <DialogContent>
          <DialogContentText>
            确定要删除自选列表「{deleteTarget?.name}」吗？此操作不可撤销。
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)}>取消</Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleDelete}
            disabled={deleting}
          >
            删除
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
