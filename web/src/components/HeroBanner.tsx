"use client";

import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { useThemeMode } from "./ThemeProvider";

export default function HeroBanner() {
  const { mode } = useThemeMode();

  const gradient =
    mode === "dark"
      ? "linear-gradient(135deg, #060a12 0%, #0a1628 50%, #1a3a6e 100%)"
      : "linear-gradient(135deg, #0f2246 0%, #1a3a6e 50%, #3b89ff 100%)";

  return (
    <Box
      sx={{
        background: gradient,
        px: 5,
        py: 5,
        mb: 0,
        width: "100%",
        transition: "background 0.3s ease",
      }}
    >
      <Typography
        variant="caption"
        sx={{
          color: "rgba(255,255,255,0.6)",
          fontSize: "0.7rem",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.12em",
          display: "block",
          mb: 0.5,
        }}
      >
        Options Signal System
      </Typography>
      <Typography
        variant="h4"
        sx={{
          color: "#ffffff",
          fontWeight: 700,
          fontSize: "1.75rem",
          mb: 0.5,
        }}
      >
        期权信号仪表盘
      </Typography>
      <Typography
        variant="body2"
        sx={{ color: "rgba(255,255,255,0.65)", fontSize: "0.875rem" }}
      >
        Rule-based options trading signal scanner —
        规则驱动的期权交易信号扫描系统
      </Typography>
    </Box>
  );
}
