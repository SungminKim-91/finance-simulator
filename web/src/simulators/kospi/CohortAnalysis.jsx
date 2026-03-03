import { useState, useMemo, useCallback } from "react";
import {
  ComposedChart,
  Bar,
  Cell,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
} from "recharts";
import { C } from "./colors";
import { TERM, TermLabel, fmtBillion } from "./shared/terms";
import { COHORT_DATA, INVESTOR_FLOWS, MARKET_DATA, SHORT_SELLING } from "./data/kospi_data";

const FONT = "'JetBrains Mono', monospace";

const STATUS_COLORS = { safe: C.safe, watch: C.watch, marginCall: C.marginCall, danger: C.danger };
const STATUS_LABELS = {
  safe: "안전", watch: "주의", marginCall: "마진콜", danger: "위험",
};

/* ── Sub-components ── */

function SectionTitle({ children, termKey }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, color: C.text, fontSize: 15, fontWeight: 700, marginBottom: 10, fontFamily: FONT }}>
      {children}
      {termKey && <TermLabel dataKey={termKey} color={C.dim} />}
    </div>
  );
}

function PanelBox({ children, style }) {
  return (
    <div style={{
      background: C.panel, border: `1px solid ${C.border}`,
      borderRadius: 10, padding: 18, marginBottom: 14, ...style,
    }}>
      {children}
    </div>
  );
}

const axisProps = { stroke: C.dim, fontSize: 11, fontFamily: FONT };

/* ── Toggle Button Group ── */
function ToggleGroup({ options, value, onChange }) {
  return (
    <div style={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
      {options.map((o) => (
        <button key={o.id} onClick={() => onChange(o.id)} style={{
          background: value === o.id ? C.kospi : "transparent",
          color: value === o.id ? "#fff" : C.muted,
          border: `1px solid ${value === o.id ? C.kospi : C.border}`,
          borderRadius: 6, padding: "4px 12px", fontSize: 11,
          fontWeight: 600, cursor: "pointer", fontFamily: FONT, transition: "all 0.15s",
        }}>{o.label}</button>
      ))}
    </div>
  );
}

/* ── Summary Card ── */
function SummaryCard({ label, value, unit, color = C.text }) {
  return (
    <div style={{
      background: C.bg, border: `1px solid ${C.border}`, borderRadius: 8,
      padding: "10px 14px", minWidth: 110, textAlign: "center",
    }}>
      <div style={{ fontSize: 11, color: C.muted, marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color, fontFamily: FONT }}>
        {value}
        {unit && <span style={{ fontSize: 12, fontWeight: 400, color: C.muted }}> {unit}</span>}
      </div>
    </div>
  );
}

/* ── Slider ── */
function SliderControl({ label, value, min, max, step = 1, onChange, format, termKey }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12, color: C.muted, marginBottom: 3 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {label}
          {termKey && <TermLabel dataKey={termKey} color={C.dim} />}
        </span>
        <span style={{ color: C.text, fontWeight: 600 }}>{format ? format(value) : value}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ width: "100%", accentColor: C.kospi }} />
    </div>
  );
}

/* ── Custom Tooltip for Simulator Chart ── */
function SimTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const billionKeys = ["forced_liq"];
  return (
    <div style={{
      background: C.panel, border: `1px solid ${C.border}`,
      borderRadius: 8, padding: "10px 14px", fontSize: 12, fontFamily: FONT,
    }}>
      <div style={{ color: C.muted, fontSize: 11, marginBottom: 4 }}>라운드 {label}</div>
      {payload.map((entry) => (
        <div key={entry.dataKey} style={{ color: entry.color, marginBottom: 2 }}>
          {entry.name}: {billionKeys.includes(entry.dataKey) ? fmtBillion(entry.value) : (typeof entry.value === "number" ? entry.value.toLocaleString() : entry.value)}
        </div>
      ))}
    </div>
  );
}

