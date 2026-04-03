"use client";

import Box from "@mui/material/Box";
import HeroBanner from "@/components/HeroBanner";
import CompareSection from "@/components/CompareSection";

export default function ComparePage() {
  return (
    <>
      <HeroBanner />
      <Box sx={{ px: 4, py: 4 }}>
        <CompareSection />
      </Box>
    </>
  );
}
