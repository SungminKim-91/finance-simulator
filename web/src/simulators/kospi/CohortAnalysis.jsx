import { useState, useMemo, useCallback } from "react";
import {
  /* ComposedChart, — v1.6.1: Section 3 주석 처리 */
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
  COHORT_DATA, /* INVESTOR_FLOWS, */ MARKET_DATA, /* SHORT_SELLING, */
  COHORT_HISTORY, STOCK_CREDIT, VLPI_DATA, VLPI_CONFIG,
} from "./data/kospi_data";

const FONT = "'JetBrains Mono', monospace";

const STATUS_COLORS = { safe: C.safe, watch: C.watch, marginCall: C.marginCall, danger: C.danger };
const STATUS_LABELS = {
  safe: "안전", watch: "주의", marginCall: "마진콜", danger: "위험",
};

/* ── v1.6.0: 6-stage status ── */
const STATUS_COLORS_6 = {
  safe: C.safe6, good: C.good6, caution: C.caution6,
  marginCall: C.marginCall6, forcedLiq: C.forcedLiq6, debtExceed: C.debtExceed6,
};
const STATUS_LABELS_6 = {
  safe: "안전", good: "양호", caution: "주의",
  marginCall: "마진콜", forcedLiq: "강제청산", debtExceed: "채무초과",
};
const STATUS_ORDER_6 = ["debtExceed", "forcedLiq", "marginCall", "caution", "good", "safe"];

function normalizeStatus6(s) {
  if (!s) return null;
  const MAP = { debt_exceed: "debtExceed", forced_liq: "forcedLiq", margin_call: "marginCall" };
  return MAP[s] || s;
}

