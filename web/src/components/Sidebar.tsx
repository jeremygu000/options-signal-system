"use client";

import { useState, useEffect, useCallback } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import Drawer from "@mui/material/Drawer";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import DashboardIcon from "@mui/icons-material/Dashboard";
import CompareArrowsIcon from "@mui/icons-material/CompareArrows";
import AccountBalanceIcon from "@mui/icons-material/AccountBalance";
import ExploreIcon from "@mui/icons-material/Explore";
import FolderSpecialIcon from "@mui/icons-material/FolderSpecial";
import LightModeIcon from "@mui/icons-material/LightMode";
import DarkModeIcon from "@mui/icons-material/DarkMode";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useThemeMode } from "./ThemeProvider";
import { fetchHealth } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";

const DRAWER_WIDTH = 240;

const NAV_ITEMS = [
  { href: "/", label: "信号看板", sublabel: "Dashboard", Icon: DashboardIcon },
  {
    href: "/discover",
    label: "标的发现",
    sublabel: "Discover",
    Icon: ExploreIcon,
  },
  {
    href: "/compare",
    label: "价格对比",
    sublabel: "Compare",
    Icon: CompareArrowsIcon,
  },
  {
    href: "/options",
    label: "期权工具",
    sublabel: "Options",
    Icon: AccountBalanceIcon,
  },
  {
    href: "/positions",
    label: "持仓管理",
    sublabel: "Positions",
    Icon: FolderSpecialIcon,
  },
];

function isNavActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href);
}

