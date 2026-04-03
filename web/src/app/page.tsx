"use client";

import Box from "@mui/material/Box";
import Sidebar from "@/components/Sidebar";
import HeroBanner from "@/components/HeroBanner";
import RegimeSection from "@/components/RegimeSection";
import SignalsSection from "@/components/SignalsSection";
import IndicatorsSection from "@/components/IndicatorsSection";
import ChartsSection from "@/components/ChartsSection";
import CompareSection from "@/components/CompareSection";

const DRAWER_WIDTH = 240;

export default function HomePage() {
  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <Sidebar />
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          ml: `${DRAWER_WIDTH}px`,
          minHeight: "100vh",
          bgcolor: "background.default",
        }}
      >
        <HeroBanner />
        <Box sx={{ px: 4, py: 4 }}>
          <RegimeSection />
          <SignalsSection />
          <IndicatorsSection />
          <ChartsSection />
          <CompareSection />
        </Box>
      </Box>
    </Box>
  );
}