/* ── VLPI variable key mapping ── */
const VLPI_VAR_KEY_MAP = {
  v1: "caution_zone", v2: "credit_momentum", v3: "policy_shock",
  v4: "overnight_gap", v5: "cumulative_decline", v6: "individual_flow",
};
const VLPI_VAR_COLORS = {
  caution_zone: C.vlpiV1, credit_momentum: C.vlpiV2, policy_shock: C.vlpiV3,
  overnight_gap: C.vlpiV4, cumulative_decline: C.vlpiV5, individual_flow: C.vlpiV6,
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
/* v1.6.1: SliderControl + SimTooltip 주석 처리 (Section 3 복원 시 함께 복원)
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
*/

/* ── Cohort Bar Custom Label (6-stage) ── */
function CohortBarLabel({ x, y, width, height, entry }) {
  if (!entry || height < 8) return null;
  const s6 = entry.status_6 || entry.status;
  const statusColor = STATUS_COLORS_6[s6] || STATUS_COLORS[entry.status] || C.muted;
  const statusText = STATUS_LABELS_6[s6] || STATUS_LABELS[entry.status] || entry.status;
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

/* ── Cohort Bar Tooltip (6-stage) ── */
function CohortTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  const s6 = d.status_6 || d.status;
  const statusColor = STATUS_COLORS_6[s6] || STATUS_COLORS[d.status] || C.muted;
  const statusText = STATUS_LABELS_6[s6] || STATUS_LABELS[d.status] || d.status;
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
        {" → "}<span style={{ color: statusColor }}>{statusText}</span>
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

/* v1.6.1: 6-stage status for reconstructed cohorts */
function classifyStatus6(collateralRatio, lossPct, pnlPct) {
  if (pnlPct <= -100) return "debt_exceed";
  if (lossPct >= FORCED_LIQ_LOSS_PCT) return "forced_liq";
  if (collateralRatio < MAINTENANCE_RATIO) return "margin_call";
  if (collateralRatio < MAINTENANCE_RATIO + 0.10) return "caution";
  if (collateralRatio < MAINTENANCE_RATIO + 0.20) return "good";
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
    const status6 = classifyStatus6(collRatio, lossPct, pnlPct);

    // v1.4.1: danger/forced_liq → 전량 청산 (반대매매 확정)
    if (status === "danger") continue;

    cohorts.push({
      entry_date: entryDate,
      entry_kospi: entryKospi,
      amount,
      pnl_pct: pnlPct,
      collateral_ratio: +collRatio.toFixed(3),
      status,
      status_6: status6,
      liquidated_pct: 0,
    });
  }
  return cohorts;
}


/* ── Forced Liquidation Simulation Engine (distribution-based, v1.4.0 beta-aware) ── */
/* v1.6.1: runSimulation 주석 처리 (Section 3 복원 시 함께 복원)
function runSimulation({
  cohorts, initialPrice, initialFx, shockPct, maxRounds,
  absorptionRate, loopMode, avgTradingValue, impactCoef, params,
  portfolioBeta = 1.0,
}) {
  // ... (see git history for full implementation)
}
*/



/* ── Stock Credit Breakdown (v1.3.0) ── */
const STOCK_COLORS = [
  "#4fc3f7", "#81c784", "#ffb74d", "#e57373", "#ba68c8",
  "#4dd0e1", "#aed581", "#ffd54f", "#f06292", "#7986cb", "#90a4ae",
];

function StockCreditBreakdown({ selectedDate }) {
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

  // Status bar helper (6-stage v1.6.0)
  const StatusBar = ({ breakdown }) => {
    if (!breakdown) return null;
    const segments = [
      { key: "safe", color: C.safe6 }, { key: "good", color: C.good6 },
      { key: "caution", color: C.caution6 }, { key: "watch", color: C.caution6 },
      { key: "margin_call", color: C.marginCall6 }, { key: "forced_liq", color: C.forcedLiq6 },
      { key: "debt_exceed", color: C.debtExceed6 },
    ];
    const t = segments.reduce((s, sg) => s + (breakdown[sg.key] || 0), 0);
    if (t <= 0) return <span style={{ color: C.dim }}>-</span>;
    return (
      <div style={{ display: "flex", height: 14, borderRadius: 3, overflow: "hidden", minWidth: 60 }}>
        {segments.map(sg => {
          const v = breakdown[sg.key] || 0;
          return v > 0 ? <div key={sg.key} style={{ width: `${(v / t) * 100}%`, background: sg.color }} /> : null;
        })}
      </div>
    );
  };

  return (
    <PanelBox>
      <SectionTitle termKey="stock_credit">종목별 신용잔고 (Stock Credit)</SectionTitle>

      {/* Date badge */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8, marginBottom: 8,
        fontSize: 12, fontFamily: FONT,
      }}>
        <span style={{
          padding: "3px 10px", borderRadius: 4, fontWeight: 600,
          background: selectedDate ? `${C.samsung}22` : `${C.safe}22`,
          color: selectedDate ? C.samsung : C.safe,
          border: `1px solid ${selectedDate ? C.samsung : C.safe}44`,
        }}>
          {selectedDate ? `기준일: ${selectedDate}` : "오늘 (최신)"}
        </span>
      </div>

      {/* 과거 날짜 선택 시: 데이터 없음 안내 */}
      {selectedDate ? (
        <div style={{
          padding: "20px 16px", textAlign: "center",
          background: `${C.bg}cc`, border: `1px dashed ${C.border}`,
          borderRadius: 8, fontFamily: FONT,
        }}>
          <div style={{ fontSize: 13, color: C.muted, fontWeight: 600, marginBottom: 6 }}>
            {selectedDate} 의 종목별 신용잔고 데이터가 없습니다
          </div>
          <div style={{ fontSize: 11, color: C.dim, lineHeight: 1.6 }}>
            종목별 신용잔고는 최신(오늘) 스냅샷만 제공됩니다.
            과거 종목별 데이터는 백엔드 히스토리 확장 후 지원 예정입니다.
          </div>
        </div>
      ) : (
      <>
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
              {hasBetas && <th style={{ padding: "6px 8px", textAlign: "right", color: C.muted, fontWeight: 600 }}>Beta <TermHint dataKey="hybrid_beta" /></th>}
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
      </>
      )}
    </PanelBox>
  );
}