export default function Sidebar() {
  const pathname = usePathname();
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">(
    "checking",
  );
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const { mode, toggleMode } = useThemeMode();

  const checkHealth = useCallback(async () => {
    const start = performance.now();
    try {
      const data = await fetchHealth();
      const elapsed = Math.round(performance.now() - start);
      setApiStatus("online");
      setLatencyMs(elapsed);
      setHealthData(data);
      setLastChecked(new Date());
    } catch {
      setApiStatus("offline");
      setLatencyMs(null);
      setHealthData(null);
      setLastChecked(new Date());
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30_000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  const statusColor =
    apiStatus === "online"
      ? "#36bb80"
      : apiStatus === "offline"
        ? "#ff7134"
        : "#fdbc2a";
  const statusLabel =
    apiStatus === "online"
      ? "Live"
      : apiStatus === "offline"
        ? "Offline"
        : "...";

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: DRAWER_WIDTH,
        flexShrink: 0,
        "& .MuiDrawer-paper": {
          width: DRAWER_WIDTH,
          bgcolor: "#0f2246",
        },
      }}
    >
      <Box
        sx={{
          px: 2.5,
          py: 2.5,
          borderBottom: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <Link href="/" style={{ textDecoration: "none" }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <Box
              sx={{
                width: 32,
                height: 32,
                borderRadius: "8px",
                background: "linear-gradient(135deg, #3b89ff 0%, #1a6fe0 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <Typography
                sx={{ color: "#fff", fontWeight: 800, fontSize: "0.875rem" }}
              >
                O
              </Typography>
            </Box>
            <Box>
              <Typography
                sx={{
                  color: "#ffffff",
                  fontWeight: 700,
                  fontSize: "0.85rem",
                  lineHeight: 1.2,
                }}
              >
                Options Signal
              </Typography>
              <Typography
                sx={{
                  color: "rgba(255,255,255,0.4)",
                  fontSize: "0.65rem",
                  fontFamily: "var(--font-geist-mono)",
                }}
              >
                v1.0.0
              </Typography>
            </Box>
          </Box>
        </Link>
      </Box>

      <List sx={{ flex: 1, px: 1.5, py: 2 }}>
        {NAV_ITEMS.map((item) => {
          const isActive = isNavActive(pathname, item.href);
          const { Icon } = item;
          return (
            <ListItemButton
              key={item.href}
              component={Link}
              href={item.href}
              selected={isActive}
              sx={{
                borderRadius: "8px",
                mb: 0.5,
                px: 1.5,
                py: 1,
                color: isActive ? "#3b89ff" : "rgba(255,255,255,0.55)",
                bgcolor: isActive
                  ? "rgba(59,137,255,0.12) !important"
                  : "transparent",
                "&:hover": {
                  bgcolor: "rgba(255,255,255,0.06) !important",
                  color: "rgba(255,255,255,0.85)",
                },
                "&.Mui-selected": {
                  bgcolor: "rgba(59,137,255,0.12)",
                },
                textDecoration: "none",
              }}
            >
              <ListItemIcon
                sx={{
                  minWidth: 36,
                  color: isActive ? "#3b89ff" : "rgba(255,255,255,0.4)",
                }}
              >
                <Icon sx={{ fontSize: "1.1rem" }} />
              </ListItemIcon>
              <ListItemText
                primary={item.label}
                secondary={item.sublabel}
                primaryTypographyProps={{
                  fontSize: "0.875rem",
                  fontWeight: isActive ? 600 : 400,
                  color: "inherit",
                  fontFamily: "var(--font-geist-sans)",
                }}
                secondaryTypographyProps={{
                  fontSize: "0.65rem",
                  color: isActive
                    ? "rgba(59,137,255,0.6)"
                    : "rgba(255,255,255,0.3)",
                  fontFamily: "var(--font-geist-mono)",
                }}
              />
              {isActive && (
                <Box
                  sx={{
                    width: 3,
                    height: 20,
                    borderRadius: "2px",
                    bgcolor: "#3b89ff",
                    ml: 1,
                  }}
                />
              )}
            </ListItemButton>
          );
        })}
      </List>

      <Divider sx={{ borderColor: "rgba(255,255,255,0.08)" }} />

      <Box
        sx={{
          px: 2,
          py: 1.5,
          borderBottom: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Typography
            sx={{
              fontSize: "0.65rem",
              color: "rgba(255,255,255,0.35)",
              fontFamily: "var(--font-geist-mono)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            {mode === "light" ? "Light" : "Dark"}
          </Typography>
          <IconButton
            onClick={toggleMode}
            size="small"
            sx={{
              color: mode === "light" ? "#fdbc2a" : "#6aaeff",
              "&:hover": {
                bgcolor: "rgba(255,255,255,0.08)",
              },
              p: 0.75,
            }}
            aria-label={
              mode === "light" ? "Switch to dark mode" : "Switch to light mode"
            }
          >
            {mode === "light" ? (
              <LightModeIcon sx={{ fontSize: "1rem" }} />
            ) : (
              <DarkModeIcon sx={{ fontSize: "1rem" }} />
            )}
          </IconButton>
        </Box>
      </Box>

      <Box sx={{ px: 2.5, py: 2 }}>
        {/* Header row: API label + status dot + retry */}
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            mb: 1,
          }}
        >
          <Typography
            sx={{
              fontSize: "0.65rem",
              color: "rgba(255,255,255,0.35)",
              fontFamily: "var(--font-geist-mono)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            API
          </Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
            <Box
              sx={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                bgcolor: statusColor,
                ...(apiStatus === "online" && {
                  boxShadow: `0 0 6px 2px ${statusColor}60`,
                  animation: "pulse-dot 2s ease-in-out infinite",
                  "@keyframes pulse-dot": {
                    "0%, 100%": {
                      opacity: 1,
                      boxShadow: `0 0 6px 2px ${statusColor}60`,
                    },
                    "50%": {
                      opacity: 0.7,
                      boxShadow: `0 0 2px 1px ${statusColor}30`,
                    },
                  },
                }),
                ...(apiStatus === "checking" && {
                  animation: "blink 1s ease-in-out infinite",
                  "@keyframes blink": {
                    "0%, 100%": { opacity: 1 },
                    "50%": { opacity: 0.3 },
                  },
                }),
              }}
            />
            <Typography
              sx={{
                fontSize: "0.65rem",
                color: statusColor,
                fontFamily: "var(--font-geist-mono)",
                fontWeight: 600,
              }}
            >
              {statusLabel}
            </Typography>
            {apiStatus === "offline" && (
              <Tooltip title="重试 Retry" arrow>
                <IconButton
                  onClick={checkHealth}
                  size="small"
                  sx={{
                    color: "rgba(255,255,255,0.4)",
                    p: 0.25,
                    "&:hover": {
                      color: "#3b89ff",
                      bgcolor: "rgba(255,255,255,0.06)",
                    },
                  }}
                  aria-label="Retry health check"
                >
                  <RefreshIcon sx={{ fontSize: "0.85rem" }} />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        </Box>

        {/* Latency + version row */}
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            mb: 0.5,
          }}
        >
          <Typography
            sx={{
              fontSize: "0.6rem",
              color: "rgba(255,255,255,0.25)",
              fontFamily: "var(--font-geist-mono)",
            }}
          >
            {process.env.NEXT_PUBLIC_API_URL ?? "localhost:8400"}
          </Typography>
          {latencyMs !== null && (
            <Typography
              sx={{
                fontSize: "0.6rem",
                color:
                  latencyMs < 200
                    ? "#36bb80"
                    : latencyMs < 500
                      ? "#fdbc2a"
                      : "#ff7134",
                fontFamily: "var(--font-geist-mono)",
              }}
            >
              {latencyMs}ms
            </Typography>
          )}
        </Box>

        {/* Data status pills */}
        {healthData && healthData.data_status && (
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mb: 0.75 }}>
            {Object.entries(healthData.data_status).map(([key, ok]) => (
              <Box
                key={key}
                sx={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 0.4,
                  px: 0.75,
                  py: 0.15,
                  borderRadius: "4px",
                  bgcolor: ok
                    ? "rgba(54,187,128,0.12)"
                    : "rgba(255,113,52,0.12)",
                }}
              >
                <Box
                  sx={{
                    width: 4,
                    height: 4,
                    borderRadius: "50%",
                    bgcolor: ok ? "#36bb80" : "#ff7134",
                  }}
                />
                <Typography
                  sx={{
                    fontSize: "0.55rem",
                    color: ok ? "rgba(54,187,128,0.9)" : "rgba(255,113,52,0.9)",
                    fontFamily: "var(--font-geist-mono)",
                    textTransform: "uppercase",
                  }}
                >
                  {key}
                </Typography>
              </Box>
            ))}
          </Box>
        )}

        {/* Version + last checked */}
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          {healthData?.version && (
            <Typography
              sx={{
                fontSize: "0.55rem",
                color: "rgba(255,255,255,0.2)",
                fontFamily: "var(--font-geist-mono)",
              }}
            >
              {healthData.version}
            </Typography>
          )}
          {lastChecked && (
            <Typography
              sx={{
                fontSize: "0.55rem",
                color: "rgba(255,255,255,0.18)",
                fontFamily: "var(--font-geist-mono)",
              }}
            >
              {lastChecked.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </Typography>
          )}
        </Box>
      </Box>
    </Drawer>
  );
}
