"use client";

import { createContext, useContext, useState, useEffect, useMemo } from "react";
import {
  createTheme,
  ThemeProvider as MuiThemeProvider,
} from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import EmotionCacheProvider from "./EmotionCacheProvider";

interface ThemeContextValue {
  mode: "light" | "dark";
  toggleMode: () => void;
}

export const ThemeContext = createContext<ThemeContextValue>({
  mode: "light",
  toggleMode: () => {},
});

export function useThemeMode(): ThemeContextValue {
  return useContext(ThemeContext);
}

const lightTheme = createTheme({
  palette: {
    mode: "light",
    background: {
      default: "#f8f9fb",
      paper: "#ffffff",
    },
    primary: {
      main: "#3b89ff",
      dark: "#1a6fe0",
      light: "#6aaeff",
      contrastText: "#ffffff",
    },
    secondary: {
      main: "#0f2246",
      dark: "#081530",
      light: "#1e3a6e",
      contrastText: "#ffffff",
    },
    text: {
      primary: "#00162f",
      secondary: "#627183",
      disabled: "#8190b5",
    },
    success: {
      main: "#36bb80",
      light: "#5dd9a0",
      dark: "#2a9264",
    },
    error: {
      main: "#ff7134",
      light: "#ff9463",
      dark: "#d95620",
    },
    warning: {
      main: "#fdbc2a",
      light: "#fdd06a",
      dark: "#d49a14",
    },
    divider: "#e5e9ef",
  },
  typography: {
    fontFamily: "var(--font-geist-sans), system-ui, -apple-system, sans-serif",
    h1: { fontWeight: 700, color: "#00162f" },
    h2: { fontWeight: 700, color: "#00162f" },
    h3: { fontWeight: 600, color: "#00162f" },
    h4: { fontWeight: 600, color: "#00162f" },
    h5: { fontWeight: 600, color: "#00162f" },
    h6: { fontWeight: 600, color: "#00162f" },
    body1: { color: "#00162f" },
    body2: { color: "#627183" },
    caption: { color: "#8190b5" },
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)",
          borderRadius: 12,
          border: "none",
        },
      },
    },
    MuiCardContent: {
      styleOverrides: {
        root: {
          "&:last-child": {
            paddingBottom: 16,
          },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          textTransform: "none",
          fontWeight: 500,
          boxShadow: "none",
          "&:hover": {
            boxShadow: "none",
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          fontWeight: 600,
          fontSize: "0.75rem",
        },
      },
    },
    MuiSelect: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          "& .MuiTableCell-root": {
            backgroundColor: "#f1f4f8",
            color: "#627183",
            fontWeight: 600,
            fontSize: "0.75rem",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            borderBottom: "1px solid #e5e9ef",
          },
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          "&:hover": {
            backgroundColor: "#f8f9fb",
          },
          "&:last-child .MuiTableCell-root": {
            borderBottom: "none",
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: "1px solid #f0f2f5",
          padding: "10px 16px",
          fontSize: "0.8125rem",
        },
      },
    },
    MuiToggleButton: {
      styleOverrides: {
        root: {
          borderRadius: "6px !important",
          border: "1px solid #e5e9ef !important",
          textTransform: "none",
          fontSize: "0.75rem",
          fontWeight: 500,
          padding: "4px 12px",
          color: "#627183",
          "&.Mui-selected": {
            backgroundColor: "#3b89ff",
            color: "#ffffff",
            "&:hover": {
              backgroundColor: "#1a6fe0",
            },
          },
        },
      },
    },
    MuiToggleButtonGroup: {
      styleOverrides: {
        root: {
          gap: 4,
          "& .MuiToggleButtonGroup-grouped": {
            borderRadius: "6px !important",
            border: "1px solid #e5e9ef !important",
            margin: 0,
          },
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: {
          borderRadius: 4,
          height: 8,
          backgroundColor: "#f0f2f5",
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: "#0f2246",
          borderRight: "none",
          boxShadow: "2px 0 8px rgba(0,0,0,0.15)",
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: "#e5e9ef",
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          "& .MuiOutlinedInput-notchedOutline": {
            borderColor: "#e5e9ef",
          },
          "&:hover .MuiOutlinedInput-notchedOutline": {
            borderColor: "#b0bec5",
          },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
            borderColor: "#3b89ff",
          },
        },
      },
    },
  },
});

