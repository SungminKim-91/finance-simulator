import { useState, useMemo } from "react";
import {
  LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import { C } from "./colors";
import { TERM } from "./shared/terms";
import { HISTORICAL } from "./data/kospi_data";

const FONT = "'JetBrains Mono', monospace";
const CASE_COLORS = [C.muted, C.s2, C.s3, C.s4, C.s5];

/* -- Sub-components -- */

function PanelBox({ children, style }) {
  return (
    <div style={{
      background: C.panel, border: `1px solid ${C.border}`,
      borderRadius: 10, padding: 18, marginBottom: 14, ...style,
    }}>{children}</div>
  );
}

function SectionTitle({ children }) {
  return (
    <div style={{ color: C.text, fontSize: 15, fontWeight: 700, marginBottom: 10, fontFamily: FONT }}>
      {children}
    </div>
  );
}

function GuideBox({ children }) {
  return (
    <div style={{
      background: "rgba(59,130,246,0.08)", border: "1px solid rgba(59,130,246,0.2)",
      borderRadius: 8, padding: "12px 14px", marginBottom: 12,
      fontSize: 12, color: C.muted, lineHeight: 1.7, fontFamily: FONT,
    }}>{children}</div>
  );
}

const axisProps = { stroke: C.dim, fontSize: 11, fontFamily: FONT };

/* -- Overlay Tooltip -- */

function OverlayTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: C.panel, border: `1px solid ${C.border}`,
      borderRadius: 8, padding: "8px 12px", fontSize: 11, fontFamily: FONT,
    }}>
      <div style={{ color: C.muted, marginBottom: 3 }}>D+{label}</div>
      {payload.map((entry) => (
        <div key={entry.dataKey} style={{ color: entry.color, marginBottom: 2 }}>
          {entry.name}: {entry.value?.toFixed(2) ?? "—"}%
        </div>
      ))}
    </div>
  );
}

/* -- Similarity Bar -- */

function SimBar({ label, value, color }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{
        display: "flex", justifyContent: "space-between",
        fontSize: 12, color: C.muted, marginBottom: 3,
      }}>
        <span>{label}</span>
        <span style={{ color: C.text, fontWeight: 700 }}>{(value * 100).toFixed(0)}%</span>
      </div>
      <div style={{ background: C.bg, borderRadius: 4, height: 8, overflow: "hidden" }}>
        <div style={{
          width: `${value * 100}%`, height: "100%", background: color,
          borderRadius: 4, transition: "width 0.3s",
        }} />
      </div>
    </div>
  );
}

/* ===============================================
   Main Component
   =============================================== */

