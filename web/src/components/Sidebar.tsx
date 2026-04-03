"use client";

import { useState, useEffect } from "react";
import Drawer from "@mui/material/Drawer";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import PublicIcon from "@mui/icons-material/Public";
import SignalCellularAltIcon from "@mui/icons-material/SignalCellularAlt";
import BarChartIcon from "@mui/icons-material/BarChart";
import CandlestickChartIcon from "@mui/icons-material/CandlestickChart";
import CompareArrowsIcon from "@mui/icons-material/CompareArrows";
import LightModeIcon from "@mui/icons-material/LightMode";
import DarkModeIcon from "@mui/icons-material/DarkMode";
import { useThemeMode } from "./ThemeProvider";
import { fetchHealth } from "@/lib/api";

const DRAWER_WIDTH = 240;

const NAV_ITEMS = [
  { id: "regime", label: "市场环境", Icon: PublicIcon },
  { id: "signals", label: "交易信号", Icon: SignalCellularAltIcon },
  { id: "indicators", label: "技术指标", Icon: BarChartIcon },
  { id: "charts", label: "价格走势", Icon: CandlestickChartIcon },
  { id: "compare", label: "价格对比", Icon: CompareArrowsIcon },
] as const;

type SectionId = (typeof NAV_ITEMS)[number]["id"];

function scrollTo(id: SectionId) {
  const el = document.getElementById(id);
  if (el) {
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

export default function Sidebar() {
  const [active, setActive] = useState<SectionId>("regime");
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">(
    "checking",
  );
  const { mode, toggleMode } = useThemeMode();

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && entry.intersectionRatio >= 0.3) {
            setActive(entry.target.id as SectionId);
          }
        }
      },
      { threshold: 0.3, rootMargin: "-10% 0px -60% 0px" },
    );

    for (const item of NAV_ITEMS) {
      const el = document.getElementById(item.id);
      if (el) observer.observe(el);
    }

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    fetchHealth()
      .then(() => setApiStatus("online"))
      .catch(() => setApiStatus("offline"));
  }, []);

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
      </Box>

      <List sx={{ flex: 1, px: 1.5, py: 2 }}>
        {NAV_ITEMS.map((item) => {
          const isActive = active === item.id;
          const { Icon } = item;
          return (
            <ListItemButton
              key={item.id}
              onClick={() => scrollTo(item.id)}
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
                primaryTypographyProps={{
                  fontSize: "0.875rem",
                  fontWeight: isActive ? 600 : 400,
                  color: "inherit",
                  fontFamily: "var(--font-geist-sans)",
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
              fontSize: "0.65rem",
              color: "rgba(255,255,255,0.35)",
              fontFamily: "var(--font-geist-mono)",
              textTransform: "uppercase",
            }}
          >
            API
          </Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            <Box
              sx={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                bgcolor: statusColor,
              }}
            />
            <Typography
              sx={{
                fontSize: "0.65rem",
                color: statusColor,
                fontFamily: "var(--font-geist-mono)",
              }}
            >
              {statusLabel}
            </Typography>
          </Box>
        </Box>
        <Typography
          sx={{
            fontSize: "0.6rem",
            color: "rgba(255,255,255,0.25)",
            fontFamily: "var(--font-geist-mono)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {process.env.NEXT_PUBLIC_API_URL ?? "localhost:8200"}
        </Typography>
      </Box>
    </Drawer>
  );
}
