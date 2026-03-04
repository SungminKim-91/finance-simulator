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
  ScatterChart,
  Scatter,
  ReferenceLine,
} from "recharts";
import { C } from "./colors";
import { TERM, TermLabel, TermHint, fmtBillion } from "./shared/terms";
import {
  COHORT_DATA, INVESTOR_FLOWS, MARKET_DATA, SHORT_SELLING,
  COHORT_HISTORY, BACKTEST_DATES, STOCK_CREDIT,
} from "./data/kospi_data";

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
function CohortBarLabel({ x, y, width, height, entry }) {
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
      {d.liquidated_pct > 0 && (
        <div style={{ color: C.danger, marginTop: 2 }}>
          청산추정: {d.liquidated_pct.toFixed(1)}% (잔여 {(100 - d.liquidated_pct).toFixed(1)}%)
        </div>
      )}
    </div>
  );
}

/* ── Utility: Compute approximate portfolio beta from MARKET_DATA for a given date index ── */
function computeBacktestBeta(dateIdx, lookback = 7) {
  const defaultBeta = COHORT_DATA.portfolio_beta || 1.0;
  if (dateIdx < lookback || !MARKET_DATA?.length) return defaultBeta;

  const weights = STOCK_CREDIT?.stocks?.reduce((acc, s) => {
    if (s.ticker !== "_residual" && s.kospi_weight_pct > 0) acc[s.ticker] = s.kospi_weight_pct / 100;
    return acc;
  }, {}) || {};

  // Compute hybrid beta for samsung (005930) and hynix (000660) from MARKET_DATA
  const computeStockBeta = (getPrice) => {
    let sumWXY = 0, sumWXX = 0;
    for (let i = dateIdx - lookback + 1; i <= dateIdx; i++) {
      const prev = MARKET_DATA[i - 1], curr = MARKET_DATA[i];
      if (!prev || !curr) continue;
      const kp = prev.kospi, kc = curr.kospi;
      const sp = getPrice(prev), sc = getPrice(curr);
      if (!kp || !kc || !sp || !sc || kp <= 0 || sp <= 0) continue;
      const kr = kc / kp - 1, sr = sc / sp - 1;
      const w = kr < 0 ? 0.6 : 0.4;
      sumWXY += w * sr * kr;
      sumWXX += w * kr * kr;
    }
    if (sumWXX < 1e-10) return 1.0;
    return Math.max(0.5, Math.min(3.0, sumWXY / sumWXX));
  };

  const samBeta = computeStockBeta(r => r.samsung);
  const hyBeta = computeStockBeta(r => r.hynix);
  const samW = weights["005930"] || 0.5;
  const hyW = weights["000660"] || 0.1;
  const coveredW = samW + hyW;
  const residualW = 1.0 - coveredW;
  return +(samW * samBeta + hyW * hyBeta + residualW * 1.0).toFixed(3);
}

/* ── v1.4.1 Status Classification (단일 기준) ── */
const MARGIN_RATE = 0.45;
const MAINTENANCE_RATIO = 1.40;
const FORCED_LIQ_LOSS_PCT = 39;

function classifyStatus(collateralRatio, lossPct) {
  if (lossPct >= FORCED_LIQ_LOSS_PCT) return "danger";   // 반대매매 확정
  if (collateralRatio < MAINTENANCE_RATIO) return "marginCall"; // D+2 추가담보
  if (collateralRatio < MAINTENANCE_RATIO + 0.20) return "watch";
  return "safe";
}

/* ── Utility: Reconstruct cohorts from history snapshot ── */
function reconstructCohorts(registry, snapshot, params, portfolioBeta = 1.0) {
  if (!registry || !snapshot) return [];

  const cohorts = [];
  const amounts = snapshot.amounts || {};
  const currentKospi = snapshot.kospi || 0;

  for (const [entryDate, amount] of Object.entries(amounts)) {
    const reg = registry[entryDate];
    if (!reg || amount <= 0) continue;
    const entryKospi = reg.entry_kospi || 0;

    const rawRatio = entryKospi > 0 ? currentKospi / entryKospi : 1.0;
    const effectiveRatio = 1.0 + (rawRatio - 1.0) * portfolioBeta;

    const pnlPct = entryKospi > 0 ? +((effectiveRatio - 1.0) * 100).toFixed(2) : 0;
    const collRatio = entryKospi > 0 ? effectiveRatio / (1 - MARGIN_RATE) : 9.99;
    const lossPct = Math.max(0, -pnlPct);
    const status = classifyStatus(collRatio, lossPct);

    // v1.4.1: danger → 전량 청산 (반대매매 확정)
    if (status === "danger") continue;

    cohorts.push({
      entry_date: entryDate,
      entry_kospi: entryKospi,
      amount,
      pnl_pct: pnlPct,
      collateral_ratio: +collRatio.toFixed(3),
      status,
      liquidated_pct: 0,
    });
  }
  return cohorts;
}

/* ── Utility: Compute implied absorption from actual data ── */
function computeImpliedAbsorption({ forcedLiq, actualPriceChange, avgTradingValue, impactCoef }) {
  if (forcedLiq <= 0 || avgTradingValue <= 0) return null;
  // actualPriceChange = -impactA = -(sellPressure / avgTV) * impactCoef
  // sellPressure = forcedLiq * (1 - absorption)
  // absorption = 1 - (actualPriceChange * avgTV) / (forcedLiq * impactCoef)
  const absActual = Math.abs(actualPriceChange);
  const implied = 1 - (absActual * avgTradingValue) / (forcedLiq * impactCoef);
  return Math.max(0, Math.min(1, implied));
}

