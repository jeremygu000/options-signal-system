"use client";

import Box from "@mui/material/Box";
import HeroBanner from "@/components/HeroBanner";
import RegimeSection from "@/components/RegimeSection";
import SignalsSection from "@/components/SignalsSection";
import IndicatorsSection from "@/components/IndicatorsSection";
import ChartsSection from "@/components/ChartsSection";

export default function DashboardPage() {
  return (
    <>
      <HeroBanner />
      <Box sx={{ px: 4, py: 4 }}>
        <RegimeSection />
        <SignalsSection />
        <IndicatorsSection />
        <ChartsSection />
      </Box>
    </>
  );
}