/* ── VLPI Gauge (SVG semicircle, v1.6.0) ── */
function VLPIGauge({ score, level, levels }) {
  const w = 240, h = 140, cx = 120, cy = 120, r = 90, thickness = 22;
  const ri = r - thickness;

  const arc = (startDeg, endDeg, radius) => {
    const s = (Math.PI / 180) * startDeg;
    const e = (Math.PI / 180) * endDeg;
    const x1 = cx + radius * Math.cos(s), y1 = cy - radius * Math.sin(s);
    const x2 = cx + radius * Math.cos(e), y2 = cy - radius * Math.sin(e);
    const large = endDeg - startDeg > 180 ? 1 : 0;
    return `M${x1},${y1} A${radius},${radius} 0 ${large} 0 ${x2},${y2}`;
  };

  // Build segment paths (180° = left, 0° = right)
  const segments = levels.map(lv => {
    const startDeg = 180 - (lv.min / 100) * 180;
    const endDeg = 180 - (lv.max / 100) * 180;
    return { ...lv, startDeg: Math.min(startDeg, endDeg), endDeg: Math.max(startDeg, endDeg) };
  });

  // Needle angle
  const clampedScore = Math.max(0, Math.min(100, score));
  const needleAngle = (Math.PI / 180) * (180 - (clampedScore / 100) * 180);
  const needleLen = r - 8;
  const nx = cx + needleLen * Math.cos(needleAngle);
  const ny = cy - needleLen * Math.sin(needleAngle);

  const levelLabel = levels.find(lv => score >= lv.min && score < lv.max)?.label
    || levels[levels.length - 1]?.label || "";
  const levelColor = levels.find(lv => score >= lv.min && score < lv.max)?.color
    || levels[levels.length - 1]?.color || C.muted;

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: "block" }}>
      {segments.map((seg, i) => (
        <path key={i} d={arc(seg.startDeg, seg.endDeg, r)}
          fill="none" stroke={seg.color} strokeWidth={thickness} strokeLinecap="butt" opacity={0.7} />
      ))}
      {/* Inner track */}
      <path d={arc(0, 180, ri)} fill="none" stroke={C.border} strokeWidth={2} />
      {/* Needle */}
      <line x1={cx} y1={cy} x2={nx} y2={ny} stroke={C.text} strokeWidth={2.5} strokeLinecap="round" />
      <circle cx={cx} cy={cy} r={5} fill={C.text} />
      {/* Score text */}
      <text x={cx} y={cy - 24} textAnchor="middle" fill={C.text}
        style={{ fontSize: 32, fontWeight: 700, fontFamily: FONT }}>{score.toFixed(1)}</text>
      <text x={cx} y={cy - 2} textAnchor="middle" fill={levelColor}
        style={{ fontSize: 14, fontWeight: 600, fontFamily: FONT }}>{levelLabel}</text>
      {/* Min/Max labels */}
      <text x={cx - r - 4} y={cy + 14} textAnchor="end" fill={C.dim}
        style={{ fontSize: 10, fontFamily: FONT }}>0</text>
      <text x={cx + r + 4} y={cy + 14} textAnchor="start" fill={C.dim}
        style={{ fontSize: 10, fontFamily: FONT }}>100</text>
    </svg>
  );
}

/* ── VLPI Component Breakdown (v1.6.0) ── */
function ComponentBreakdown({ components, variables, weights }) {
  if (!components || !variables) return null;
  const data = variables.map(v => {
    const varKey = VLPI_VAR_KEY_MAP[v.key];
    return {
      name: v.label,
      value: components[varKey] || 0,
      raw: VLPI_DATA?.latest?.raw_variables?.[v.key] ?? "-",
      weight: weights[v.weight_key] || 0,
      color: VLPI_VAR_COLORS[varKey] || C.muted,
      desc: v.desc,
    };
  });
  const maxVal = Math.max(...data.map(d => d.value), 1);

  return (
    <div>
      <div style={{ fontSize: 12, color: C.muted, marginBottom: 8, fontWeight: 600 }}>
        구성요소 기여분 <TermLabel dataKey="vlpi_component" color={C.dim} />
      </div>
      {data.map((d, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <div style={{ width: 80, fontSize: 11, color: C.muted, textAlign: "right", flexShrink: 0 }}>
            {d.name}
          </div>
          <div style={{ flex: 1, height: 16, background: C.bg, borderRadius: 3, overflow: "hidden", position: "relative" }}>
            <div style={{
              width: `${maxVal > 0 ? (d.value / maxVal) * 100 : 0}%`,
              height: "100%", background: d.color, borderRadius: 3,
              transition: "width 0.3s",
            }} />
          </div>
          <div style={{ width: 40, fontSize: 11, color: d.value > 0 ? C.text : C.dim, fontWeight: 600, textAlign: "right", fontFamily: FONT }}>
            {d.value.toFixed(1)}
          </div>
        </div>
      ))}
      <div style={{ fontSize: 10, color: C.dim, marginTop: 4 }}>
        합계: {data.reduce((s, d) => s + d.value, 0).toFixed(1)} | 가중치: {variables.map(v => `${v.label.slice(0, 2)}=${((weights[v.weight_key] || 0) * 100).toFixed(0)}%`).join(", ")}
      </div>
    </div>
  );
}

