import { useState } from "react";
import MarketPulse from "./MarketPulse";
import { C } from "./colors";

const FONT = "'JetBrains Mono', monospace";

const TABS = [
  { id: "pulse", label: "Market Pulse" },
  { id: "cohort", label: "Cohort & Forced Liq." },
  { id: "scenario", label: "Scenario Tracker" },
  { id: "history", label: "Historical Compare" },
];

function Placeholder({ name }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
      height: 400, color: C.dim, fontFamily: FONT, fontSize: 14 }}>
      {name} — Phase 2~4 구현 예정
    </div>
  );
}

export default function KospiApp() {
  const [tab, setTab] = useState("pulse");

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, fontFamily: FONT }}>
      {/* ── Tab Bar ── */}
      <div style={{
        display: "flex", gap: 2, padding: "8px 16px",
        background: C.panel, borderBottom: `1px solid ${C.border}`,
        position: "sticky", top: 40, zIndex: 100,
      }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            background: tab === t.id ? C.kospi : "transparent",
            color: tab === t.id ? "#fff" : C.muted,
            border: "none", borderRadius: 6, padding: "6px 14px",
            fontSize: 11, fontWeight: 600, cursor: "pointer", fontFamily: FONT,
            transition: "all 0.15s",
          }}>{t.label}</button>
        ))}
      </div>

      {/* ── Tab Content ── */}
      <div style={{ padding: "16px" }}>
        {tab === "pulse" && <MarketPulse />}
        {tab === "cohort" && <Placeholder name="Cohort & Forced Liquidation" />}
        {tab === "scenario" && <Placeholder name="Scenario Tracker" />}
        {tab === "history" && <Placeholder name="Historical Comparison" />}
      </div>
    </div>
  );
}