/* ── Cohort Bar Custom Label ── */
function CohortBarLabel({ x, y, width, height, value, entry }) {
  if (!entry || height < 8) return null;
  const statusColor = STATUS_COLORS[entry.status] || C.muted;
  const statusText = STATUS_LABELS[entry.status] || entry.status;
  return (
    <text
      x={x + width + 6} y={y + height / 2}
      textAnchor="start" dominantBaseline="central"
      style={{ fontSize: 10, fontFamily: FONT, fill: C.muted }}
    >
      <tspan>{fmtBillion(entry.amount)}</tspan>
      <tspan dx={6} fill={statusColor}>{entry.pnl_pct > 0 ? "+" : ""}{entry.pnl_pct}%</tspan>
      <tspan dx={4} fill={statusColor} fontWeight={600}>{statusText}</tspan>
    </text>
  );
}

/* ── Cohort Bar Tooltip ── */
function CohortTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  const statusColor = STATUS_COLORS[d.status] || C.muted;
  return (
    <div style={{
      background: C.panel, border: `1px solid ${C.border}`,
      borderRadius: 8, padding: "10px 14px", fontSize: 12, fontFamily: FONT,
    }}>
      <div style={{ color: C.text, fontWeight: 700, marginBottom: 4 }}>
        {TERM.cohort.label}
      </div>
      <div style={{ color: C.muted, marginBottom: 2 }}>
        진입가: <span style={{ color: C.text }}>{d.entry_kospi.toLocaleString()}</span>
        {" "}({d.entry_date})
      </div>
      <div style={{ color: C.muted, marginBottom: 2 }}>
        잔액: <span style={{ color: C.text }}>{fmtBillion(d.amount)}</span>
      </div>
      <div style={{ color: C.muted, marginBottom: 2 }}>
        손익: <span style={{ color: statusColor, fontWeight: 700 }}>{d.pnl_pct > 0 ? "+" : ""}{d.pnl_pct}%</span>
      </div>
      <div style={{ color: C.muted }}>
        담보비율: <span style={{ color: statusColor, fontWeight: 700 }}>
          {(d.collateral_ratio * 100).toFixed(0)}%
        </span>
        {" → "}<span style={{ color: statusColor }}>{STATUS_LABELS[d.status]}</span>
      </div>
    </div>
  );
}

/* ── Forced Liquidation Simulation Engine ── */
function runSimulation({
  cohorts, initialPrice, initialFx, shockPct, maxRounds,
  absorptionRate, loopMode, avgTradingValue, impactCoef, params,
}) {
  const rounds = [];
  let price = initialPrice * (1 + shockPct / 100);
  let fx = initialFx;
  const marginDist = params.margin_distribution;

  for (let r = 1; r <= maxRounds; r++) {
    // Loop A: forced liquidation
    let forcedLiq = 0;
    let marginCall = 0;
    if (loopMode === "A" || loopMode === "AB") {
      for (const c of cohorts) {
        const entry = c.entry_kospi || initialPrice;
        const amount = c.amount || 0;
        for (const [mr, w] of Object.entries(marginDist)) {
          if (entry === 0) continue;
          const ratio = (price / entry) / (1 - Number(mr));
          if (ratio < 1.30) forcedLiq += amount * w;
          else if (ratio < 1.40) marginCall += amount * w;
        }
      }
    }
    const sellPressureA = forcedLiq * (1 - absorptionRate);
    const impactA = avgTradingValue > 0
      ? (sellPressureA / avgTradingValue) * impactCoef : 0;

    // Loop B: FX → foreign selling (reserved, not active)
    let fxChangePct = 0;
    let foreignSell = 0;
    let impactB = 0;
    if (loopMode === "B" || loopMode === "AB") {
      const kospiDropPct = Math.abs((price / initialPrice - 1) * 100);
      fxChangePct = kospiDropPct * 0.3;
      let sensitivity;
      if (fxChangePct <= 1) sensitivity = 0.5;
      else if (fxChangePct <= 2) sensitivity = 1.0;
      else if (fxChangePct <= 3) sensitivity = 1.5;
      else sensitivity = 2.0;
      foreignSell = fxChangePct * sensitivity * 100;
      const sellPressureB = foreignSell * (1 - absorptionRate);
      impactB = avgTradingValue > 0
        ? (sellPressureB / avgTradingValue) * impactCoef : 0;
    }

    const totalImpact = impactA + impactB;
    price = price * (1 - totalImpact);
    fx = fx * (1 + fxChangePct / 100);

    const cumulativeDrop = +((price / initialPrice - 1) * 100).toFixed(2);

    rounds.push({
      round: r,
      price: Math.round(price),
      fx: Math.round(fx),
      forced_liq: Math.round(forcedLiq),
      margin_call: Math.round(marginCall),
      foreign_sell: Math.round(foreignSell),
      impact_a_pct: +(impactA * 100).toFixed(2),
      impact_b_pct: +(impactB * 100).toFixed(2),
      cumulative_drop_pct: cumulativeDrop,
    });

    if (forcedLiq < 100 && foreignSell < 50) break;
  }

  return {
    initialPrice,
    initialFx,
    finalPrice: rounds.length > 0 ? rounds[rounds.length - 1].price : initialPrice,
    finalFx: rounds.length > 0 ? rounds[rounds.length - 1].fx : initialFx,
    totalDropPct: rounds.length > 0 ? rounds[rounds.length - 1].cumulative_drop_pct : 0,
    convergedAt: rounds.length,
    rounds,
  };
}