const darkTheme = createTheme({
  palette: {
    mode: "dark",
    background: {
      default: "#0a0e17",
      paper: "#111827",
    },
    primary: {
      main: "#3b89ff",
      dark: "#1a6fe0",
      light: "#6aaeff",
      contrastText: "#ffffff",
    },
    secondary: {
      main: "#0f2246",
      dark: "#081530",
      light: "#1e3a6e",
      contrastText: "#ffffff",
    },
    text: {
      primary: "#e5e9ef",
      secondary: "#8899aa",
      disabled: "#4a5568",
    },
    success: {
      main: "#36bb80",
      light: "#5dd9a0",
      dark: "#2a9264",
    },
    error: {
      main: "#ff7134",
      light: "#ff9463",
      dark: "#d95620",
    },
    warning: {
      main: "#fdbc2a",
      light: "#fdd06a",
      dark: "#d49a14",
    },
    divider: "#1e2a3a",
  },
  typography: {
    fontFamily: "var(--font-geist-sans), system-ui, -apple-system, sans-serif",
    h1: { fontWeight: 700, color: "#e5e9ef" },
    h2: { fontWeight: 700, color: "#e5e9ef" },
    h3: { fontWeight: 600, color: "#e5e9ef" },
    h4: { fontWeight: 600, color: "#e5e9ef" },
    h5: { fontWeight: 600, color: "#e5e9ef" },
    h6: { fontWeight: 600, color: "#e5e9ef" },
    body1: { color: "#e5e9ef" },
    body2: { color: "#8899aa" },
    caption: { color: "#4a5568" },
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
          borderRadius: 12,
          border: "none",
        },
      },
    },
    MuiCardContent: {
      styleOverrides: {
        root: {
          "&:last-child": {
            paddingBottom: 16,
          },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          textTransform: "none",
          fontWeight: 500,
          boxShadow: "none",
          "&:hover": {
            boxShadow: "none",
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          fontWeight: 600,
          fontSize: "0.75rem",
        },
      },
    },
    MuiSelect: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          "& .MuiTableCell-root": {
            backgroundColor: "#111827",
            color: "#8899aa",
            fontWeight: 600,
            fontSize: "0.75rem",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            borderBottom: "1px solid #1e2a3a",
          },
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          "&:hover": {
            backgroundColor: "#0d1525",
          },
          "&:last-child .MuiTableCell-root": {
            borderBottom: "none",
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: "1px solid #1e2a3a",
          padding: "10px 16px",
          fontSize: "0.8125rem",
        },
      },
    },
    MuiToggleButton: {
      styleOverrides: {
        root: {
          borderRadius: "6px !important",
          border: "1px solid #1e2a3a !important",
          textTransform: "none",
          fontSize: "0.75rem",
          fontWeight: 500,
          padding: "4px 12px",
          color: "#8899aa",
          "&.Mui-selected": {
            backgroundColor: "#3b89ff",
            color: "#ffffff",
            "&:hover": {
              backgroundColor: "#1a6fe0",
            },
          },
        },
      },
    },
    MuiToggleButtonGroup: {
      styleOverrides: {
        root: {
          gap: 4,
          "& .MuiToggleButtonGroup-grouped": {
            borderRadius: "6px !important",
            border: "1px solid #1e2a3a !important",
            margin: 0,
          },
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: {
          borderRadius: 4,
          height: 8,
          backgroundColor: "#1e2a3a",
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: "#060a12",
          borderRight: "none",
          boxShadow: "2px 0 8px rgba(0,0,0,0.4)",
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: "#1e2a3a",
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          "& .MuiOutlinedInput-notchedOutline": {
            borderColor: "#1e2a3a",
          },
          "&:hover .MuiOutlinedInput-notchedOutline": {
            borderColor: "#2d3748",
          },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
            borderColor: "#3b89ff",
          },
        },
      },
    },
  },
});

export default function ThemeProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [mode, setMode] = useState<"light" | "dark">("light");

  useEffect(() => {
    const stored = localStorage.getItem("theme-mode");
    if (stored === "dark" || stored === "light") {
      setMode(stored);
    }
  }, []);

  const toggleMode = () => {
    setMode((prev) => {
      const next = prev === "light" ? "dark" : "light";
      localStorage.setItem("theme-mode", next);
      return next;
    });
  };

  const contextValue = useMemo(() => ({ mode, toggleMode }), [mode]);

  const muiTheme = mode === "dark" ? darkTheme : lightTheme;

  return (
    <ThemeContext.Provider value={contextValue}>
      <EmotionCacheProvider>
        <MuiThemeProvider theme={muiTheme}>
          <CssBaseline />
          {children}
        </MuiThemeProvider>
      </EmotionCacheProvider>
    </ThemeContext.Provider>
  );
}