export default function HistoricalComp() {
  const { cases = [], similarities = {}, overlay = [], indicator_comparison = [] } = HISTORICAL;

  // Find the best-matching case
  const sortedCases = useMemo(() => {
    return [...cases]
      .map(c => ({ ...c, sim: similarities[c.id] || { dtw: 0, cosine: 0, hybrid: 0 } }))
      .sort((a, b) => b.sim.hybrid - a.sim.hybrid);
  }, [cases, similarities]);

  const [selectedIdx, setSelectedIdx] = useState(0);
  const selected = sortedCases[selectedIdx] || null;
  const sim = selected?.sim || { dtw: 0, cosine: 0, hybrid: 0 };

  // Dynamic overlay key
  const overlayKey = selected ? `${selected.id}_pct` : null;

  if (!cases.length) {
    return (
      <PanelBox>
        <SectionTitle>과거 사례 유사도 (Historical Similarity)</SectionTitle>
        <div style={{ color: C.dim, fontSize: 12, padding: 20, textAlign: "center" }}>
          과거 사례 데이터가 없습니다. compute_models.py를 실행해주세요.
        </div>
      </PanelBox>
    );
  }

  return (
    <div>
      {/* ================================================
          Section 1: Similarity Score Card
          ================================================ */}
      <PanelBox>
        <SectionTitle>과거 사례 유사도 (Historical Similarity)</SectionTitle>
        <GuideBox>
          현재 시장 상황과 과거 위기 사례를 DTW(시계열 형태 매칭)와
          코사인 유사도(방향 일치)로 비교합니다.
          종합 유사도 = DTW 60% + Cosine 40% 가중 합산.
        </GuideBox>

        {/* Case selector */}
        <div style={{ display: "flex", gap: 6, marginBottom: 14, flexWrap: "wrap" }}>
          {sortedCases.map((c, i) => (
            <button key={c.id} onClick={() => setSelectedIdx(i)} style={{
              background: selectedIdx === i ? C.kospi : "transparent",
              color: selectedIdx === i ? "#fff" : C.muted,
              border: `1px solid ${selectedIdx === i ? C.kospi : C.border}`,
              borderRadius: 6, padding: "5px 12px",
              fontSize: 11, fontWeight: 600, cursor: "pointer", fontFamily: FONT,
            }}>
              {c.name} ({(c.sim.hybrid * 100).toFixed(0)}%)
            </button>
          ))}
        </div>

        {selected && (
          <div style={{
            background: C.bg, border: `1px solid ${C.border}`, borderRadius: 10,
            padding: "16px 20px",
          }}>
            <div style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              marginBottom: 12,
            }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: C.text, fontFamily: FONT }}>
                  {selected.name}
                </div>
                <div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>
                  고점: {selected.peak_date} (KOSPI {selected.peak_kospi?.toLocaleString()})
                </div>
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, color: C.kospi, fontFamily: FONT }}>
                {(sim.hybrid * 100).toFixed(0)}%
              </div>
            </div>

            <SimBar label="DTW 유사도" value={sim.dtw} color={C.s2} />
            <SimBar label="코사인 유사도" value={sim.cosine} color={C.s3} />
            <SimBar label="종합 유사도 (DTW 60% + Cosine 40%)" value={sim.hybrid} color={C.kospi} />

            <div style={{
              display: "flex", gap: 16, marginTop: 12,
              fontSize: 12, color: C.muted, fontFamily: FONT,
            }}>
              <span>저점: <span style={{ color: C.text }}>{selected.bottom_kospi?.toLocaleString()}</span></span>
              <span>하락폭: <span style={{ color: C.danger }}>{selected.drop_pct}%</span></span>
              <span>회복: <span style={{ color: C.safe }}>{selected.recovery_days > 0 ? `${selected.recovery_days}일` : "미회복"}</span></span>
            </div>
          </div>
        )}
      </PanelBox>

      {/* ================================================
          Section 2: Overlay Chart
          ================================================ */}
      <PanelBox>
        <SectionTitle>오버레이 차트 (Overlay)</SectionTitle>
        <GuideBox>
          고점 대비 경과일 기준으로 현재 시장과 과거 사례를 겹쳐 비교합니다.
          Y축은 고점 대비 변화율(%)이며, 0% = 고점, 음수 = 하락을 의미합니다.
        </GuideBox>

        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={overlay} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
            <XAxis dataKey="day" {...axisProps}
              label={{ value: "고점 대비 경과일 (D+)", position: "insideBottom", offset: -2,
                style: { fill: C.muted, fontSize: 10 } }} />
            <YAxis {...axisProps} tickFormatter={(v) => `${v}%`}
              label={{ value: "변화율 (%)", angle: -90, position: "insideLeft",
                style: { fill: C.muted, fontSize: 10 } }} />
            <ReferenceLine y={0} stroke={C.dim} strokeDasharray="3 3" />
            <Tooltip content={<OverlayTooltip />} cursor={false} wrapperStyle={{ outline: "none" }} />
            <Line type="monotone" dataKey="current_pct" name="현재 (2025~2026)"
              stroke={C.kospi} strokeWidth={2.5} dot={false} />
            {overlayKey && (
              <Line type="monotone" dataKey={overlayKey}
                name={selected?.name || "과거 사례"}
                stroke={C.muted} strokeWidth={1.5} strokeDasharray="5 3" dot={false} />
            )}
          </LineChart>
        </ResponsiveContainer>

        <div style={{
          display: "flex", gap: 16, justifyContent: "center", marginTop: 8,
          fontSize: 11, fontFamily: FONT,
        }}>
          <span style={{ color: C.kospi }}>{"\u2501\u2501"} 현재 (2025~2026)</span>
          {selected && <span style={{ color: C.muted }}>{"\u2505\u2505"} {selected.name}</span>}
        </div>
      </PanelBox>

      {/* ================================================
          Section 3: Indicator Comparison Table
          ================================================ */}
      {indicator_comparison.length > 0 && (
        <PanelBox>
          <SectionTitle>지표 비교 (Indicator Comparison)</SectionTitle>
          <GuideBox>
            현재 시장의 주요 지표 값입니다. 각 지표의 raw 값을 확인할 수 있습니다.
          </GuideBox>

          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: FONT }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  {["지표", "현재 값"].map((h) => (
                    <th key={h} style={{
                      padding: "8px 10px", textAlign: h === "지표" ? "left" : "right",
                      color: C.muted, fontWeight: 600, fontSize: 11,
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {indicator_comparison.map((row) => (
                  <tr key={row.indicator} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td style={{ padding: "8px 10px", color: C.text }}>{row.label}</td>
                    <td style={{
                      padding: "8px 10px", textAlign: "right", color: C.text, fontWeight: 600,
                    }}>
                      {typeof row.current === "number"
                        ? (Math.abs(row.current) >= 100 ? row.current.toFixed(0) : row.current.toFixed(2))
                        : row.current}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </PanelBox>
      )}
    </div>
  );
}
