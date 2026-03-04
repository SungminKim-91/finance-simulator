import { useMemo } from "react";
import {
  LineChart, Line, BarChart, Bar, Cell,
  AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, ReferenceArea,
} from "recharts";
import { C } from "./colors";
import { TERM } from "./shared/terms";
import { CRISIS_SCORE, SCENARIOS, DEFENSE_WALLS, LOOP_STATUS } from "./data/kospi_data";

const FONT = "'JetBrains Mono', monospace";
const SCENARIO_COLORS = { S1: C.s1, S2: C.s2, S3: C.s3, S4: C.s4, S5: C.s5 };

const CLASSIFICATION_LABELS = {
  normal: "정상 (Normal)", caution: "주의 (Caution)",
  warning: "경고 (Warning)", danger: "위험 (Danger)", extreme: "극단 (Extreme)",
};
const CLASSIFICATION_COLORS = {
  normal: C.safe, caution: C.watch, warning: C.marginCall,
  danger: C.danger, extreme: "#991b1b",
};

/* ── Sub-components ── */

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

function SummaryCard({ label, value, color = C.text }) {
  return (
    <div style={{
      background: C.bg, border: `1px solid ${C.border}`, borderRadius: 8,
      padding: "10px 14px", minWidth: 110, textAlign: "center",
    }}>
      <div style={{ fontSize: 11, color: C.muted, marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color, fontFamily: FONT }}>{value}</div>
    </div>
  );
}

const axisProps = { stroke: C.dim, fontSize: 11, fontFamily: FONT };

/* ── SVG Semi-circle Gauge ── */

function CrisisGauge({ score, classification }) {
  const w = 240, h = 135;
  const cx = w / 2, cy = 115, r = 85, sw = 16;

  const toAngle = (s) => Math.PI * (1 - s / 100);

  const describeArc = (s1, s2) => {
    const a1 = toAngle(s1), a2 = toAngle(s2);
    const x1 = cx + r * Math.cos(a1), y1 = cy - r * Math.sin(a1);
    const x2 = cx + r * Math.cos(a2), y2 = cy - r * Math.sin(a2);
    const large = (s2 - s1) > 50 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
  };

  const zones = [
    { min: 0, max: 50, color: C.safe },
    { min: 50, max: 70, color: C.watch },
    { min: 70, max: 85, color: C.marginCall },
    { min: 85, max: 95, color: C.danger },
    { min: 95, max: 100, color: "#991b1b" },
  ];

  const needleAngle = toAngle(score);
  const labelColor = CLASSIFICATION_COLORS[classification] || C.muted;

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <path d={describeArc(0, 100)} fill="none" stroke={C.border} strokeWidth={sw} strokeLinecap="round" />
      {zones.map((z, i) => {
        const end = Math.min(z.max, score);
        if (end <= z.min) return null;
        return <path key={i} d={describeArc(z.min, end)} fill="none"
          stroke={z.color} strokeWidth={sw} strokeLinecap="butt" opacity={0.85} />;
      })}
      <circle cx={cx + r * Math.cos(needleAngle)} cy={cy - r * Math.sin(needleAngle)}
        r={5} fill="#fff" stroke={labelColor} strokeWidth={2} />
      <text x={cx} y={cy - 22} textAnchor="middle" fill={C.text}
        fontSize={34} fontWeight={700} fontFamily={FONT}>{score}</text>
      <text x={cx} y={cy + 2} textAnchor="middle" fill={labelColor}
        fontSize={13} fontWeight={600} fontFamily={FONT}>
        {CLASSIFICATION_LABELS[classification]}
      </text>
    </svg>
  );
}

/* ── Tooltips ── */

function ScoreTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const { score, classification } = payload[0]?.payload || {};
  return (
    <div style={{
      background: C.panel, border: `1px solid ${C.border}`,
      borderRadius: 8, padding: "8px 12px", fontSize: 11, fontFamily: FONT,
    }}>
      <div style={{ color: C.muted, marginBottom: 3 }}>{label}</div>
      <div style={{ color: CLASSIFICATION_COLORS[classification] || C.text, fontWeight: 700 }}>
        {score} — {CLASSIFICATION_LABELS[classification]}
      </div>
    </div>
  );
}