/* ── Forced Liquidation Simulation Engine (distribution-based, v1.4.0 beta-aware) ── */
function runSimulation({
  cohorts, initialPrice, initialFx, shockPct, maxRounds,
  absorptionRate, loopMode, avgTradingValue, impactCoef, params,
  portfolioBeta = 1.0,
}) {
  const rounds = [];
  let price = initialPrice * (1 + shockPct / 100);
  let fx = initialFx;

  for (let r = 1; r <= maxRounds; r++) {
    let forcedLiq = 0;
    let marginCall = 0;
    if (loopMode === "A" || loopMode === "AB") {
      for (const c of cohorts) {
        const entry = c.entry_kospi || initialPrice;
        const amount = c.amount || 0;
        if (entry === 0) continue;
        const rawRatio = price / entry;
        const effectiveRatio = 1.0 + (rawRatio - 1.0) * portfolioBeta;
        const collRatio = effectiveRatio / (1 - MARGIN_RATE);
        const lossPct = Math.max(0, (1 - effectiveRatio) * 100);
        if (lossPct >= FORCED_LIQ_LOSS_PCT) forcedLiq += amount;
        else if (collRatio < MAINTENANCE_RATIO) marginCall += amount;
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

/* ── BacktestComparison sub-component ── */
function BacktestComparison({ simResult, forward, baseKospi, absorptionRate, params }) {
  if (!simResult || !forward?.length) return null;

  const impactCoef = params.impact_coefficient || 1.5;

  // Build comparison data: Round ↔ Day mapping
  const comparison = simResult.rounds.map((r, i) => {
    const actual = forward[i];
    const simKospi = r.price;
    const actualKospi = actual?.kospi;
    const errorPct = actualKospi && simKospi
      ? +((simKospi - actualKospi) / actualKospi * 100).toFixed(2) : null;
    const simDir = r.cumulative_drop_pct < 0 ? "하락" : "상승";
    const actualDir = actual && baseKospi
      ? ((actual.kospi - baseKospi) / baseKospi * 100 < 0 ? "하락" : "상승")
      : null;
    return {
      round: r.round,
      day: `D+${i + 1}`,
      date: actual?.date || "-",
      simKospi,
      actualKospi,
      errorPct,
      simDir,
      actualDir,
      dirMatch: simDir === actualDir,
    };
  });

  // Implied absorption for D+1
  const d1 = forward[0];
  const impliedAbs = d1 && simResult.rounds[0]
    ? computeImpliedAbsorption({
        forcedLiq: simResult.rounds[0].forced_liq,
        actualPriceChange: simResult.rounds[0].impact_a_pct / 100,
        avgTradingValue: d1.trading_value_billion || 100,
        impactCoef,
      })
    : null;

  // Dual-line chart data
  const chartData = comparison.filter(c => c.actualKospi).map(c => ({
    name: c.day,
    sim: c.simKospi,
    actual: c.actualKospi,
  }));

  return (
    <div style={{ marginTop: 16, borderTop: `1px solid ${C.border}`, paddingTop: 14 }}>
      <SectionTitle termKey="backtest">백테스트 비교 (Backtest Comparison)</SectionTitle>

      {/* Dual Line Chart */}
      {chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={240}>
          <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
            <XAxis dataKey="name" {...axisProps} />
            <YAxis {...axisProps} tickFormatter={(v) => v.toLocaleString()} domain={["auto", "auto"]} />
            <Tooltip contentStyle={{ background: C.panel, border: `1px solid ${C.border}`, fontSize: 11, fontFamily: FONT }} />
            <Legend formatter={(v) => <span style={{ fontSize: 11, color: C.muted }}>{v}</span>} />
            <Line type="monotone" dataKey="sim" name="시뮬레이션" stroke={C.kospi} strokeWidth={2} dot={{ r: 3 }} />
            <Line type="monotone" dataKey="actual" name="실제" stroke={C.samsung} strokeWidth={2} dot={{ r: 3 }} strokeDasharray="5 3" />
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* Implied Absorption */}
      {impliedAbs !== null && (
        <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
          <SummaryCard label="가정 흡수율" value={absorptionRate.toFixed(2)} color={C.muted} />
          <SummaryCard label="역산 흡수율" value={impliedAbs.toFixed(2)} color={C.foreign} />
          <SummaryCard
            label="차이"
            value={((impliedAbs - absorptionRate) * 100).toFixed(1)}
            unit="%p"
            color={Math.abs(impliedAbs - absorptionRate) > 0.2 ? C.danger : C.safe}
          />
        </div>
      )}

      {/* Comparison Table */}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: FONT }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {["Day", "Date", "Sim KOSPI", "Actual", "Error%", "Direction"].map((h) => (
                <th key={h} style={{ padding: "6px 8px", textAlign: "right", color: C.muted, fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {comparison.map((r) => (
              <tr key={r.round} style={{ borderBottom: `1px solid ${C.border}22` }}>
                <td style={{ padding: "6px 8px", textAlign: "right", color: C.text }}>{r.day}</td>
                <td style={{ padding: "6px 8px", textAlign: "right", color: C.dim }}>{r.date}</td>
                <td style={{ padding: "6px 8px", textAlign: "right", color: C.kospi }}>{r.simKospi.toLocaleString()}</td>
                <td style={{ padding: "6px 8px", textAlign: "right", color: C.samsung }}>
                  {r.actualKospi ? r.actualKospi.toLocaleString() : "-"}
                </td>
                <td style={{ padding: "6px 8px", textAlign: "right", color: r.errorPct !== null && Math.abs(r.errorPct) > 3 ? C.danger : C.muted }}>
                  {r.errorPct !== null ? `${r.errorPct > 0 ? "+" : ""}${r.errorPct}%` : "-"}
                </td>
                <td style={{ padding: "6px 8px", textAlign: "right", color: r.dirMatch ? C.safe : C.danger, fontWeight: 600 }}>
                  {r.actualDir ? (r.dirMatch ? "O" : "X") : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Forward actual data */}
      {forward.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12, color: C.muted, marginBottom: 6, fontWeight: 600 }}>
            실제 시장 데이터 (D+1 ~ D+5)
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11, fontFamily: FONT }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  {["Day", "KOSPI", "개인(B)", "외국인(B)", "기관(B)", "거래대금(B)"].map((h) => (
                    <th key={h} style={{ padding: "5px 6px", textAlign: "right", color: C.dim, fontWeight: 600 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {forward.map((f) => (
                  <tr key={f.day} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td style={{ padding: "5px 6px", textAlign: "right", color: C.text }}>D+{f.day}</td>
                    <td style={{ padding: "5px 6px", textAlign: "right", color: C.kospi }}>{f.kospi?.toLocaleString() || "-"}</td>
                    <td style={{ padding: "5px 6px", textAlign: "right", color: C.individual }}>{f.individual_billion?.toFixed(1) || "-"}</td>
                    <td style={{ padding: "5px 6px", textAlign: "right", color: C.foreign }}>{f.foreign_billion?.toFixed(1) || "-"}</td>
                    <td style={{ padding: "5px 6px", textAlign: "right", color: C.institution }}>{f.institution_billion?.toFixed(1) || "-"}</td>
                    <td style={{ padding: "5px 6px", textAlign: "right", color: C.muted }}>{f.trading_value_billion?.toFixed(1) || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── ReliabilityDashboard sub-component ── */
function ReliabilityDashboard({ params, registry, snapshots, backtestDates, avgTradingValue, autoAbsorption, portfolioBeta = 1.0 }) {
  const results = useMemo(() => {
    if (!backtestDates?.length || !snapshots?.length || !registry) return [];
    const impactCoef = params.impact_coefficient || 1.5;

    // Build date→index map for snapshots
    const dateIdx = {};
    snapshots.forEach((s, i) => { dateIdx[s.date] = i; });

    return backtestDates.map((evt) => {
      // Find prev-day snapshot
      const evtIdx = dateIdx[evt.date];
      const prevIdx = evtIdx != null ? evtIdx - 1 : null;
      const prevSnap = prevIdx != null && prevIdx >= 0 ? snapshots[prevIdx] : null;

      if (!prevSnap) {
        return { ...evt, simD1: null, actualD1: null, error: null, dirMatch: null };
      }

      const prevKospi = prevSnap.kospi || 0;
      // v1.4.0: Compute beta for the event date
      const evtDateIdx = MARKET_DATA.findIndex(r => r.date === evt.date);
      const btBeta = evtDateIdx >= 0 ? computeBacktestBeta(evtDateIdx) : portfolioBeta;
      const cohorts = reconstructCohorts(registry, prevSnap, params, btBeta);
      if (!cohorts.length || !prevKospi) {
        return { ...evt, simD1: null, actualD1: null, error: null, dirMatch: null };
      }

      const sim = runSimulation({
        cohorts,
        initialPrice: prevKospi,
        initialFx: 1400,
        shockPct: evt.shock_pct,
        maxRounds: 5,
        absorptionRate: autoAbsorption,
        loopMode: "A",
        avgTradingValue: prevSnap.trading_value || avgTradingValue,
        impactCoef,
        params,
        portfolioBeta: btBeta,
      });

      const simD1 = sim.rounds[0]?.price || null;
      const actualD1 = evt.forward?.[0]?.kospi || null;
      const error = simD1 && actualD1
        ? +((simD1 - actualD1) / actualD1 * 100).toFixed(2) : null;
      const simDrop = sim.totalDropPct;
      const actualDrop = actualD1 && prevKospi
        ? (actualD1 - prevKospi) / prevKospi * 100 : null;
      const dirMatch = simDrop !== null && actualDrop !== null
        ? (simDrop < 0) === (actualDrop < 0) : null;

      return {
        ...evt,
        simD1,
        actualD1,
        error,
        simDrop: +simDrop.toFixed(2),
        actualDrop: actualDrop !== null ? +actualDrop.toFixed(2) : null,
        dirMatch,
      };
    }).filter(r => r.simD1 !== null && r.actualD1 !== null);
  }, [backtestDates, snapshots, registry, params, avgTradingValue, autoAbsorption, portfolioBeta]);

  if (!results.length) {
    return (
      <PanelBox>
        <SectionTitle termKey="direction_accuracy">모델 신뢰도 대시보드</SectionTitle>
        <div style={{ textAlign: "center", padding: 24, color: C.dim, fontSize: 13 }}>
          백테스트 데이터 부족 (코호트 히스토리 필요)
        </div>
      </PanelBox>
    );
  }

  // Summary stats
  const dirCorrect = results.filter(r => r.dirMatch === true).length;
  const dirTotal = results.filter(r => r.dirMatch !== null).length;
  const dirAccuracy = dirTotal > 0 ? ((dirCorrect / dirTotal) * 100).toFixed(1) : "N/A";
  const errors = results.filter(r => r.error !== null).map(r => r.error);
  const rmse = errors.length > 0
    ? Math.sqrt(errors.reduce((s, e) => s + e * e, 0) / errors.length).toFixed(2) : "N/A";

  // Scatter data
  const scatterData = results.filter(r => r.actualDrop !== null).map(r => ({
    actual: r.actualDrop,
    sim: r.simDrop,
    date: r.date,
  }));

  return (
    <PanelBox>
      <SectionTitle termKey="direction_accuracy">모델 신뢰도 대시보드 (Reliability)</SectionTitle>

      <div style={{
        background: `${C.bg}cc`, border: `1px solid ${C.border}`,
        borderRadius: 8, padding: "12px 16px", marginBottom: 12,
        fontSize: 12, color: C.muted, lineHeight: 1.7, fontFamily: FONT,
      }}>
        BACKTEST_DATES 전체({results.length}건)에 대해 시뮬레이션을 실행한 결과입니다.
        시뮬레이션 D+1 가격과 실제 D+1 가격을 비교하여 방향 정확도와 오차를 산출합니다.
      </div>

      {/* Summary */}
      <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        <SummaryCard label="방향 정확도" value={dirAccuracy} unit="%" color={Number(dirAccuracy) > 60 ? C.safe : C.danger} />
        <SummaryCard label="RMSE" value={rmse} unit="%" color={C.muted} />
        <SummaryCard label="테스트 건수" value={results.length} color={C.text} />
      </div>

      {/* Scatter: actual vs sim */}
      {scatterData.length > 0 && (
        <>
          <div style={{ fontSize: 12, color: C.muted, marginBottom: 6, fontWeight: 600 }}>
            산점도: X=실제변동%, Y=시뮬변동% (대각선=완벽 예측)
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <ScatterChart margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis type="number" dataKey="actual" name="실제" {...axisProps}
                label={{ value: "실제 변동%", position: "insideBottom", offset: -4, style: { fill: C.muted, fontSize: 10 } }} />
              <YAxis type="number" dataKey="sim" name="시뮬" {...axisProps}
                label={{ value: "시뮬 변동%", angle: -90, position: "insideLeft", style: { fill: C.muted, fontSize: 10 } }} />
              <Tooltip
                contentStyle={{ background: C.panel, border: `1px solid ${C.border}`, fontSize: 11, fontFamily: FONT }}
                formatter={(val, name) => [`${val.toFixed(2)}%`, name]}
                labelFormatter={() => ""}
              />
              <ReferenceLine
                segment={[{ x: -15, y: -15 }, { x: 5, y: 5 }]}
                stroke={C.dim} strokeDasharray="5 3" strokeWidth={1}
              />
              <Scatter data={scatterData} fill={C.kospi} opacity={0.7} />
            </ScatterChart>
          </ResponsiveContainer>
        </>
      )}

      {/* Detail Table */}
      <div style={{ overflowX: "auto", marginTop: 10, maxHeight: 300, overflow: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11, fontFamily: FONT }}>
          <thead style={{ position: "sticky", top: 0, background: C.panel }}>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {["Date", "Shock%", "Sim D+1", "Actual D+1", "Error%", "Dir"].map((h) => (
                <th key={h} style={{ padding: "5px 6px", textAlign: "right", color: C.muted, fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.date} style={{ borderBottom: `1px solid ${C.border}22` }}>
                <td style={{ padding: "5px 6px", textAlign: "right", color: C.dim }}>{r.date}</td>
                <td style={{ padding: "5px 6px", textAlign: "right", color: r.shock_pct < 0 ? C.danger : C.safe, fontWeight: 600 }}>
                  {r.shock_pct > 0 ? "+" : ""}{r.shock_pct}%
                </td>
                <td style={{ padding: "5px 6px", textAlign: "right", color: C.kospi }}>{r.simD1?.toLocaleString()}</td>
                <td style={{ padding: "5px 6px", textAlign: "right", color: C.samsung }}>{r.actualD1?.toLocaleString()}</td>
                <td style={{ padding: "5px 6px", textAlign: "right", color: r.error !== null && Math.abs(r.error) > 3 ? C.danger : C.muted }}>
                  {r.error !== null ? `${r.error > 0 ? "+" : ""}${r.error}%` : "-"}
                </td>
                <td style={{ padding: "5px 6px", textAlign: "right", color: r.dirMatch ? C.safe : C.danger, fontWeight: 600 }}>
                  {r.dirMatch !== null ? (r.dirMatch ? "O" : "X") : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PanelBox>
  );
}

/* ── Stock Credit Breakdown (v1.3.0) ── */
const STOCK_COLORS = [
  "#4fc3f7", "#81c784", "#ffb74d", "#e57373", "#ba68c8",
  "#4dd0e1", "#aed581", "#ffd54f", "#f06292", "#7986cb", "#90a4ae",
];

function StockCreditBreakdown() {
  const stocks = STOCK_CREDIT?.stocks || [];
  const isWeighted = STOCK_CREDIT?.stock_weighted || false;
  const betas = STOCK_CREDIT?.betas || {};
  const hasBetas = Object.keys(betas).some(k => !k.startsWith("_"));

  if (!stocks.length) return null;

  const total = stocks.reduce((s, st) => s + (st.credit_billion || 0), 0);
  const top10Only = stocks.filter(s => s.ticker !== "_residual");
  const residual = stocks.find(s => s.ticker === "_residual");
  const top10Total = top10Only.reduce((s, st) => s + (st.credit_billion || 0), 0);

  const fmtPrice = (v) => v > 0 ? v.toLocaleString() : "-";
  const fmtBeta = (v) => v > 0 ? v.toFixed(2) : "-";

  // Status bar helper
  const StatusBar = ({ breakdown }) => {
    if (!breakdown) return null;
    const t = (breakdown.safe || 0) + (breakdown.watch || 0) + (breakdown.margin_call || 0) + (breakdown.forced_liq || 0);
    if (t <= 0) return <span style={{ color: C.dim }}>-</span>;
    const safePct = ((breakdown.safe || 0) / t * 100).toFixed(0);
    return (
      <div style={{ display: "flex", height: 14, borderRadius: 3, overflow: "hidden", minWidth: 60 }}>
        {breakdown.safe > 0 && <div style={{ width: `${(breakdown.safe / t) * 100}%`, background: C.safe }} />}
        {breakdown.watch > 0 && <div style={{ width: `${(breakdown.watch / t) * 100}%`, background: C.watch }} />}
        {breakdown.margin_call > 0 && <div style={{ width: `${(breakdown.margin_call / t) * 100}%`, background: C.marginCall }} />}
        {breakdown.forced_liq > 0 && <div style={{ width: `${(breakdown.forced_liq / t) * 100}%`, background: C.danger }} />}
      </div>
    );
  };

  return (
    <PanelBox>
      <SectionTitle termKey="stock_credit">종목별 신용잔고 (Stock Credit)</SectionTitle>

      {/* Summary cards */}
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <SummaryCard label="Top 10 합계" value={(top10Total / 1000).toFixed(1)} unit="조원" color={C.kospi} />
        <SummaryCard label="기타" value={residual ? (residual.credit_billion / 1000).toFixed(1) : "0"} unit="조원" />
        <SummaryCard label="Top 10 비중" value={total > 0 ? ((top10Total / total) * 100).toFixed(1) : "0"} unit="%" color={C.samsung} />
        <SummaryCard label="모델" value={hasBetas ? "Beta가중" : isWeighted ? "가중" : "단일"} color={hasBetas ? C.safe : C.muted} />
      </div>

      {/* Horizontal stacked bar */}
      <div style={{ marginBottom: 8 }}>
        <div style={{ display: "flex", height: 28, borderRadius: 6, overflow: "hidden", border: `1px solid ${C.border}` }}>
          {top10Only.map((st, i) => {
            const pct = total > 0 ? (st.credit_billion / total) * 100 : 0;
            if (pct < 0.5) return null;
            return (
              <div key={st.ticker} title={`${st.name}: ${fmtBillion(st.credit_billion)} (${pct.toFixed(1)}%)`}
                style={{
                  width: `${pct}%`, background: STOCK_COLORS[i % STOCK_COLORS.length],
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: pct > 8 ? 10 : 0, color: "#1a1a2e", fontWeight: 700, fontFamily: FONT,
                  transition: "width 0.3s",
                }}>
                {pct > 8 ? st.name.slice(0, 4) : ""}
              </div>
            );
          })}
          {residual && residual.credit_billion > 0 && (
            <div title={`기타: ${fmtBillion(residual.credit_billion)}`}
              style={{
                width: `${total > 0 ? (residual.credit_billion / total) * 100 : 0}%`,
                background: "#555", display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 10, color: C.muted, fontFamily: FONT,
              }}>
              기타
            </div>
          )}
        </div>
      </div>

      {/* Per-stock detail table */}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11, fontFamily: FONT }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              <th style={{ padding: "6px 8px", textAlign: "left", color: C.muted, fontWeight: 600 }}>종목</th>
              <th style={{ padding: "6px 8px", textAlign: "right", color: C.muted, fontWeight: 600 }}>신용잔고</th>
              <th style={{ padding: "6px 8px", textAlign: "right", color: C.muted, fontWeight: 600 }}>비중</th>
              <th style={{ padding: "6px 8px", textAlign: "right", color: C.muted, fontWeight: 600 }}>KOSPI가중</th>
              {hasBetas && <th style={{ padding: "6px 8px", textAlign: "right", color: C.muted, fontWeight: 600 }}>Beta<TermHint dataKey="hybrid_beta" /></th>}
              <th style={{ padding: "6px 8px", textAlign: "right", color: C.muted, fontWeight: 600 }}>현재가</th>
              <th style={{ padding: "6px 6px", textAlign: "center", color: C.muted, fontWeight: 600, minWidth: 70 }}>상태<TermHint dataKey="stock_price_status" /></th>
            </tr>
          </thead>
          <tbody>
            {top10Only.map((st, i) => (
              <tr key={st.ticker} style={{ borderBottom: `1px solid ${C.border}22` }}>
                <td style={{ padding: "5px 8px" }}>
                  <span style={{ color: STOCK_COLORS[i % STOCK_COLORS.length], marginRight: 4 }}>{"\u25CF"}</span>
                  <span style={{ color: C.text }}>{st.name}</span>
                  <span style={{ color: C.dim, fontSize: 10, marginLeft: 4 }}>{st.ticker}</span>
                </td>
                <td style={{ padding: "5px 8px", textAlign: "right", color: C.text }}>
                  {fmtBillion(st.credit_billion)}
                </td>
                <td style={{ padding: "5px 8px", textAlign: "right", color: C.muted }}>
                  {total > 0 ? ((st.credit_billion / total) * 100).toFixed(1) : "0"}%
                </td>
                <td style={{ padding: "5px 8px", textAlign: "right", color: C.kospi }}>
                  {st.kospi_weight_pct?.toFixed(1) || "0"}%
                </td>
                {hasBetas && (
                  <td style={{ padding: "5px 8px", textAlign: "right", color: (st.beta || betas[st.ticker] || 0) > 1.5 ? C.danger : (st.beta || betas[st.ticker] || 0) > 1.0 ? C.watch : C.safe }}>
                    {fmtBeta(st.beta || betas[st.ticker] || 0)}
                  </td>
                )}
                <td style={{ padding: "5px 8px", textAlign: "right", color: C.text, fontSize: 10 }}>
                  {fmtPrice(st.current_price || 0)}
                </td>
                <td style={{ padding: "5px 6px" }}>
                  <StatusBar breakdown={st.status_breakdown} />
                </td>
              </tr>
            ))}
            {residual && (
              <tr style={{ borderTop: `1px solid ${C.border}` }}>
                <td style={{ padding: "5px 8px" }}>
                  <span style={{ color: "#555", marginRight: 4 }}>{"\u25CF"}</span>
                  <span style={{ color: C.muted }}>기타 (Top 10 외)</span>
                </td>
                <td style={{ padding: "5px 8px", textAlign: "right", color: C.muted }}>
                  {fmtBillion(residual.credit_billion)}
                </td>
                <td style={{ padding: "5px 8px", textAlign: "right", color: C.muted }}>
                  {total > 0 ? ((residual.credit_billion / total) * 100).toFixed(1) : "0"}%
                </td>
                <td style={{ padding: "5px 8px", textAlign: "right", color: C.dim }}>
                  {residual.kospi_weight_pct?.toFixed(1) || "-"}%
                </td>
                {hasBetas && <td style={{ padding: "5px 8px", textAlign: "right", color: C.dim }}>-</td>}
                <td style={{ padding: "5px 8px", textAlign: "right", color: C.dim }}>-</td>
                <td style={{ padding: "5px 6px" }}>
                  <StatusBar breakdown={residual.status_breakdown} />
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Beta info */}
      {hasBetas && (
        <div style={{ marginTop: 8, fontSize: 10, color: C.dim, lineHeight: 1.5, fontFamily: FONT }}>
          Beta: {betas._method || "hybrid"}, Lookback: {betas._lookback || 7}일.
          {" "}Beta {">"} 1.0 = KOSPI보다 큰 하락, {"<"} 1.0 = 방어적.
        </div>
      )}

      {/* Methodology note */}
      <div style={{ marginTop: 4, fontSize: 10, color: C.dim, lineHeight: 1.5, fontFamily: FONT }}>
        * 시가총액 비중으로 신용잔고 배분 (proxy). 상태 판정: 종목 종가 기반 (v1.4.0).
      </div>
    </PanelBox>
  );
}


/* ── Trigger Map Table with optional stock_shocks expand ── */
function TriggerMapTable({ triggerMap }) {
  const [expandedShock, setExpandedShock] = useState(null);
  const weightedMap = STOCK_CREDIT?.weighted_trigger_map || [];
  const tickers = STOCK_CREDIT?.tickers || {};

  const shockColor = (pct) => {
    const abs = Math.abs(pct);
    if (abs <= 5) return C.watch;
    if (abs <= 15) return C.marginCall;
    return C.danger;
  };

  // Use weighted map if available, else COHORT_DATA trigger_map
  const mapToShow = weightedMap.length > 0 ? weightedMap : triggerMap;
  const hasStockShocks = mapToShow.some(r => r.stock_shocks);

  const tickerName = (t) => {
    if (t === "_residual") return "기타";
    return tickers[t]?.name || t;
  };

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: FONT }}>
        <thead>
          <tr style={{ borderBottom: `1px solid ${C.border}` }}>
            {[
              "하락폭",
              "예상 KOSPI",
              "마진콜 (추가 입금 요구 D+2)",
              "반대매매 (강제 청산)",
              ...(hasStockShocks ? ["가중영향"] : []),
            ].map((h) => (
              <th key={h} style={{
                padding: "8px 10px", textAlign: "right", color: C.muted, fontWeight: 600,
                fontSize: 11,
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {mapToShow.map((row) => {
            const isExpanded = expandedShock === row.shock_pct;
            const shocks = row.stock_shocks || {};
            const shockEntries = Object.entries(shocks)
              .filter(([k]) => !k.startsWith("_"))
              .sort((a, b) => a[1] - b[1]);
            const residualShock = shocks._residual;
            return (
              <>{/* eslint-disable-next-line react/jsx-key */}
                <tr
                  key={row.shock_pct}
                  style={{ borderBottom: `1px solid ${C.border}22`, cursor: hasStockShocks ? "pointer" : "default" }}
                  onClick={() => hasStockShocks && setExpandedShock(isExpanded ? null : row.shock_pct)}
                >
                  <td style={{ padding: "8px 10px", textAlign: "right", color: shockColor(row.shock_pct), fontWeight: 700 }}>
                    {hasStockShocks && <span style={{ fontSize: 9, marginRight: 4 }}>{isExpanded ? "\u25BC" : "\u25B6"}</span>}
                    {row.shock_pct}%
                  </td>
                  <td style={{ padding: "8px 10px", textAlign: "right", color: C.text }}>
                    {row.expected_kospi?.toLocaleString()}
                  </td>
                  <td style={{ padding: "8px 10px", textAlign: "right", color: C.marginCall }}>
                    {fmtBillion(row.margin_call_billion)}
                  </td>
                  <td style={{ padding: "8px 10px", textAlign: "right", color: C.danger, fontWeight: 700 }}>
                    {fmtBillion(row.forced_liq_billion)}
                  </td>
                  {hasStockShocks && (
                    <td style={{ padding: "8px 10px", textAlign: "right", color: C.kospi }}>
                      {fmtBillion(row.weighted_impact_billion || 0)}
                    </td>
                  )}
                </tr>
                {isExpanded && shockEntries.length > 0 && (
                  <tr key={`${row.shock_pct}_detail`} style={{ background: `${C.bg}88` }}>
                    <td colSpan={hasStockShocks ? 5 : 4} style={{ padding: "6px 24px", fontSize: 10, color: C.muted, lineHeight: 1.8 }}>
                      <span style={{ color: C.dim, marginRight: 6 }}>{"\u2514"}</span>
                      {shockEntries.map(([t, v], i) => (
                        <span key={t}>
                          <span style={{ color: C.text }}>{tickerName(t)}</span>
                          <span style={{ color: shockColor(v), fontWeight: 600 }}> {v > 0 ? "+" : ""}{v.toFixed(1)}%</span>
                          {i < shockEntries.length - 1 && <span style={{ color: C.dim }}>, </span>}
                        </span>
                      ))}
                      {residualShock != null && (
                        <span>
                          <span style={{ color: C.dim }}>, </span>
                          <span style={{ color: C.muted }}>기타</span>
                          <span style={{ color: shockColor(residualShock), fontWeight: 600 }}> {residualShock > 0 ? "+" : ""}{residualShock.toFixed(1)}%</span>
                        </span>
                      )}
                    </td>
                  </tr>
                )}
              </>
            );
          })}
        </tbody>
      </table>
      {hasStockShocks && (
        <div style={{ fontSize: 10, color: C.dim, marginTop: 4, fontFamily: FONT }}>
          * 종목별 충격: Hybrid Beta 정규화 적용. 가중합 = 입력 충격% 보장. 행 클릭 시 상세.
        </div>
      )}
    </div>
  );
}


/* ── MiniCohortChart: 백테스트 기준일 코호트 바 차트 (축소 버전) ── */
function MiniCohortChart({ cohorts, currentKospi }) {
  if (!cohorts?.length) return null;
  const chartData = cohorts
    .filter(c => c.amount > 0)
    .sort((a, b) => b.entry_kospi - a.entry_kospi)
    .slice(0, 12)
    .map(c => ({
      label: `${c.entry_kospi.toLocaleString()} (${c.entry_date.slice(5)})`,
      amount: Math.round(c.amount),
      status: c.status,
      pnl_pct: c.pnl_pct,
      entry_kospi: c.entry_kospi,
      entry_date: c.entry_date,
      collateral_ratio: c.collateral_ratio,
      liquidated_pct: c.liquidated_pct || 0,
    }));

  if (!chartData.length) return null;
  const kospiIdx = chartData.findIndex(c => c.entry_kospi <= currentKospi);

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: 11, color: C.muted, marginBottom: 4 }}>
        기준일 KOSPI: <span style={{ color: C.kospi, fontWeight: 700 }}>{currentKospi?.toLocaleString()}</span>
        {" "}— 위험 코호트 상위 {chartData.length}개
      </div>
      <ResponsiveContainer width="100%" height={Math.max(120, chartData.length * 24 + 30)}>
        <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 120, left: 70, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={C.border} horizontal={false} />
          <XAxis type="number" {...axisProps} tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : `${v}`} />
          <YAxis type="category" dataKey="label" {...axisProps} width={65} tick={{ fill: C.muted, fontSize: 9 }} />
          <Tooltip content={<CohortTooltip />} cursor={false} wrapperStyle={{ outline: "none" }} />
          <Bar dataKey="amount" radius={[0, 3, 3, 0]} isAnimationActive={false}
            label={({ x, y, width, height, index }) => {
              const entry = chartData[index];
              if (!entry || height < 6) return null;
              const sc = STATUS_COLORS[entry.status] || C.muted;
              return (
                <text x={x + width + 4} y={y + height / 2} textAnchor="start" dominantBaseline="central"
                  style={{ fontSize: 9, fontFamily: FONT, fill: C.muted }}>
                  <tspan>{fmtBillion(entry.amount)}</tspan>
                  <tspan dx={4} fill={sc}>{entry.pnl_pct > 0 ? "+" : ""}{entry.pnl_pct}%</tspan>
                  <tspan dx={3} fill={sc} fontWeight={600}>{STATUS_LABELS[entry.status]}</tspan>
                </text>
              );
            }}
          >
            {chartData.map((entry, i) => (
              <Cell key={i} fill={STATUS_COLORS[entry.status] || C.muted}
                opacity={kospiIdx < 0 || i < kospiIdx ? 0.9 : 0.5} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   Main Component
   ═══════════════════════════════════════════════════ */

export default function CohortAnalysis() {
  const { lifo, fifo, trigger_map, current_kospi, current_fx,
    avg_daily_trading_value_billion, params, portfolio_beta: portfolioBeta = 1.0 } = COHORT_DATA;

  /* ── Section 1: Cohort Distribution ── */
  const [cohortMode, setCohortMode] = useState("LIFO");
  const [guideOpen, setGuideOpen] = useState(true);
  const [cohortDate, setCohortDate] = useState(""); // "" = 오늘(현재)

  /* Section 1 날짜 옵션 (최근 60일) */
  const cohortDateOptions = useMemo(() => {
    if (!COHORT_HISTORY?.snapshots?.length) return [];
    const snaps = COHORT_HISTORY.snapshots;
    return snaps.slice(-60).reverse().map(s => s.date);
  }, []);

  /* Section 1 코호트 — 날짜 선택 시 히스토리에서 복원 */
  const { activeCohorts, cohortKospi } = useMemo(() => {
    if (!cohortDate) {
      return { activeCohorts: cohortMode === "LIFO" ? lifo : fifo, cohortKospi: current_kospi };
    }
    const snap = COHORT_HISTORY?.snapshots?.find(s => s.date === cohortDate);
    if (!snap) return { activeCohorts: [], cohortKospi: current_kospi };
    const dateIdx = MARKET_DATA.findIndex(r => r.date === cohortDate);
    const btBeta = dateIdx >= 0 ? computeBacktestBeta(dateIdx) : portfolioBeta;
    return {
      activeCohorts: reconstructCohorts(COHORT_HISTORY.registry, snap, params, btBeta),
      cohortKospi: snap.kospi || current_kospi,
    };
  }, [cohortDate, cohortMode, lifo, fifo, current_kospi, params, portfolioBeta]);

  const cohortSummary = useMemo(() => {
    const total = activeCohorts.reduce((s, c) => s + c.amount, 0);
    const safe = activeCohorts.filter(c => c.status === "safe").reduce((s, c) => s + c.amount, 0);
    const danger = activeCohorts.filter(c => c.status === "danger").reduce((s, c) => s + c.amount, 0);
    const marginCall = activeCohorts.filter(c => c.status === "marginCall").reduce((s, c) => s + c.amount, 0);
    return {
      total,
      safePct: total > 0 ? ((safe / total) * 100).toFixed(1) : "0",
      dangerPct: total > 0 ? (((danger + marginCall) / total) * 100).toFixed(1) : "0",
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
      if (cohortChartData[i].entry_kospi <= cohortKospi) return i;
    }
    return cohortChartData.length;
  }, [cohortChartData, cohortKospi]);

  /* ── Cohort display: collapse safe cohorts at bottom ── */
  const MAX_VISIBLE = 20;
  const [showAllCohorts, setShowAllCohorts] = useState(false);
  const visibleCohortData = useMemo(() => {
    if (showAllCohorts || cohortChartData.length <= MAX_VISIBLE) return cohortChartData;
    // Show top MAX_VISIBLE (highest entry_kospi = most at risk)
    return cohortChartData.slice(0, MAX_VISIBLE);
  }, [cohortChartData, showAllCohorts]);
  const hiddenCount = cohortChartData.length - visibleCohortData.length;
  const hiddenAmount = hiddenCount > 0
    ? cohortChartData.slice(MAX_VISIBLE).reduce((s, c) => s + c.amount, 0) : 0;

  /* ── Section 3: Simulator ── */
  const [simMode, setSimMode] = useState("whatif"); // "whatif" | "backtest"
  const [selectedBaseDate, setSelectedBaseDate] = useState(""); // backtest 기준일
  const [shock, setShock] = useState(-10);
  const [maxRounds, setMaxRounds] = useState(5);
  const loopMode = "A";
  const [absorptionMode, setAbsorptionMode] = useState("auto");
  const [customAbsorption, setCustomAbsorption] = useState(0.5);
  const [simGuideOpen, setSimGuideOpen] = useState(true);

  /* Auto Absorption Rate */
  const autoAbsorption = useMemo(() => {
    const recentFlows = INVESTOR_FLOWS.slice(-5);
    const avgRetailBuy = recentFlows.reduce((s, f) => s + Math.max(0, f.retail_billion || 0), 0) / recentFlows.length;
    const tradingValue = MARKET_DATA.slice(-5).reduce((s, d) => s + (d.trading_value_billion || 0), 0) / 5;
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

  /* Backtest: 기준일 snapshot + forward 실제 데이터 (MARKET_DATA에서 동적 조회) */
  const baseDateSnapshot = useMemo(() => {
    if (!selectedBaseDate || !COHORT_HISTORY?.snapshots?.length) return null;
    return COHORT_HISTORY.snapshots.find(s => s.date === selectedBaseDate) || null;
  }, [selectedBaseDate]);

  const backtestForward = useMemo(() => {
    if (!selectedBaseDate) return [];
    const idx = MARKET_DATA.findIndex(r => r.date === selectedBaseDate);
    if (idx < 0) return [];
    const fwd = [];
    for (let d = 1; d <= 5; d++) {
      if (idx + d >= MARKET_DATA.length) break;
      const r = MARKET_DATA[idx + d];
      const inv = INVESTOR_FLOWS[idx + d] || {};
      fwd.push({
        day: d,
        date: r.date,
        kospi: r.kospi,
        kospi_change_pct: r.kospi_change_pct,
        individual_billion: inv.individual_billion,
        foreign_billion: inv.foreign_billion,
        institution_billion: inv.institution_billion,
        trading_value_billion: r.trading_value_billion,
      });
    }
    return fwd;
  }, [selectedBaseDate]);

  /* Available dates for backtest (snapshot dates, newest first) */
  const backtestDateOptions = useMemo(() => {
    if (!COHORT_HISTORY?.snapshots?.length) return [];
    return [...COHORT_HISTORY.snapshots].reverse().map(s => s.date);
  }, []);

  /* Backtest: 기준일의 위험 코호트 요약 */
  const backtestCohortSummary = useMemo(() => {
    if (!baseDateSnapshot) return null;
    // v1.4.0: Compute beta for the selected base date
    const dateIdx = MARKET_DATA.findIndex(r => r.date === selectedBaseDate);
    const btBeta = dateIdx >= 0 ? computeBacktestBeta(dateIdx) : portfolioBeta;
    const cohorts = reconstructCohorts(COHORT_HISTORY.registry, baseDateSnapshot, params, btBeta);
    const total = cohorts.reduce((s, c) => s + c.amount, 0);
    const byStatus = { danger: 0, marginCall: 0, watch: 0, safe: 0 };
    cohorts.forEach(c => { byStatus[c.status] = (byStatus[c.status] || 0) + c.amount; });
    const riskCohorts = cohorts
      .filter(c => c.status === "danger" || c.status === "marginCall" || c.status === "watch")
      .sort((a, b) => {
        const order = { danger: 0, marginCall: 1, watch: 2 };
        return (order[a.status] ?? 3) - (order[b.status] ?? 3) || b.amount - a.amount;
      })
      .slice(0, 8);
    return { total, byStatus, riskCohorts, count: cohorts.length, allCohorts: cohorts };
  }, [baseDateSnapshot, params]);

  const handleRun = useCallback(() => {
    let cohorts, initialPrice, initialFx, beta;

    if (simMode === "backtest" && baseDateSnapshot) {
      // v1.4.0: Compute beta from base date's prior 7 trading days
      const dateIdx = MARKET_DATA.findIndex(r => r.date === selectedBaseDate);
      beta = dateIdx >= 0 ? computeBacktestBeta(dateIdx) : portfolioBeta;
      cohorts = reconstructCohorts(COHORT_HISTORY.registry, baseDateSnapshot, params, beta);
      initialPrice = baseDateSnapshot.kospi || current_kospi;
      initialFx = baseDateSnapshot.usd_krw || current_fx;
    } else {
      beta = portfolioBeta;
      cohorts = activeCohorts;
      initialPrice = current_kospi;
      initialFx = current_fx;
    }

    const result = runSimulation({
      cohorts,
      initialPrice,
      initialFx,
      shockPct: shock,
      maxRounds,
      absorptionRate,
      loopMode,
      avgTradingValue: avg_daily_trading_value_billion,
      impactCoef: params.impact_coefficient,
      params,
      portfolioBeta: beta,
    });
    setSimResult(result);
  }, [simMode, baseDateSnapshot, selectedBaseDate, activeCohorts, current_kospi, current_fx, shock, maxRounds, absorptionRate,
      avg_daily_trading_value_billion, params, portfolioBeta]);

  /* ── Trigger Map Color ── */
  const shockColor = (pct) => {
    const abs = Math.abs(pct);
    if (abs <= 5) return C.watch;
    if (abs <= 15) return C.marginCall;
    return C.danger;
  };

  return (
    <div>
      {/* ══════════════════════════════════════════
          Section 1: Cohort Distribution
          ══════════════════════════════════════════ */}
      <PanelBox>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
          <SectionTitle termKey="cohort">Cohort Distribution</SectionTitle>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <select
              value={cohortDate}
              onChange={(e) => setCohortDate(e.target.value)}
              style={{
                background: C.bg, color: cohortDate ? C.samsung : C.text,
                border: `1px solid ${cohortDate ? C.samsung : C.border}`,
                borderRadius: 6, padding: "4px 10px", fontSize: 11, fontFamily: FONT,
              }}
            >
              <option value="">오늘 ({current_kospi.toLocaleString()})</option>
              {cohortDateOptions.map((d) => {
                const snap = COHORT_HISTORY.snapshots.find(s => s.date === d);
                return <option key={d} value={d}>{d} | {snap?.kospi?.toLocaleString()}</option>;
              })}
            </select>
            {!cohortDate && (
              <ToggleGroup
                options={[{ id: "LIFO", label: "LIFO" }, { id: "FIFO", label: "FIFO" }]}
                value={cohortMode} onChange={setCohortMode}
              />
            )}
          </div>
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
                <span><span style={{ color: C.safe }}>&#9632;</span> 안전</span>
                <span><span style={{ color: C.watch }}>&#9632;</span> 주의</span>
                <span><span style={{ color: C.marginCall }}>&#9632;</span> 마진콜</span>
                <span><span style={{ color: C.danger }}>&#9632;</span> 위험</span>
              </div>
              <div style={{ marginTop: 6, fontSize: 11, color: C.dim, lineHeight: 1.6 }}>
                개별주식 신용거래 기반 (ETF 제외). 상위 5개 증권사 일괄 기준:<br/>
                보증금 45% | 담보유지 140% | 손실 39%↑ 반대매매 | D+2 미납 → D+3 강제청산
              </div>
            </div>
          )}
        </div>

        {/* Summary Cards */}
        <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
          <SummaryCard label="Active Cohorts" value={cohortSummary.count} />
          <SummaryCard label="Total Balance" value={(cohortSummary.total / 1000).toFixed(1)} unit="조원" />
          <SummaryCard label="Safe Ratio" value={cohortSummary.safePct} unit="%" color={C.safe} />
          <SummaryCard label="Risk Ratio" value={cohortSummary.dangerPct} unit="%" color={C.danger} />
          <SummaryCard label="Portfolio Beta" value={portfolioBeta.toFixed(2)} color={portfolioBeta > 1.0 ? C.danger : C.safe} />
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
          {cohortDate ? `${cohortDate} ` : "현재 "}KOSPI: <span style={{ color: C.kospi, fontWeight: 700 }}>{cohortKospi.toLocaleString()}</span>
          — 위 코호트는 손실, 아래 코호트는 이익
        </div>

        {/* Individual Cohort Bars */}
        <ResponsiveContainer width="100%" height={Math.max(200, visibleCohortData.length * 28 + 60)}>
          <BarChart
            data={visibleCohortData}
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
                  entry={visibleCohortData[index]}
                />
              )}
            >
              {visibleCohortData.map((entry, i) => (
                <Cell
                  key={i}
                  fill={STATUS_COLORS[entry.status] || C.muted}
                  opacity={i < currentKospiIdx ? 0.9 : 0.5}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        {/* Collapsed cohorts indicator + expand/collapse button */}
        {(hiddenCount > 0 || showAllCohorts) && cohortChartData.length > MAX_VISIBLE && (
          <div style={{ textAlign: "center", marginTop: 4 }}>
            <button onClick={() => setShowAllCohorts(!showAllCohorts)} style={{
              background: "transparent", color: C.dim, border: `1px solid ${C.border}`,
              borderRadius: 6, padding: "5px 16px", fontSize: 11, cursor: "pointer",
              fontFamily: FONT, transition: "all 0.15s",
            }}>
              {showAllCohorts
                ? "접기"
                : `+${hiddenCount}개 안전 코호트 더보기 (${fmtBillion(hiddenAmount)})`
              }
            </button>
          </div>
        )}

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
          Section 1.5: Stock Credit Breakdown (v1.3.0)
          ══════════════════════════════════════════ */}
      <StockCreditBreakdown />

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

        <TriggerMapTable triggerMap={trigger_map} />
      </PanelBox>

      {/* ══════════════════════════════════════════
          Section 3: Simulator (What-if + Backtest)
          ══════════════════════════════════════════ */}
      <PanelBox>
        <SectionTitle termKey="forced_liq">반대매매 연쇄 시뮬레이터</SectionTitle>

        {/* Mode Toggle */}
        <div style={{ marginBottom: 14 }}>
          <ToggleGroup
            options={[
              { id: "whatif", label: "오늘 (What-if)" },
              { id: "backtest", label: "과거 검증 (Backtest)" },
            ]}
            value={simMode}
            onChange={(v) => { setSimMode(v); setSimResult(null); }}
          />
        </div>

        {/* Guide Box */}
        <div style={{
          background: `${C.bg}cc`, border: `1px solid ${C.border}`,
          borderRadius: 8, padding: simGuideOpen ? "12px 16px" : "8px 16px",
          marginBottom: 14, cursor: "pointer", transition: "all 0.2s",
        }} onClick={() => setSimGuideOpen(!simGuideOpen)}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: C.text, fontFamily: FONT }}>
              {simMode === "whatif" ? "반대매매 연쇄 시뮬레이터란?" : "백테스트 모드란?"}
            </span>
            <span style={{ fontSize: 12, color: C.dim }}>{simGuideOpen ? "\u25B2" : "\u25BC"}</span>
          </div>
          {simGuideOpen && (
            <div style={{ marginTop: 8, fontSize: 12, color: C.muted, lineHeight: 1.7, fontFamily: FONT }}>
              {simMode === "whatif" ? (
                <>
                  <div>
                    KOSPI가 급락하면 신용매수 투자자의 담보가 부족해져 증권사가 강제 매도(반대매매)합니다.
                    이 매도 물량이 추가 하락을 일으키고, 다시 반대매매를 유발하는 악순환을 시뮬레이션합니다.
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <span style={{ color: C.danger }}>연쇄 구조</span>: 주가&#8595; &#8594; 담보부족 &#8594; 강제매도 &#8594; 추가하락 &#8594; 반복
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <strong>1.</strong> 기준일 선택 — 충격 직전 날짜 (해당일의 코호트를 복원)<br/>
                    <strong>2.</strong> 초기 충격 입력 — 기준일 다음에 실제 발생한 (또는 가정할) 하락률<br/>
                    <strong>3.</strong> 시뮬 실행 → 기준일+1~+5 실제 데이터와 비교
                  </div>
                  <div style={{ marginTop: 8, padding: "8px 12px", background: `${C.panel}aa`, borderRadius: 6, borderLeft: `2px solid ${C.samsung}` }}>
                    <span style={{ color: C.samsung }}>예시:</span> 2/26 선택 → -7.25% 입력 → 3/3의 급락으로 인한 반대매매 연쇄를 시뮬 → 3/4~3/7 실제와 비교
                  </div>
                </>
              )}
              <div style={{ marginTop: 8, padding: "8px 12px", background: `${C.panel}aa`, borderRadius: 6, borderLeft: `2px solid ${C.foreign}` }}>
                <span style={{ color: C.foreign }}>v1.4.0 Beta 가중 모델:</span> 종목별 Hybrid Beta(하방60%+상방40%)를 가중평균하여
                포트폴리오 Beta({portfolioBeta.toFixed(2)})로 충격을 증폭합니다.
                Beta {">"} 1.0이면 KOSPI 대비 더 큰 손실, {"<"} 1.0이면 방어적입니다.
                백테스트 시 기준일 직전 7일로 Beta를 재계산합니다.
              </div>
            </div>
          )}
        </div>

        {/* Backtest: Base Date Selector */}
        {simMode === "backtest" && backtestDateOptions.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 12, color: C.muted, marginBottom: 4, fontWeight: 600 }}>
              Step 1. 기준일 선택 (충격 전날)
            </div>
            <select
              value={selectedBaseDate}
              onChange={(e) => { setSelectedBaseDate(e.target.value); setSimResult(null); }}
              style={{
                background: C.bg, color: C.text, border: `1px solid ${C.border}`,
                borderRadius: 6, padding: "6px 12px", fontSize: 12, fontFamily: FONT,
                width: "100%", maxWidth: 400,
              }}
            >
              <option value="">-- 기준일 선택 --</option>
              {backtestDateOptions.map((date) => {
                const snap = COHORT_HISTORY.snapshots.find(s => s.date === date);
                return (
                  <option key={date} value={date}>
                    {date} | KOSPI {snap?.kospi?.toLocaleString() || "?"}
                  </option>
                );
              })}
            </select>
            {baseDateSnapshot && (
              <div style={{
                marginTop: 8, padding: "10px 14px", background: `${C.bg}cc`,
                border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 12, lineHeight: 1.8,
              }}>
                <div style={{ color: C.text, fontWeight: 600, marginBottom: 4 }}>
                  기준일: {selectedBaseDate} — KOSPI {baseDateSnapshot.kospi?.toLocaleString()}
                </div>
                <div style={{ color: C.muted }}>
                  이 날의 코호트 상태가 복원됩니다. 아래에서 <strong>초기 충격</strong>을 입력하세요.
                </div>
                {/* Show next-day actual if available */}
                {backtestForward.length > 0 && (
                  <div style={{ marginTop: 6, color: C.dim, fontSize: 11 }}>
                    참고 — 다음 거래일({backtestForward[0].date}):
                    KOSPI {backtestForward[0].kospi?.toLocaleString()}{" "}
                    (<span style={{ color: (backtestForward[0].kospi_change_pct || 0) < 0 ? C.danger : C.safe, fontWeight: 600 }}>
                      {(backtestForward[0].kospi_change_pct || 0) > 0 ? "+" : ""}{backtestForward[0].kospi_change_pct}%
                    </span>)
                  </div>
                )}

                {/* Risk cohort summary for base date */}
                {backtestCohortSummary && (
                  <div style={{ marginTop: 10, borderTop: `1px solid ${C.border}44`, paddingTop: 8 }}>
                    <div style={{ fontSize: 11, color: C.muted, marginBottom: 4 }}>
                      기준일 코호트 ({backtestCohortSummary.count}개, 총 {fmtBillion(backtestCohortSummary.total)}):
                      {Object.entries(backtestCohortSummary.byStatus).map(([s, amt]) =>
                        amt > 0 ? (
                          <span key={s} style={{ marginLeft: 8 }}>
                            <span style={{ color: STATUS_COLORS[s] }}>&#9632;</span>{" "}
                            {STATUS_LABELS[s]} {fmtBillion(amt)}
                          </span>
                        ) : null
                      )}
                    </div>
                    <MiniCohortChart
                      cohorts={backtestCohortSummary.allCohorts}
                      currentKospi={baseDateSnapshot?.kospi || current_kospi}
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Controls */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 14 }}>
          <div>
            {/* Initial Shock + Presets */}
            <SliderControl label="초기 충격 (Initial Shock)" value={shock} min={-50} max={-1}
              onChange={setShock} format={(v) => `${v}%`} termKey="initial_shock" />
            {simMode === "whatif" && (
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
            )}

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
          {simMode === "whatif" ? "시뮬레이션 실행" : "백테스트 실행"}
        </button>

        {/* Results */}
        {simResult && (
          <>
            {/* Summary Cards */}
            <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
              <SummaryCard label="초기 KOSPI" value={simResult.initialPrice.toLocaleString()} color={C.muted} />
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

            {/* Backtest Comparison (only in backtest mode) */}
            {simMode === "backtest" && backtestForward.length > 0 && (
              <BacktestComparison
                simResult={simResult}
                forward={backtestForward}
                baseKospi={baseDateSnapshot?.kospi || current_kospi}
                absorptionRate={absorptionRate}
                params={params}
              />
            )}
          </>
        )}

        {!simResult && (
          <div style={{ textAlign: "center", padding: 24, color: C.dim, fontSize: 13 }}>
            {simMode === "whatif"
              ? <>파라미터를 설정하고 <strong>시뮬레이션 실행</strong>을 클릭하세요.</>
              : <>기준일을 선택하고, 충격%를 입력한 뒤 <strong>백테스트 실행</strong>을 클릭하세요.</>
            }
          </div>
        )}
      </PanelBox>

      {/* ══════════════════════════════════════════
          Section 4: Reliability Dashboard
          ══════════════════════════════════════════ */}
      <ReliabilityDashboard
        params={params}
        registry={COHORT_HISTORY?.registry}
        snapshots={COHORT_HISTORY?.snapshots}
        backtestDates={BACKTEST_DATES}
        avgTradingValue={avg_daily_trading_value_billion}
        autoAbsorption={autoAbsorption}
        portfolioBeta={portfolioBeta}
      />
    </div>
  );
}
