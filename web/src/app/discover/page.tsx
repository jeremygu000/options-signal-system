"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import TextField from "@mui/material/TextField";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TablePagination from "@mui/material/TablePagination";
import TableSortLabel from "@mui/material/TableSortLabel";
import Skeleton from "@mui/material/Skeleton";
import Alert from "@mui/material/Alert";
import Chip from "@mui/material/Chip";
import InputAdornment from "@mui/material/InputAdornment";
import SearchIcon from "@mui/icons-material/Search";
import SectionHeader from "@/components/SectionHeader";
import { searchSymbols } from "@/lib/api";
import type { PaginatedSymbolResult, SymbolMeta } from "@/lib/types";

// ── Helpers ─────────────────────────────────────────────────────────

type SortKey = "symbol" | "volume" | "rows" | "return" | "last_close";

const SKELETON_ROWS = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"];
const SKELETON_CELLS = ["c1", "c2", "c3", "c4", "c5", "c6"];

function formatVolume(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toFixed(0);
}

function formatReturn(r: number): string {
  const sign = r >= 0 ? "+" : "";
  return `${sign}${(r * 100).toFixed(2)}%`;
}

function returnColor(r: number): string {
  if (r > 0) return "#36bb80";
  if (r < 0) return "#ff7134";
  return "inherit";
}

// ── Component ───────────────────────────────────────────────────────

export default function DiscoverPage() {
  const router = useRouter();

  const [data, setData] = useState<PaginatedSymbolResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [sortBy, setSortBy] = useState<SortKey>("symbol");
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(50);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
      setPage(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const fetchData = useCallback(
    (isInitial: boolean) => {
      if (isInitial) setLoading(true);
      searchSymbols({
        query: debouncedQuery || undefined,
        sort_by: sortBy,
        limit: rowsPerPage,
        offset: page * rowsPerPage,
      })
        .then((res) => {
          setData(res);
          setError(null);
        })
        .catch((e: unknown) =>
          setError(e instanceof Error ? e.message : "Failed to load"),
        )
        .finally(() => {
          if (isInitial) setLoading(false);
        });
    },
    [debouncedQuery, sortBy, page, rowsPerPage],
  );

  const isFirstLoad = useRef(true);
  useEffect(() => {
    fetchData(isFirstLoad.current);
    isFirstLoad.current = false;
  }, [fetchData]);

  const handleSort = (key: SortKey) => {
    setSortBy(key);
    setPage(0);
  };

  // ── Render ──────────────────────────────────────────────────────────

  return (
    <Box sx={{ px: 4, py: 4 }}>
      <SectionHeader number="S" title="标的发现 Symbol Discovery" />

      {/* Search & Stats */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 2,
          mb: 3,
        }}
      >
        <TextField
          size="small"
          placeholder="Search symbol..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon
                    sx={{ fontSize: "1.1rem", color: "text.secondary" }}
                  />
                </InputAdornment>
              ),
            },
          }}
          sx={{ width: 280 }}
        />
        {data && (
          <Chip
            label={`${data.total.toLocaleString()} symbols`}
            size="small"
            variant="outlined"
            sx={{
              fontFamily: "var(--font-geist-mono)",
              fontSize: "0.75rem",
            }}
          />
        )}
      </Box>

      {/* Error */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Table */}
      <Paper variant="outlined" sx={{ borderRadius: 2, overflow: "hidden" }}>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>
                  <TableSortLabel
                    active={sortBy === "symbol"}
                    direction="asc"
                    onClick={() => handleSort("symbol")}
                  >
                    Symbol
                  </TableSortLabel>
                </TableCell>
                <TableCell align="right">
                  <TableSortLabel
                    active={sortBy === "last_close"}
                    direction="desc"
                    onClick={() => handleSort("last_close")}
                  >
                    Last Close
                  </TableSortLabel>
                </TableCell>
                <TableCell align="right">
                  <TableSortLabel
                    active={sortBy === "volume"}
                    direction="desc"
                    onClick={() => handleSort("volume")}
                  >
                    Avg Volume
                  </TableSortLabel>
                </TableCell>
                <TableCell align="right">
                  <TableSortLabel
                    active={sortBy === "return"}
                    direction="desc"
                    onClick={() => handleSort("return")}
                  >
                    1Y Return
                  </TableSortLabel>
                </TableCell>
                <TableCell align="right">
                  <TableSortLabel
                    active={sortBy === "rows"}
                    direction="desc"
                    onClick={() => handleSort("rows")}
                  >
                    Data Rows
                  </TableSortLabel>
                </TableCell>
                <TableCell>Date Range</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading
                ? SKELETON_ROWS.map((rowKey) => (
                    <TableRow key={rowKey}>
                      {SKELETON_CELLS.map((cellKey) => (
                        <TableCell key={`${rowKey}-${cellKey}`}>
                          <Skeleton variant="text" width="80%" />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                : data?.items.map((row: SymbolMeta) => (
                    <TableRow
                      key={row.symbol}
                      hover
                      sx={{ cursor: "pointer" }}
                      onClick={() =>
                        router.push(`/symbol/${row.symbol.toLowerCase()}`)
                      }
                    >
                      <TableCell>
                        <Typography
                          sx={{
                            fontWeight: 600,
                            fontFamily: "var(--font-geist-mono)",
                            fontSize: "0.85rem",
                          }}
                        >
                          {row.symbol}
                        </Typography>
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontFamily: "var(--font-geist-mono)" }}
                      >
                        ${row.last_close.toFixed(2)}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontFamily: "var(--font-geist-mono)" }}
                      >
                        {formatVolume(row.avg_volume)}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          fontFamily: "var(--font-geist-mono)",
                          fontWeight: 600,
                          color: returnColor(row.return_1y),
                        }}
                      >
                        {formatReturn(row.return_1y)}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontFamily: "var(--font-geist-mono)" }}
                      >
                        {row.rows.toLocaleString()}
                      </TableCell>
                      <TableCell>
                        <Typography
                          sx={{
                            fontSize: "0.75rem",
                            color: "text.secondary",
                            fontFamily: "var(--font-geist-mono)",
                          }}
                        >
                          {row.first_date} → {row.last_date}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
              {!loading && data?.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 4 }}>
                    <Typography color="text.secondary">
                      No symbols found
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
        {data && (
          <TablePagination
            component="div"
            count={data.total}
            page={page}
            onPageChange={(_, p) => setPage(p)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={(e) => {
              setRowsPerPage(parseInt(e.target.value, 10));
              setPage(0);
            }}
            rowsPerPageOptions={[25, 50, 100]}
          />
        )}
      </Paper>
    </Box>
  );
}