/* ═══════════════════════════════════════════════════
   Main Component
   ═══════════════════════════════════════════════════ */

export default function CohortAnalysis() {
  const { lifo, fifo, trigger_map, current_kospi, current_fx,
    avg_daily_trading_value_billion, params } = COHORT_DATA;

  /* ── Section 1: Cohort Distribution ── */
  const [cohortMode, setCohortMode] = useState("LIFO");
  const [guideOpen, setGuideOpen] = useState(true);
  const activeCohorts = cohortMode === "LIFO" ? lifo : fifo;

  const cohortSummary = useMemo(() => {
    const total = activeCohorts.reduce((s, c) => s + c.amount, 0);
    const safe = activeCohorts.filter(c => c.status === "safe").reduce((s, c) => s + c.amount, 0);
    const danger = activeCohorts.filter(c => c.status === "danger").reduce((s, c) => s + c.amount, 0);
    return {
      total,
      safePct: total > 0 ? ((safe / total) * 100).toFixed(1) : "0",
      dangerPct: total > 0 ? ((danger / total) * 100).toFixed(1) : "0",
      count: activeCohorts.length,
    };
  }, [activeCohorts]);

  /* ── Cohort chart data: individual bars sorted by entry price ── */
  const cohortChartData = useMemo(() => {
    return activeCohorts
      .filter(c => c.amount > 0)
      .sort((a, b) => b.entry_kospi - a.entry_kospi)
      .map(c => ({
        label: `${c.entry_kospi.toLocaleString()} (${c.entry_date.slice(5)})`,
        amount: Math.round(c.amount),
        status: c.status,
        pnl_pct: c.pnl_pct,
        entry_kospi: c.entry_kospi,
        entry_date: c.entry_date,
        collateral_ratio: c.collateral_ratio,
      }));
  }, [activeCohorts]);

  /* ── Find index where current KOSPI falls ── */
  const currentKospiIdx = useMemo(() => {
    for (let i = 0; i < cohortChartData.length; i++) {
      if (cohortChartData[i].entry_kospi <= current_kospi) return i;
    }
    return cohortChartData.length;
  }, [cohortChartData, current_kospi]);

  /* ── Section 3: Simulator ── */
  const [shock, setShock] = useState(-10);
  const [maxRounds, setMaxRounds] = useState(5);
  const loopMode = "A"; // 반대매매 연쇄만 (환율 루프 제외)
  const [absorptionMode, setAbsorptionMode] = useState("auto");
  const [customAbsorption, setCustomAbsorption] = useState(0.5);
  const [simGuideOpen, setSimGuideOpen] = useState(true);

  /* Auto Absorption Rate (design doc spec) */
  const autoAbsorption = useMemo(() => {
    const recentFlows = INVESTOR_FLOWS.slice(-5);
    const avgRetailBuy = recentFlows.reduce((s, f) => s + Math.max(0, f.retail_billion), 0) / recentFlows.length;
    const tradingValue = MARKET_DATA.slice(-5).reduce((s, d) => s + d.trading_value_billion, 0) / 5;
    const buyRatio = tradingValue > 0 ? avgRetailBuy / tradingValue : 0;
    let absorption = Math.max(0.1, Math.min(0.9, buyRatio * 2));
    const lastShort = SHORT_SELLING[SHORT_SELLING.length - 1];
    if (lastShort?.gov_ban) absorption = Math.max(0.6, absorption);
    return +absorption.toFixed(2);
  }, []);

  const absorptionRate = absorptionMode === "custom"
    ? customAbsorption
    : absorptionMode === "auto"
      ? autoAbsorption
      : { conservative: 0.3, neutral: 0.5, optimistic: 0.7 }[absorptionMode];

  const [simResult, setSimResult] = useState(null);

  const handleRun = useCallback(() => {
    const result = runSimulation({
      cohorts: activeCohorts,
      initialPrice: current_kospi,
      initialFx: current_fx,
      shockPct: shock,
      maxRounds,
      absorptionRate,
      loopMode,
      avgTradingValue: avg_daily_trading_value_billion,
      impactCoef: params.impact_coefficient,
      params,
    });
    setSimResult(result);
  }, [activeCohorts, current_kospi, current_fx, shock, maxRounds, absorptionRate,
      avg_daily_trading_value_billion, params]);

  /* ── Trigger Map Color ── */
  const shockColor = (pct) => {
    const abs = Math.abs(pct);
    if (abs <= 5) return C.watch;
    if (abs <= 15) return C.marginCall;
    return C.danger;
  };

  const chartHeight = Math.max(200, cohortChartData.length * 28 + 60);

  return (
    <div>
      {/* ══════════════════════════════════════════
          Section 1: Cohort Distribution
          ══════════════════════════════════════════ */}
      <PanelBox>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
          <SectionTitle termKey="cohort">Cohort Distribution</SectionTitle>
          <ToggleGroup
            options={[{ id: "LIFO", label: "LIFO" }, { id: "FIFO", label: "FIFO" }]}
            value={cohortMode} onChange={setCohortMode}
          />
        </div>

        {/* Cohort Guide Box */}
        <div style={{
          background: `${C.bg}cc`, border: `1px solid ${C.border}`,
          borderRadius: 8, padding: guideOpen ? "12px 16px" : "8px 16px",
          marginBottom: 12, cursor: "pointer", transition: "all 0.2s",
        }} onClick={() => setGuideOpen(!guideOpen)}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: C.text, fontFamily: FONT }}>
              {TERM.cohort.label} ?
            </span>
            <span style={{ fontSize: 12, color: C.dim }}>{guideOpen ? "\u25B2" : "\u25BC"}</span>
          </div>
          {guideOpen && (
            <div style={{ marginTop: 6, fontSize: 12, color: C.muted, lineHeight: 1.7, fontFamily: FONT }}>
              <div>{TERM.cohort.desc}</div>
              <div style={{ marginTop: 4 }}>
                진입가가 높을수록 현재가 대비 손실이 크고, 반대매매 위험이 높습니다.
              </div>
              <div style={{ display: "flex", gap: 14, marginTop: 8, flexWrap: "wrap" }}>
                <span><span style={{ color: C.safe }}>&#9632;</span> 안전 (160%+)</span>
                <span><span style={{ color: C.watch }}>&#9632;</span> 주의 (140-160%)</span>
                <span><span style={{ color: C.marginCall }}>&#9632;</span> 마진콜 (130-140%)</span>
                <span><span style={{ color: C.danger }}>&#9632;</span> 위험 (130%↓)</span>
              </div>
            </div>
          )}
        </div>

        {/* Summary Cards */}
        <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
          <SummaryCard label="Active Cohorts" value={cohortSummary.count} />
          <SummaryCard label="Total Balance" value={(cohortSummary.total / 1000).toFixed(1)} unit="조원" />
          <SummaryCard label="Safe Ratio" value={cohortSummary.safePct} unit="%" color={C.safe} />
          <SummaryCard label="Danger Ratio" value={cohortSummary.dangerPct} unit="%" color={C.danger} />
        </div>

        {/* Current KOSPI Reference */}
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          fontSize: 12, color: C.muted, marginBottom: 8, fontFamily: FONT,
        }}>
          <span style={{
            display: "inline-block", width: 20, height: 2,
            background: C.kospi, borderRadius: 1,
          }} />
          현재 KOSPI: <span style={{ color: C.kospi, fontWeight: 700 }}>{current_kospi.toLocaleString()}</span>
          — 위 코호트는 손실, 아래 코호트는 이익
        </div>

        {/* Individual Cohort Bars */}
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart
            data={cohortChartData}
            layout="vertical"
            margin={{ top: 5, right: 160, left: 80, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke={C.border} horizontal={false} />
            <XAxis type="number" {...axisProps}
              tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(0)}K B` : `${v} B`}
            />
            <YAxis type="category" dataKey="label" {...axisProps} width={75}
              tick={{ fill: C.muted, fontSize: 10 }}
            />
            <Tooltip content={<CohortTooltip />} cursor={false} wrapperStyle={{ outline: "none" }} />
            <Bar dataKey="amount" radius={[0, 4, 4, 0]} isAnimationActive={false}
              label={({ x, y, width, height, index }) => (
                <CohortBarLabel
                  x={x} y={y} width={width} height={height}
                  value={cohortChartData[index]?.amount}
                  entry={cohortChartData[index]}
                />
              )}
            >
              {cohortChartData.map((entry, i) => (
                <Cell
                  key={i}
                  fill={STATUS_COLORS[entry.status] || C.muted}
                  opacity={i < currentKospiIdx ? 0.9 : 0.5}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        {/* Legend */}
        <div style={{ display: "flex", gap: 16, justifyContent: "center", marginTop: 8, fontSize: 11, fontFamily: FONT }}>
          {[
            { key: "status_safe", c: C.safe },
            { key: "status_watch", c: C.watch },
            { key: "status_marginCall", c: C.marginCall },
            { key: "status_danger", c: C.danger },
          ].map(({ key, c }) => (
            <TermLabel key={key} dataKey={key} color={c} />
          ))}
        </div>
      </PanelBox>

      {/* ══════════════════════════════════════════
          Section 2: Trigger Map
          ══════════════════════════════════════════ */}
      <PanelBox>
        <SectionTitle termKey="trigger_map">트리거 맵 (Trigger Map)</SectionTitle>

        {/* Guide Box */}
        <div style={{
          background: `${C.bg}cc`, border: `1px solid ${C.border}`,
          borderRadius: 8, padding: "12px 16px", marginBottom: 12,
          fontSize: 12, color: C.muted, lineHeight: 1.7, fontFamily: FONT,
        }}>
          <div style={{ fontWeight: 700, color: C.text, marginBottom: 4 }}>{TERM.trigger_map.label} ?</div>
          KOSPI가 현재가 대비 얼마나 하락하면, 얼마나 많은 신용매수 투자자에게
          마진콜(추가 담보 요구)이나 반대매매(강제 청산)가 발생하는지 보여주는 표입니다.
          하락폭이 클수록 위험 규모가 급격히 커집니다.
        </div>

        <div style={{ fontSize: 12, color: C.muted, marginBottom: 10 }}>
          현재 KOSPI: <span style={{ color: C.kospi, fontWeight: 700 }}>{current_kospi.toLocaleString()}</span>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: FONT }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                {[
                  "하락폭",
                  "예상 KOSPI",
                  "마진콜 (추가 입금 요구 D+2)",
                  "반대매매 (강제 청산)",
                ].map((h) => (
                  <th key={h} style={{
                    padding: "8px 10px", textAlign: "right", color: C.muted, fontWeight: 600,
                    fontSize: 11,
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trigger_map.map((row) => (
                <tr key={row.shock_pct} style={{ borderBottom: `1px solid ${C.border}22` }}>
                  <td style={{ padding: "8px 10px", textAlign: "right", color: shockColor(row.shock_pct), fontWeight: 700 }}>
                    {row.shock_pct}%
                  </td>
                  <td style={{ padding: "8px 10px", textAlign: "right", color: C.text }}>
                    {row.expected_kospi.toLocaleString()}
                  </td>
                  <td style={{ padding: "8px 10px", textAlign: "right", color: C.marginCall }}>
                    {fmtBillion(row.margin_call_billion)}
                  </td>
                  <td style={{ padding: "8px 10px", textAlign: "right", color: C.danger, fontWeight: 700 }}>
                    {fmtBillion(row.forced_liq_billion)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </PanelBox>

      {/* ══════════════════════════════════════════
          Section 3: Simulator
          ══════════════════════════════════════════ */}
      <PanelBox>
        <SectionTitle termKey="forced_liq">반대매매 연쇄 시뮬레이터</SectionTitle>

        {/* Guide Box */}
        <div style={{
          background: `${C.bg}cc`, border: `1px solid ${C.border}`,
          borderRadius: 8, padding: simGuideOpen ? "12px 16px" : "8px 16px",
          marginBottom: 14, cursor: "pointer", transition: "all 0.2s",
        }} onClick={() => setSimGuideOpen(!simGuideOpen)}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: C.text, fontFamily: FONT }}>
              반대매매 연쇄 시뮬레이터란?
            </span>
            <span style={{ fontSize: 12, color: C.dim }}>{simGuideOpen ? "\u25B2" : "\u25BC"}</span>
          </div>
          {simGuideOpen && (
            <div style={{ marginTop: 8, fontSize: 12, color: C.muted, lineHeight: 1.7, fontFamily: FONT }}>
              <div>
                KOSPI가 급락하면 신용매수 투자자의 담보가 부족해져 증권사가 강제 매도(반대매매)합니다.
                이 매도 물량이 추가 하락을 일으키고, 다시 반대매매를 유발하는 악순환을 시뮬레이션합니다.
              </div>
              <div style={{ marginTop: 8 }}>
                <span style={{ color: C.danger }}>연쇄 구조</span>: 주가&#8595; &#8594; 담보부족 &#8594; 강제매도 &#8594; 추가하락 &#8594; 반복
              </div>
              <div style={{ marginTop: 8, padding: "8px 12px", background: `${C.panel}aa`, borderRadius: 6, borderLeft: `2px solid ${C.foreign}` }}>
                <span style={{ color: C.foreign }}>참고:</span> 실제 대규모 반대매매 발생 시, 시장 불안 심화로 외국인 투자자의
                위험 회피 매도가 동반되어 하락 규모가 본 시뮬레이션보다 클 수 있습니다.
              </div>
            </div>
          )}
        </div>

        {/* Controls */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 14 }}>
          <div>
            {/* Initial Shock + Presets */}
            <SliderControl label="초기 충격 (Initial Shock)" value={shock} min={-50} max={-1}
              onChange={setShock} format={(v) => `${v}%`} termKey="initial_shock" />
            <div style={{ display: "flex", gap: 4, marginBottom: 10, marginTop: -4 }}>
              {[
                { label: "소폭 조정 (-5%)", value: -5 },
                { label: "급락 (-15%)", value: -15 },
                { label: "대폭락 (-30%)", value: -30 },
              ].map((p) => (
                <button key={p.value} onClick={() => setShock(p.value)} style={{
                  background: shock === p.value ? C.kospi : "transparent",
                  color: shock === p.value ? "#fff" : C.muted,
                  border: `1px solid ${shock === p.value ? C.kospi : C.border}`,
                  borderRadius: 6, padding: "3px 10px", fontSize: 11,
                  cursor: "pointer", fontFamily: FONT, transition: "all 0.15s",
                }}>{p.label}</button>
              ))}
            </div>

            <SliderControl label="반복 횟수 (Max Rounds)" value={maxRounds} min={1} max={10}
              onChange={setMaxRounds} termKey="max_rounds" />
            <div style={{ fontSize: 11, color: C.dim, marginTop: -4, marginBottom: 4 }}>
              보통 3~5회에 수렴합니다
            </div>
          </div>
          <div>
            {/* Absorption */}
            <div style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: C.muted, marginBottom: 4 }}>
                시장흡수율 — 반대매매 물량 중 시장이 소화하는 비율
              </div>
              <ToggleGroup
                options={[
                  { id: "auto", label: `자동 (${autoAbsorption})` },
                  { id: "conservative", label: "보수적 (0.3)" },
                  { id: "neutral", label: "중립 (0.5)" },
                  { id: "optimistic", label: "낙관 (0.7)" },
                  { id: "custom", label: "직접 입력" },
                ]}
                value={absorptionMode} onChange={setAbsorptionMode}
              />
              {absorptionMode === "auto" && (
                <div style={{ fontSize: 11, color: C.dim, marginTop: 6, lineHeight: 1.6 }}>
                  최근 5일 개인+금투 매수 비율 기반 자동 산출. 정부 개입 시 최소 0.6
                </div>
              )}
              {absorptionMode === "custom" && (
                <SliderControl label="" value={customAbsorption} min={0.1} max={0.9} step={0.05}
                  onChange={setCustomAbsorption} format={(v) => v.toFixed(2)} />
              )}
            </div>
          </div>
        </div>

        {/* Run Button */}
        <button onClick={handleRun} style={{
          background: C.kospi, color: "#fff", border: "none", borderRadius: 8,
          padding: "10px 28px", fontSize: 13, fontWeight: 700, cursor: "pointer",
          fontFamily: FONT, marginBottom: 16, transition: "opacity 0.15s",
        }}
          onMouseEnter={(e) => (e.target.style.opacity = 0.8)}
          onMouseLeave={(e) => (e.target.style.opacity = 1)}>
          시뮬레이션 실행
        </button>

        {/* Results */}
        {simResult && (
          <>
            {/* Summary Cards */}
            <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
              <SummaryCard label="최종 KOSPI" value={simResult.finalPrice.toLocaleString()} color={C.kospi} />
              <SummaryCard label="총 하락폭" value={simResult.totalDropPct} unit="%" color={C.danger} />
              <SummaryCard label="수렴 라운드" value={`${simResult.convergedAt}회`} color={C.safe} />
            </div>

            {/* Chart — TradingView volume style: bars capped at bottom 30% */}
            <ResponsiveContainer width="100%" height={340}>
              <ComposedChart data={simResult.rounds} margin={{ top: 10, right: 30, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="round" {...axisProps} label={{ value: "라운드", position: "insideBottom", offset: -2, style: { fill: C.muted, fontSize: 10 } }} />

                <YAxis yAxisId="left" {...axisProps} orientation="left"
                  domain={["auto", "auto"]}
                  tickFormatter={(v) => v.toLocaleString()}
                  label={{ value: "KOSPI", angle: -90, position: "insideLeft", style: { fill: C.muted, fontSize: 10 } }} />

                {/* Right axis: inflate domain 3.3x so bars only fill bottom ~30% */}
                <YAxis yAxisId="right" orientation="right" hide
                  domain={[0, (dataMax) => Math.max(Math.ceil(dataMax * 3.3), 1)]} />

                <Tooltip content={<SimTooltip />} cursor={false} wrapperStyle={{ outline: "none" }} />
                <Legend formatter={(v) => <span style={{ fontSize: 11, color: C.muted }}>{v}</span>} />

                <Bar yAxisId="right" dataKey="forced_liq" name="반대매매"
                  fill={C.danger} opacity={0.35} radius={[3, 3, 0, 0]} />

                <Line yAxisId="left" type="monotone" dataKey="price" name="KOSPI"
                  stroke={C.kospi} strokeWidth={2.5} dot={{ r: 4, fill: C.kospi }} />
              </ComposedChart>
            </ResponsiveContainer>

            {/* Round Detail Table */}
            <div style={{ overflowX: "auto", marginTop: 10 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: FONT }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                    {["라운드", "KOSPI", "반대매매", "충격률", "누적 하락"].map((h) => (
                      <th key={h} style={{ padding: "6px 8px", textAlign: "right", color: C.muted, fontWeight: 600 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {simResult.rounds.map((r) => (
                    <tr key={r.round} style={{ borderBottom: `1px solid ${C.border}22` }}>
                      <td style={{ padding: "6px 8px", textAlign: "right", color: C.text }}>{r.round}</td>
                      <td style={{ padding: "6px 8px", textAlign: "right", color: C.kospi }}>{r.price.toLocaleString()}</td>
                      <td style={{ padding: "6px 8px", textAlign: "right", color: C.danger }}>
                        {r.forced_liq > 0 ? fmtBillion(r.forced_liq) : "-"}
                      </td>
                      <td style={{ padding: "6px 8px", textAlign: "right", color: C.muted }}>{r.impact_a_pct}%</td>
                      <td style={{ padding: "6px 8px", textAlign: "right", color: C.danger, fontWeight: 600 }}>{r.cumulative_drop_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {!simResult && (
          <div style={{ textAlign: "center", padding: 24, color: C.dim, fontSize: 13 }}>
            파라미터를 설정하고 <strong>시뮬레이션 실행</strong>을 클릭하세요.
          </div>
        )}
      </PanelBox>
    </div>
  );
}
