import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import Divider from "@mui/material/Divider";

interface SectionHeaderProps {
  number: string;
  title: string;
  subtitle?: string;
}

export default function SectionHeader({
  number,
  title,
  subtitle,
}: SectionHeaderProps) {
  return (
    <Box sx={{ mb: 3 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 1.5 }}>
        <Chip
          label={number}
          size="small"
          sx={{
            bgcolor: "primary.main",
            color: "white",
            fontFamily: "var(--font-geist-mono)",
            fontWeight: 700,
            fontSize: "0.7rem",
            height: 22,
            borderRadius: "4px",
          }}
        />
        <Typography variant="h6" sx={{ fontWeight: 700, fontSize: "1.1rem" }}>
          {title}
        </Typography>
        {subtitle && (
          <Typography
            variant="body2"
            sx={{ color: "text.secondary", fontSize: "0.8rem" }}
          >
            {subtitle}
          </Typography>
        )}
      </Box>
      <Divider />
    </Box>
  );
}