/* ── VLPI Impact Table (v1.6.0) ── */
function ImpactTable({ scenarios, currentVlpi }) {
  if (!scenarios?.length) return null;
  // Find closest scenario to current VLPI
  let closestIdx = 0;
  let minDiff = Infinity;
  scenarios.forEach((s, i) => {
    const diff = Math.abs(s.pre_vlpi - currentVlpi);
    if (diff < minDiff) { minDiff = diff; closestIdx = i; }
  });

  const fmtSellVol = (v) => {
    if (!v || v <= 0) return "-";
    // sell_volume_억 is in 억원
    if (v >= 10000) return `${(v / 10000).toFixed(0)}조원`;
    return `${v.toLocaleString()}억원`;
  };

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 12, color: C.muted, marginBottom: 8, fontWeight: 600 }}>
        시나리오 매트릭스 <TermLabel dataKey="vlpi_impact" color={C.dim} />
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: FONT }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {["시나리오", "EWY 변동", "정책쇼크", "Pre-VLPI", "매도추정", "매도비율"].map(h => (
                <th key={h} style={{ padding: "6px 10px", textAlign: "right", color: C.muted, fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {scenarios.map((s, i) => {
              const isHighlight = i === closestIdx;
              return (
                <tr key={s.label} style={{
                  borderBottom: `1px solid ${C.border}22`,
                  background: isHighlight ? `${C.kospi}15` : "transparent",
                }}>
                  <td style={{ padding: "6px 10px", textAlign: "right", color: isHighlight ? C.text : C.muted, fontWeight: isHighlight ? 700 : 400 }}>
                    {isHighlight && <span style={{ color: C.kospi, marginRight: 4 }}>{"\u25B6"}</span>}
                    {s.label}
                  </td>
                  <td style={{ padding: "6px 10px", textAlign: "right", color: s.ewy_change_pct >= 0 ? C.safe : C.danger }}>
                    {s.ewy_change_pct > 0 ? "+" : ""}{s.ewy_change_pct}%
                  </td>
                  <td style={{ padding: "6px 10px", textAlign: "right", color: s.policy_shock ? C.danger : C.dim }}>
                    {s.policy_shock ? "Yes" : "No"}
                  </td>
                  <td style={{ padding: "6px 10px", textAlign: "right", color: C.text, fontWeight: 600 }}>
                    {s.pre_vlpi}
                  </td>
                  <td style={{ padding: "6px 10px", textAlign: "right", color: C.marginCall6 }}>
                    {fmtSellVol(s.sell_volume_억)}
                  </td>
                  <td style={{ padding: "6px 10px", textAlign: "right", color: C.muted }}>
                    {s.sell_ratio_pct?.toFixed(1) || "-"}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Cohort Risk Map (v1.6.0) ── */
function CohortRiskMap({ cohorts, thresholds }) {
  if (!cohorts?.length) return null;
  const data = cohorts
    .filter(c => c.amount > 0 && c.collateral_ratio > 0)
    .map((c, i) => {
      const s6 = normalizeStatus6(c.status_6) || c.status;
      return {
        idx: i,
        collateral_pct: +(c.collateral_ratio * 100).toFixed(1),
        amount: c.amount,
        entry_kospi: c.entry_kospi,
        entry_date: c.entry_date,
        status_6: s6,
        color: STATUS_COLORS_6[s6] || STATUS_COLORS[c.status] || C.muted,
      };
    })
    .filter(d => d.collateral_pct >= 80 && d.collateral_pct <= 250);

  if (!data.length) return null;

  const thresholdLines = [
    { y: 170, label: "양호(170%)", color: C.good6 },
    { y: 155, label: "주의(155%)", color: C.caution6 },
    { y: 140, label: "마진콜(140%)", color: C.marginCall6 },
    { y: 120, label: "강제청산(120%)", color: C.forcedLiq6 },
    { y: 100, label: "채무초과(100%)", color: C.debtExceed6 },
  ];

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 12, color: C.muted, marginBottom: 8, fontWeight: 600 }}>
        코호트 담보비율 분포 <TermLabel dataKey="risk_map" color={C.dim} />
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <ScatterChart margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
          <XAxis type="number" dataKey="idx" name="코호트" {...axisProps} hide />
          <YAxis type="number" dataKey="collateral_pct" name="담보비율"
            domain={[90, 220]} {...axisProps}
            tickFormatter={v => `${v}%`}
            label={{ value: "담보비율 %", angle: -90, position: "insideLeft", style: { fill: C.muted, fontSize: 10 } }}
          />
          <Tooltip
            contentStyle={{ background: C.panel, border: `1px solid ${C.border}`, fontSize: 11, fontFamily: FONT }}
            formatter={(val, name) => {
              if (name === "담보비율") return [`${val}%`, name];
              return [val, name];
            }}
            labelFormatter={() => ""}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0]?.payload;
              if (!d) return null;
              return (
                <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 6, padding: "8px 12px", fontSize: 11, fontFamily: FONT }}>
                  <div style={{ color: C.text, fontWeight: 600 }}>{d.entry_date} | {d.entry_kospi?.toLocaleString()}</div>
                  <div style={{ color: C.muted }}>담보비율: <span style={{ color: d.color, fontWeight: 700 }}>{d.collateral_pct}%</span></div>
                  <div style={{ color: C.muted }}>잔액: {fmtBillion(d.amount)}</div>
                  <div style={{ color: d.color }}>{STATUS_LABELS_6[d.status_6] || d.status_6}</div>
                </div>
              );
            }}
          />
          {thresholdLines.map(tl => (
            <ReferenceLine key={tl.y} y={tl.y} stroke={tl.color} strokeDasharray="5 3" strokeWidth={1}
              label={{ value: tl.label, position: "right", style: { fill: tl.color, fontSize: 9, fontFamily: FONT } }}
            />
          ))}
          <Scatter data={data} isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.color} opacity={0.8}
                r={Math.max(4, Math.min(12, Math.sqrt(d.amount) * 1.5))} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
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
      status_6: c.status_6,
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
              const s6 = normalizeStatus6(entry.status_6) || entry.status;
              const sc = STATUS_COLORS_6[s6] || STATUS_COLORS[entry.status] || C.muted;
              const sl = STATUS_LABELS_6[s6] || STATUS_LABELS[entry.status] || entry.status;
              return (
                <text x={x + width + 4} y={y + height / 2} textAnchor="start" dominantBaseline="central"
                  style={{ fontSize: 9, fontFamily: FONT, fill: C.muted }}>
                  <tspan>{fmtBillion(entry.amount)}</tspan>
                  <tspan dx={4} fill={sc}>{entry.pnl_pct > 0 ? "+" : ""}{entry.pnl_pct}%</tspan>
                  <tspan dx={3} fill={sc} fontWeight={600}>{sl}</tspan>
                </text>
              );
            }}
          >
            {chartData.map((entry, i) => {
              const s6 = normalizeStatus6(entry.status_6) || entry.status;
              return (
                <Cell key={i} fill={STATUS_COLORS_6[s6] || STATUS_COLORS[entry.status] || C.muted}
                  opacity={kospiIdx < 0 || i < kospiIdx ? 0.9 : 0.5} />
              );
            })}
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

  /* 전체 시장 신용잔고 (MARKET_DATA 최신 유효값) */
  const totalMarketCredit = useMemo(() => {
    for (let i = MARKET_DATA.length - 1; i >= 0; i--) {
      const v = MARKET_DATA[i].credit_balance_billion;
      if (v && v > 0) return v;
    }
    return 0;
  }, []);

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
    const byS6 = {};
    activeCohorts.forEach(c => {
      const s6 = normalizeStatus6(c.status_6) || c.status;
      byS6[s6] = (byS6[s6] || 0) + c.amount;
    });
    const safeGood = (byS6.safe || 0) + (byS6.good || 0);
    const risk = (byS6.marginCall || 0) + (byS6.forcedLiq || 0) + (byS6.debtExceed || 0);
    return {
      total,
      safeGoodPct: total > 0 ? ((safeGood / total) * 100).toFixed(1) : "0",
      cautionPct: total > 0 ? (((byS6.caution || 0) + (byS6.watch || 0)) / total * 100).toFixed(1) : "0",
      riskPct: total > 0 ? ((risk / total) * 100).toFixed(1) : "0",
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
        status_6: c.status_6,
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

  /* ── Section 3: Simulator (v1.6.1: commented out — may restore later) ── */
  /*
  const [simMode, setSimMode] = useState("whatif");
  const [selectedBaseDate, setSelectedBaseDate] = useState("");
  const [shock, setShock] = useState(-10);
  const [maxRounds, setMaxRounds] = useState(5);
  const loopMode = "A";
  const [absorptionMode, setAbsorptionMode] = useState("auto");
  const [customAbsorption, setCustomAbsorption] = useState(0.5);
  const [simGuideOpen, setSimGuideOpen] = useState(true);
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
      fwd.push({ day: d, date: r.date, kospi: r.kospi, kospi_change_pct: r.kospi_change_pct,
        individual_billion: inv.individual_billion, foreign_billion: inv.foreign_billion,
        institution_billion: inv.institution_billion, trading_value_billion: r.trading_value_billion });
    }
    return fwd;
  }, [selectedBaseDate]);
  const backtestDateOptions = useMemo(() => {
    if (!COHORT_HISTORY?.snapshots?.length) return [];
    return [...COHORT_HISTORY.snapshots].reverse().map(s => s.date);
  }, []);
  const backtestCohortSummary = useMemo(() => {
    if (!baseDateSnapshot) return null;
    const dateIdx = MARKET_DATA.findIndex(r => r.date === selectedBaseDate);
    const btBeta = dateIdx >= 0 ? computeBacktestBeta(dateIdx) : portfolioBeta;
    const cohorts = reconstructCohorts(COHORT_HISTORY.registry, baseDateSnapshot, params, btBeta);
    const total = cohorts.reduce((s, c) => s + c.amount, 0);
    const byStatus = { danger: 0, marginCall: 0, watch: 0, safe: 0 };
    cohorts.forEach(c => { byStatus[c.status] = (byStatus[c.status] || 0) + c.amount; });
    return { total, byStatus, count: cohorts.length, allCohorts: cohorts };
  }, [baseDateSnapshot, params]);
  const handleRun = useCallback(() => {
    let cohorts, initialPrice, initialFx, beta;
    if (simMode === "backtest" && baseDateSnapshot) {
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
    const result = runSimulation({ cohorts, initialPrice, initialFx, shockPct: shock,
      maxRounds, absorptionRate, loopMode, avgTradingValue: avg_daily_trading_value_billion,
      impactCoef: params.impact_coefficient, params, portfolioBeta: beta });
    setSimResult(result);
  }, [simMode, baseDateSnapshot, selectedBaseDate, activeCohorts, current_kospi, current_fx, shock, maxRounds, absorptionRate,
      avg_daily_trading_value_billion, params, portfolioBeta]);
  */

  /* ── VLPI data for selected date ── */
  const vlpiForDate = useMemo(() => {
    if (!cohortDate) return VLPI_DATA?.latest || null;
    const h = VLPI_DATA?.history?.find(e => e.date === cohortDate);
    return h || null;
  }, [cohortDate]);
  const vlpiIsExact = !cohortDate || (vlpiForDate?.date === cohortDate);

  return (
    <div>
      {/* ══════════════════════════════════════════
          Global Date Selector (v1.6.1)
          ══════════════════════════════════════════ */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10, marginBottom: 10,
        padding: "8px 14px", background: C.panel, border: `1px solid ${C.border}`,
        borderRadius: 8, flexWrap: "wrap",
      }}>
        <span style={{ fontSize: 12, color: C.muted, fontWeight: 600, fontFamily: FONT }}>기준일</span>
        <select
          value={cohortDate}
          onChange={(e) => setCohortDate(e.target.value)}
          style={{
            background: C.bg, color: cohortDate ? C.samsung : C.text,
            border: `1px solid ${cohortDate ? C.samsung : C.border}`,
            borderRadius: 6, padding: "5px 12px", fontSize: 12, fontFamily: FONT,
          }}
        >
          <option value="">오늘 (KOSPI {current_kospi.toLocaleString()})</option>
          {cohortDateOptions.map((d) => {
            const snap = COHORT_HISTORY.snapshots.find(s => s.date === d);
            return <option key={d} value={d}>{d} | KOSPI {snap?.kospi?.toLocaleString()}</option>;
          })}
        </select>
        {cohortDate && (
          <span style={{ fontSize: 11, color: C.samsung, fontFamily: FONT }}>
            KOSPI {cohortKospi.toLocaleString()}
          </span>
        )}
        {!cohortDate && (
          <div style={{ display: "flex", gap: 3 }}>
            {[
              { id: "LIFO", label: "LIFO", tip: "Last-In First-Out: 최근 진입 코호트를 먼저 청산. 고가 매수자가 먼저 강제매도 당한다는 가정" },
              { id: "FIFO", label: "FIFO", tip: "First-In First-Out: 오래된 코호트를 먼저 청산. 만기 도래순으로 강제매도 당한다는 가정" },
            ].map(o => (
              <button key={o.id} onClick={() => setCohortMode(o.id)} title={o.tip} style={{
                background: cohortMode === o.id ? C.kospi : "transparent",
                color: cohortMode === o.id ? "#fff" : C.muted,
                border: `1px solid ${cohortMode === o.id ? C.kospi : C.border}`,
                borderRadius: 6, padding: "4px 12px", fontSize: 11,
                fontWeight: 600, cursor: "pointer", fontFamily: FONT, transition: "all 0.15s",
              }}>{o.label}</button>
            ))}
          </div>
        )}
      </div>

      {/* ══════════════════════════════════════════
          Section 1: Cohort Distribution
          ══════════════════════════════════════════ */}
      <PanelBox>
        <SectionTitle termKey="cohort">Cohort Distribution</SectionTitle>

        {/* Date badge */}
        <div style={{
          display: "flex", alignItems: "center", gap: 8, marginBottom: 8,
          fontSize: 12, fontFamily: FONT,
        }}>
          <span style={{
            padding: "3px 10px", borderRadius: 4, fontWeight: 600,
            background: cohortDate ? `${C.samsung}22` : `${C.safe}22`,
            color: cohortDate ? C.samsung : C.safe,
            border: `1px solid ${cohortDate ? C.samsung : C.safe}44`,
          }}>
            {cohortDate ? `기준일: ${cohortDate}` : "오늘 (최신)"}
          </span>
          <span style={{ color: C.muted }}>
            KOSPI {cohortKospi.toLocaleString()} | {cohortSummary.count}개 코호트 | 총 {fmtBillion(cohortSummary.total)}
          </span>
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
              <div style={{ display: "flex", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
                {STATUS_ORDER_6.slice().reverse().map(s => (
                  <span key={s}><span style={{ color: STATUS_COLORS_6[s] }}>&#9632;</span> {STATUS_LABELS_6[s]}</span>
                ))}
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
          <SummaryCard label="총 신용잔고" value={(cohortSummary.total / 1000).toFixed(1)} unit="조원" color={C.text} />
          <SummaryCard label="코호트 수" value={cohortSummary.count} />
          <SummaryCard label="안전+양호" value={cohortSummary.safeGoodPct} unit="%" color={C.safe6} />
          <SummaryCard label="주의구간" value={cohortSummary.cautionPct} unit="%" color={C.caution6} />
          <SummaryCard label="위험(마진콜↑)" value={cohortSummary.riskPct} unit="%" color={C.forcedLiq6} />
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
              {visibleCohortData.map((entry, i) => {
                const s6 = normalizeStatus6(entry.status_6) || entry.status;
                return (
                  <Cell
                    key={i}
                    fill={STATUS_COLORS_6[s6] || STATUS_COLORS[entry.status] || C.muted}
                    opacity={i < currentKospiIdx ? 0.9 : 0.5}
                  />
                );
              })}
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
        <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 8, fontSize: 11, fontFamily: FONT }}>
          {STATUS_ORDER_6.slice().reverse().map(s => (
            <span key={s} style={{ display: "flex", alignItems: "center", gap: 3, color: C.muted }}>
              <span style={{ color: STATUS_COLORS_6[s] }}>&#9632;</span> {STATUS_LABELS_6[s]}
            </span>
          ))}
        </div>
      </PanelBox>

      {/* ══════════════════════════════════════════
          Section 1.5: Stock Credit Breakdown (v1.3.0)
          ══════════════════════════════════════════ */}
      <StockCreditBreakdown selectedDate={cohortDate} />

      {/* ══════════════════════════════════════════
          Section 2: VLPI 대시보드 (v1.6.0)
          ══════════════════════════════════════════ */}
      <PanelBox>
        <SectionTitle termKey="pre_vlpi">VLPI 대시보드 (Voluntary Liquidation Pressure Index)</SectionTitle>

        {/* Date badge */}
        <div style={{
          display: "flex", alignItems: "center", gap: 8, marginBottom: 8,
          fontSize: 12, fontFamily: FONT,
        }}>
          <span style={{
            padding: "3px 10px", borderRadius: 4, fontWeight: 600,
            background: cohortDate ? `${C.samsung}22` : `${C.safe}22`,
            color: cohortDate ? C.samsung : C.safe,
            border: `1px solid ${cohortDate ? C.samsung : C.safe}44`,
          }}>
            {cohortDate ? `기준일: ${cohortDate}` : "오늘 (최신)"}
          </span>
          {vlpiIsExact && vlpiForDate && (
            <span style={{ color: C.muted }}>
              VLPI {vlpiForDate.pre_vlpi?.toFixed(1)} | {vlpiForDate.level}
            </span>
          )}
        </div>

        {/* Guide Box */}
        <div style={{
          background: `${C.bg}cc`, border: `1px solid ${C.border}`,
          borderRadius: 8, padding: "12px 16px", marginBottom: 12,
          fontSize: 12, color: C.muted, lineHeight: 1.7, fontFamily: FONT,
        }}>
          <div style={{ fontWeight: 700, color: C.text, marginBottom: 4 }}>VLPI란?</div>
          자발적 투매 압력 지수 (0~100). 6개 변수의 가중합으로 산출합니다.
          반대매매(강제청산) 이전의 <strong>자발적 투매</strong> 압력을 측정하여, 시장 하방 압력을 선행 감지합니다.
          <div style={{ marginTop: 6 }}>
            KOSPI: <span style={{ color: C.kospi, fontWeight: 700 }}>{cohortKospi.toLocaleString()}</span>
          </div>
        </div>

        {vlpiIsExact ? (
          <>
            {/* A + B: Gauge + Breakdown (2-column) — 해당일 VLPI 데이터 있음 */}
            {vlpiForDate && VLPI_CONFIG && (
              <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 20, alignItems: "start", marginBottom: 12 }}>
                <VLPIGauge
                  score={vlpiForDate.pre_vlpi}
                  level={vlpiForDate.level}
                  levels={VLPI_CONFIG.levels}
                />
                <ComponentBreakdown
                  components={vlpiForDate.components}
                  variables={VLPI_CONFIG.variables}
                  weights={VLPI_CONFIG.weights}
                />
              </div>
            )}

            {/* C: Impact Table */}
            {VLPI_DATA?.scenario_matrix && (
              <ImpactTable
                scenarios={VLPI_DATA.scenario_matrix}
                currentVlpi={vlpiForDate?.pre_vlpi || 0}
              />
            )}
          </>
        ) : (
          /* 과거 날짜에 VLPI 히스토리 없음 */
          <div style={{
            padding: "20px 16px", marginBottom: 12, textAlign: "center",
            background: `${C.bg}cc`, border: `1px dashed ${C.border}`,
            borderRadius: 8, fontFamily: FONT,
          }}>
            <div style={{ fontSize: 13, color: C.muted, fontWeight: 600, marginBottom: 6 }}>
              {cohortDate} 의 VLPI 데이터가 없습니다
            </div>
            <div style={{ fontSize: 11, color: C.dim, lineHeight: 1.6 }}>
              VLPI는 당일 시장 데이터(변동성, 모멘텀, 수급 등)가 필요하며, 현재 히스토리에 포함되지 않은 날짜입니다.
              <br/>아래 코호트 리스크맵은 해당일 코호트 기준으로 표시됩니다.
            </div>
          </div>
        )}

        {/* D: Cohort Risk Map — 항상 표시 (activeCohorts 기반, 날짜에 반응) */}
        <CohortRiskMap
          cohorts={activeCohorts}
          thresholds={VLPI_CONFIG?.status_thresholds}
        />
      </PanelBox>

      {/* ══════════════════════════════════════════
          Section 3: Simulator (What-if + Backtest)
          — v1.6.1: 주석 처리 (향후 복원 예정)
          ══════════════════════════════════════════ */}
    </div>
  );
}
