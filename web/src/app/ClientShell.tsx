"use client";

import Box from "@mui/material/Box";
import Sidebar from "@/components/Sidebar";

export default function ClientShell({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <Sidebar />
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          minHeight: "100vh",
          bgcolor: "background.default",
        }}
      >
        {children}
      </Box>
    </Box>
  );
}
