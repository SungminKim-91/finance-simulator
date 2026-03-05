/* ── KOSPI Crisis Detector Color Palette ── */
export const C = {
  bg: "#020617", panel: "#0f172a", border: "#1e293b", borderHi: "#334155",
  text: "#e2e8f0", muted: "#94a3b8", dim: "#64748b",
  green: "#4ade80", red: "#f87171", yellow: "#facc15",

  kospi: "#ef4444", samsung: "#3b82f6", hynix: "#8b5cf6",
  individual: "#f59e0b", foreign: "#06b6d4", institution: "#10b981",
  credit: "#f97316", deposit: "#22d3ee", forcedLiq: "#dc2626",

  safe: "#4ade80", watch: "#facc15", marginCall: "#fb923c", danger: "#ef4444",
  s1: "#4ade80", s2: "#60a5fa", s3: "#f97316", s4: "#ef4444", s5: "#991b1b",

  /* 6-stage cohort status (v1.6.0) */
  safe6: "#4caf50", good6: "#8bc34a", caution6: "#ffc107",
  marginCall6: "#ff9800", forcedLiq6: "#ff5252", debtExceed6: "#ff1744",

  /* RSPI variable colors (v2.2.0) — 5-variable + Volume Amplifier */
  rspiV1: "#ef5350",   // Red - cohort proximity
  rspiV2: "#42a5f5",   // Blue - foreign flow
  rspiV3: "#4caf50",   // Green - overnight
  rspiV4: "#ec4899",   // Pink - individual flow
  rspiV5: "#ab47bc",   // Purple - credit momentum
  rspiVA: "#78909c",   // Blue Grey - volume amplifier
};