function indicatorColor(v) {
  if (v >= 85) return C.danger;
  if (v >= 70) return C.marginCall;
  if (v >= 50) return C.watch;
  return C.safe;
}

function IndicatorTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  const term = TERM[d.key];
  return (
    <div style={{
      background: C.panel, border: `1px solid ${C.border}`,
      borderRadius: 8, padding: "8px 12px", fontSize: 11, fontFamily: FONT,
    }}>
      <div style={{ color: C.text, fontWeight: 700, marginBottom: 3 }}>
        {term?.label || d.label}
      </div>
      <div style={{ color: C.muted }}>
        백분위: <span style={{ color: indicatorColor(d.value), fontWeight: 700 }}>{d.value}</span>
      </div>
      <div style={{ color: C.muted }}>원시값: {d.raw}</div>
      <div style={{ color: C.dim, fontSize: 10 }}>가중치: {(d.weight * 100).toFixed(0)}%</div>
    </div>
  );
}

function ScenarioTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: C.panel, border: `1px solid ${C.border}`,
      borderRadius: 8, padding: "8px 12px", fontSize: 11, fontFamily: FONT,
    }}>
      <div style={{ color: C.muted, marginBottom: 3 }}>{label}</div>
      {payload.map((entry) => {
        const sc = SCENARIOS.scenarios.find(s => s.id.toLowerCase() === entry.dataKey);
        return (
          <div key={entry.dataKey} style={{ color: entry.color, marginBottom: 2 }}>
            {sc?.name || entry.dataKey}: {(entry.value * 100).toFixed(1)}%
          </div>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   Main Component
   ═══════════════════════════════════════════════════ */

export default function CrisisAnalysis() {
  const { current, classification, indicators, history, weights } = CRISIS_SCORE;
  const { scenarios, probability_history, key_drivers } = SCENARIOS;

  const sortedIndicators = useMemo(() => {
    return Object.entries(indicators)
      .map(([key, v]) => ({ key, label: v.desc, value: v.value, raw: v.raw, weight: weights[key] }))
      .sort((a, b) => b.value - a.value);
  }, [indicators, weights]);

  const prevProbs = useMemo(() => {
    if (probability_history.length < 2) return null;
    return probability_history[probability_history.length - 2];
  }, [probability_history]);

  const lastProbs = useMemo(() => {
    if (!probability_history.length) return null;
    return probability_history[probability_history.length - 1];
  }, [probability_history]);

  return (
    <div>
      {/* ══════════════════════════════════════════
          Section 1: Crisis Score Gauge + History
          ══════════════════════════════════════════ */}
      <PanelBox>
        <SectionTitle>위기 점수 (Crisis Score)</SectionTitle>
        <GuideBox>
          위기 점수란? 14개 시장 지표를 PCA 가중 합산한 종합 위기 지수 (0~100).
          높을수록 시장 스트레스가 크며, 복수 지표가 동시 악화될 때 급상승합니다.
        </GuideBox>

        <div style={{ display: "flex", gap: 20, alignItems: "center", flexWrap: "wrap" }}>
          <CrisisGauge score={current} classification={classification} />

          <div style={{ flex: 1, minWidth: 300 }}>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={history} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                <ReferenceArea y1={0} y2={50} fill={C.safe} fillOpacity={0.06} />
                <ReferenceArea y1={50} y2={70} fill={C.watch} fillOpacity={0.06} />
                <ReferenceArea y1={70} y2={85} fill={C.marginCall} fillOpacity={0.06} />
                <ReferenceArea y1={85} y2={100} fill={C.danger} fillOpacity={0.06} />
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="date" {...axisProps}
                  tickFormatter={(v) => v.slice(5)} interval="preserveStartEnd" />
                <YAxis domain={[0, 100]} {...axisProps} ticks={[0, 50, 70, 85, 100]} />
                <ReferenceLine y={50} stroke={C.safe} strokeDasharray="3 3" strokeOpacity={0.5} />
                <ReferenceLine y={70} stroke={C.watch} strokeDasharray="3 3" strokeOpacity={0.5} />
                <ReferenceLine y={85} stroke={C.danger} strokeDasharray="3 3" strokeOpacity={0.5} />
                <Tooltip content={<ScoreTooltip />} cursor={false} wrapperStyle={{ outline: "none" }} />
                <Line type="monotone" dataKey="score" stroke={C.kospi}
                  strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <SummaryCard label="현재 점수" value={current} color={CLASSIFICATION_COLORS[classification]} />
          <SummaryCard label="등급" value={CLASSIFICATION_LABELS[classification]}
            color={CLASSIFICATION_COLORS[classification]} />
          <SummaryCard label="최고 위험 지표" value={sortedIndicators[0]?.label} color={C.danger} />
          <SummaryCard label="최고 위험 값" value={sortedIndicators[0]?.value} color={C.danger} />
        </div>
      </PanelBox>

      {/* ══════════════════════════════════════════
          Section 2: 13 Indicator Breakdown
          ══════════════════════════════════════════ */}
      <PanelBox>
        <SectionTitle>지표 브레이크다운 (Indicator Breakdown)</SectionTitle>
        <GuideBox>
          14개 지표는 과거 데이터 대비 백분위(0~100)로 변환됩니다.
          높은 값일수록 현재 상태가 과거 대비 극단적임을 의미합니다.
        </GuideBox>

        <ResponsiveContainer width="100%" height={Math.max(300, sortedIndicators.length * 32 + 40)}>
          <BarChart data={sortedIndicators} layout="vertical"
            margin={{ top: 5, right: 60, left: 100, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={C.border} horizontal={false} />
            <XAxis type="number" domain={[0, 100]} {...axisProps} ticks={[0, 25, 50, 75, 100]} />
            <YAxis type="category" dataKey="label" {...axisProps} width={95}
              tick={{ fill: C.muted, fontSize: 11 }} />
            <Tooltip content={<IndicatorTooltip />} cursor={false} wrapperStyle={{ outline: "none" }} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} isAnimationActive={false}
              label={({ x, y, width, height, index }) => (
                <text x={x + width + 6} y={y + height / 2} textAnchor="start"
                  dominantBaseline="central" fill={C.muted} fontSize={11} fontFamily={FONT}>
                  {sortedIndicators[index]?.value}
                </text>
              )}
            >
              {sortedIndicators.map((entry, i) => (
                <Cell key={i} fill={indicatorColor(entry.value)} opacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </PanelBox>

      {/* ══════════════════════════════════════════
          Section 3: Scenario Probabilities
          ══════════════════════════════════════════ */}
      <PanelBox>
        <SectionTitle>시나리오 확률 (Scenario Probabilities)</SectionTitle>
        <GuideBox>
          5개 시나리오의 확률을 베이지안 방법으로 매일 업데이트합니다.
          새로운 데이터(수급, 환율, 반대매매 등)가 들어올 때마다 확률이 갱신됩니다.
        </GuideBox>

        {/* Probability bars */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
          {scenarios.map((sc) => {
            const prob = lastProbs ? lastProbs[sc.id.toLowerCase()] : sc.current_prob;
            const prevProb = prevProbs ? prevProbs[sc.id.toLowerCase()] : prob;
            const delta = prob - prevProb;
            const color = SCENARIO_COLORS[sc.id];
            return (
              <div key={sc.id} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{
                  width: 80, fontSize: 12, color, fontWeight: 600,
                  fontFamily: FONT, textAlign: "right",
                }}>{sc.name}</div>
                <div style={{
                  flex: 1, background: C.bg, borderRadius: 6, height: 24,
                  position: "relative", overflow: "hidden",
                }}>
                  <div style={{
                    width: `${prob * 100}%`, height: "100%", background: color,
                    borderRadius: 6, opacity: 0.7, transition: "width 0.3s",
                  }} />
                  <div style={{
                    position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)",
                    fontSize: 11, color: C.text, fontWeight: 600, fontFamily: FONT,
                  }}>
                    {(prob * 100).toFixed(1)}%
                    {delta !== 0 && (
                      <span style={{
                        marginLeft: 4, fontSize: 10,
                        color: delta > 0 ? C.red : C.green,
                      }}>
                        {delta > 0 ? "\u25B2" : "\u25BC"}{Math.abs(delta * 100).toFixed(1)}
                      </span>
                    )}
                  </div>
                </div>
                <div style={{ width: 120, fontSize: 10, color: C.dim, fontFamily: FONT }}>
                  {sc.kospi_range[0].toLocaleString()}~{sc.kospi_range[1].toLocaleString()}
                </div>
              </div>
            );
          })}
        </div>

        {/* Stacked Area Chart */}
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={probability_history} stackOffset="expand"
            margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
            <XAxis dataKey="date" {...axisProps}
              tickFormatter={(v) => v.slice(5)} interval="preserveStartEnd" />
            <YAxis {...axisProps} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
            <Tooltip content={<ScenarioTooltip />} cursor={false} wrapperStyle={{ outline: "none" }} />
            {["s5", "s4", "s3", "s2", "s1"].map((key) => {
              const sc = scenarios.find(s => s.id.toLowerCase() === key);
              return (
                <Area key={key} type="monotone" dataKey={key}
                  stackId="1" fill={SCENARIO_COLORS[sc.id]} stroke={SCENARIO_COLORS[sc.id]}
                  fillOpacity={0.7} />
              );
            })}
          </AreaChart>
        </ResponsiveContainer>

        <div style={{
          display: "flex", gap: 16, justifyContent: "center", marginTop: 8,
          fontSize: 11, fontFamily: FONT,
        }}>
          {scenarios.map((sc) => (
            <span key={sc.id} style={{ color: SCENARIO_COLORS[sc.id] }}>
              {"\u25CF"} {sc.id} {sc.name}
            </span>
          ))}
        </div>
      </PanelBox>

      {/* ══════════════════════════════════════════
          Section 4: Key Drivers
          ══════════════════════════════════════════ */}
      <PanelBox>
        <SectionTitle>핵심 동인 (Key Drivers)</SectionTitle>
        <GuideBox>
          시나리오 확률 변동에 가장 큰 영향을 준 지표 Top 3.
          Z-score 절대값이 클수록 예상 대비 편차가 크다는 의미입니다.
        </GuideBox>

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {key_drivers.map((d, i) => {
            const term = TERM[d.indicator];
            const absZ = Math.abs(d.z_score);
            const zColor = absZ >= 2 ? C.danger : absZ >= 1 ? C.marginCall : C.muted;
            const sc = scenarios.find(s => s.id === d.scenario);
            return (
              <div key={i} style={{
                flex: "1 1 200px", background: C.bg, border: `1px solid ${C.border}`,
                borderRadius: 8, padding: "14px 16px",
              }}>
                <div style={{
                  fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 8, fontFamily: FONT,
                }}>
                  {term?.label || d.indicator}
                </div>
                <div style={{
                  display: "flex", justifyContent: "space-between",
                  fontSize: 12, color: C.muted, marginBottom: 4,
                }}>
                  <span>관측값</span>
                  <span style={{ color: C.text, fontWeight: 600 }}>{d.observed.toLocaleString()}</span>
                </div>
                <div style={{
                  display: "flex", justifyContent: "space-between",
                  fontSize: 12, color: C.muted, marginBottom: 4,
                }}>
                  <span>예상값</span>
                  <span>{d.expected.toLocaleString()}</span>
                </div>
                <div style={{
                  display: "flex", justifyContent: "space-between",
                  fontSize: 12, color: C.muted, marginBottom: 4,
                }}>
                  <span>Z-score</span>
                  <span style={{ color: zColor, fontWeight: 700 }}>
                    {d.z_score > 0 ? "+" : ""}{d.z_score.toFixed(2)}
                  </span>
                </div>
                <div style={{
                  marginTop: 8, padding: "4px 8px", borderRadius: 4,
                  background: `${SCENARIO_COLORS[d.scenario]}22`,
                  fontSize: 11, color: SCENARIO_COLORS[d.scenario],
                  fontWeight: 600, textAlign: "center",
                }}>
                  {d.direction === "supporting" ? "지지" : "반대"} → {sc?.name} ({d.scenario})
                </div>
              </div>
            );
          })}
        </div>
      </PanelBox>

      {/* ══════════════════════════════════════════
          Section 5: Loop Status
          ══════════════════════════════════════════ */}
      <PanelBox>
        <SectionTitle>Loop 상태 (Loop Status)</SectionTitle>
        <GuideBox>
          Loop A는 당일~익일 즉시적, Loop C는 T+1~T+3 지연적.
          시간차 중첩 시 하락 가속.
        </GuideBox>

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {Object.entries(LOOP_STATUS).map(([key, loop]) => {
            const isActive = loop.status === "active";
            const statusColor = isActive ? C.danger : C.safe;
            return (
              <div key={key} style={{
                flex: "1 1 280px", background: C.bg, border: `1px solid ${C.border}`,
                borderRadius: 8, padding: "14px 16px",
              }}>
                <div style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  marginBottom: 10,
                }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: C.text, fontFamily: FONT }}>
                    {loop.name}
                  </div>
                  <div style={{
                    fontSize: 11, fontWeight: 600, color: statusColor,
                    padding: "2px 8px", borderRadius: 4,
                    background: `${statusColor}22`,
                  }}>
                    {isActive ? "활성" : "비활성"}
                  </div>
                </div>

                {loop.wave1 && (
                  <>
                    <div style={{ fontSize: 12, color: C.muted, marginBottom: 4 }}>
                      <span style={{ color: C.dim }}>Wave 1:</span>{" "}
                      {loop.wave1.time} ({loop.wave1.desc})
                    </div>
                    <div style={{ fontSize: 12, color: C.muted, marginBottom: 4 }}>
                      <span style={{ color: C.dim }}>Wave 2:</span>{" "}
                      {loop.wave2.time} ({loop.wave2.desc})
                    </div>
                  </>
                )}

                {loop.delay && (
                  <>
                    <div style={{ fontSize: 12, color: C.muted, marginBottom: 4 }}>
                      <span style={{ color: C.dim }}>지연:</span> {loop.delay}
                    </div>
                    <div style={{ fontSize: 12, color: C.muted, marginBottom: 4 }}>
                      {loop.desc}
                    </div>
                  </>
                )}

                <div style={{
                  marginTop: 8, fontSize: 12, color: C.text, fontWeight: 600, fontFamily: FONT,
                }}>
                  추정 규모: {(loop.estimated_volume_billion * 10).toLocaleString()}억원
                  {loop.confidence && (
                    <span style={{ color: C.dim, fontWeight: 400, marginLeft: 6 }}>
                      (신뢰도: {loop.confidence})
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </PanelBox>

      {/* ══════════════════════════════════════════
          Section 6: Defense Walls
          ══════════════════════════════════════════ */}
      <PanelBox>
        <SectionTitle>방어벽 상태 (Defense Walls)</SectionTitle>
        <GuideBox>
          5단계 방어벽 중 Wall 1(개인) 붕괴, Wall 4(US스왑) 거절로 2개 소멸.
          시장 하락을 흡수하는 제도적/자금적 장치의 현재 상태를 나타냅니다.
        </GuideBox>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {DEFENSE_WALLS.map((wall) => {
            const statusConfig = {
              collapsed: { color: C.danger, label: "붕괴" },
              weakened: { color: C.marginCall, label: "약화" },
              active: { color: C.safe, label: "작동" },
              destroyed: { color: "#991b1b", label: "거절됨" },
              standby: { color: C.dim, label: "미발동" },
            };
            const cfg = statusConfig[wall.status] || { color: C.dim, label: wall.status };
            return (
              <div key={wall.id} style={{
                display: "flex", alignItems: "center", gap: 12,
              }}>
                <div style={{
                  width: 100, fontSize: 12, fontWeight: 600, color: C.text,
                  fontFamily: FONT, textAlign: "right",
                }}>
                  {wall.name}
                </div>
                <div style={{
                  flex: 1, background: C.bg, borderRadius: 6, height: 20,
                  position: "relative", overflow: "hidden", border: `1px solid ${C.border}`,
                }}>
                  <div style={{
                    width: `${wall.capacity * 100}%`, height: "100%",
                    background: cfg.color, borderRadius: 4, opacity: 0.7,
                    transition: "width 0.3s",
                  }} />
                </div>
                <div style={{
                  width: 60, fontSize: 11, fontWeight: 600, color: cfg.color,
                  fontFamily: FONT, textAlign: "center",
                }}>
                  {cfg.label}
                </div>
                <div style={{
                  width: 200, fontSize: 10, color: C.dim, fontFamily: FONT,
                }}>
                  {wall.detail}
                </div>
              </div>
            );
          })}
        </div>
      </PanelBox>
    </div>
  );
}
