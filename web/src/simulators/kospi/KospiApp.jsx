import { useState } from "react";
import MarketPulse from "./MarketPulse";
import CohortAnalysis from "./CohortAnalysis";
import CrisisAnalysis from "./CrisisAnalysis";
import HistoricalComp from "./HistoricalComp";
import RawDataTable from "./RawDataTable";
import KospiHeader from "./KospiHeader";
import { C } from "./colors";

const FONT = "'JetBrains Mono', monospace";

const TABS = [
  { id: "pulse", label: "시장 현황 (Market Pulse)" },
  { id: "cohort", label: "코호트 분석 (Cohort)" },
  { id: "scenario", label: "위기 분석 (Crisis)", disabled: true },
  { id: "history", label: "과거 비교 (History)", disabled: true },
  { id: "rawdata", label: "원시 데이터 (Raw Data)" },
];

export default function KospiApp() {
  const [tab, setTab] = useState("pulse");

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, fontFamily: FONT }}>
      {/* ── Common Header (탭 전환 시에도 항상 표시) ── */}
      <KospiHeader />

      {/* ── Tab Bar ── */}
      <div style={{
        display: "flex", gap: 2, padding: "6px 16px",
        background: C.panel, borderBottom: `1px solid ${C.border}`,
        position: "sticky", top: 76, zIndex: 99,
      }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => !t.disabled && setTab(t.id)} style={{
            background: tab === t.id ? C.kospi : "transparent",
            color: t.disabled ? C.dim : tab === t.id ? "#fff" : C.muted,
            border: "none", borderRadius: 6, padding: "6px 14px",
            fontSize: 11, fontWeight: 600, cursor: t.disabled ? "not-allowed" : "pointer", fontFamily: FONT,
            transition: "all 0.15s",
            opacity: t.disabled ? 0.4 : 1,
          }}>{t.label}{t.disabled ? " (준비중)" : ""}</button>
        ))}
      </div>

      {/* ── Tab Content ── */}
      <div style={{ padding: "16px" }}>
        {tab === "pulse" && <MarketPulse />}
        {tab === "cohort" && <CohortAnalysis />}
        {tab === "scenario" && <CrisisAnalysis />}
        {tab === "history" && <HistoricalComp />}
        {tab === "rawdata" && <RawDataTable />}
      </div>
    </div>
  );
}
