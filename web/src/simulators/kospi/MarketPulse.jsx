import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import {
  ComposedChart,
  Line,
  Area,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  LineChart,
  ReferenceLine,
  Brush,
} from "recharts";
import { C } from "./colors";
import {
  MARKET_DATA,
  CREDIT_DATA,
  INVESTOR_FLOWS,
  GLOBAL_DATA,
  SHORT_SELLING,
  EVENTS,
} from "./data/kospi_data";

const FONT = "'JetBrains Mono', monospace";

const PERIODS = [
  { id: "1M", days: 22 },
  { id: "3M", days: 66 },
  { id: "6M", days: 132 },
  { id: "1Y", days: 252 },
  { id: "ALL", days: 9999 },
];

/* ── Korean Term Dictionary ── */
const TERM = {
  credit_balance_billion: {
    label: "신용잔고 (Credit)",
    desc: "증권사 신용융자 잔고 — 개인투자자 레버리지 수준. 급증 시 반대매매 리스크 증가",
  },
  deposit_billion: {
    label: "고객예탁금 (Deposit)",
    desc: "증권사 예치 투자자 대기 자금. 증가 시 매수 여력 확대, 감소 시 자금 이탈",
  },
  forced_liq_billion: {
    label: "반대매매 (Forced Liq)",
    desc: "담보 부족 강제 청산 금액. 급증 시 시장 하방 압력 가중",
  },
  individual_billion: {
    label: "개인 (Individual)",
    desc: "개인투자자 일별 순매수/순매도 금액",
  },
  foreign_billion: {
    label: "외국인 (Foreign)",
    desc: "외국인투자자 일별 순매수/순매도 금액. 연속 순매도 시 경고",
  },
  institution_billion: {
    label: "기관 (Institution)",
    desc: "기관투자자(연기금·보험·투신 등) 일별 순매수/순매도 금액",
  },
  market_total_billion: {
    label: "공매도 (Short Selling)",
    desc: "전체 시장 공매도 거래대금. 정부 금지 조치 시 급감",
  },
  cum_individual: {
    label: "개인 누적 (Cum. Individual)",
    desc: "개인투자자 누적 순매수 금액",
  },
  cum_foreign: {
    label: "외국인 누적 (Cum. Foreign)",
    desc: "외국인투자자 누적 순매수 금액",
  },
  cum_institution: {
    label: "기관 누적 (Cum. Institution)",
    desc: "기관투자자 누적 순매수 금액",
  },
};

/* ── Shared Styles ── */
const TT = {
  contentStyle: {
    background: C.panel,
    border: `1px solid ${C.border}`,
    borderRadius: 8,
    fontSize: 11,
    fontFamily: FONT,
  },
  labelStyle: { color: C.muted, fontSize: 10 },
};

const axisProps = { stroke: C.dim, fontSize: 10, fontFamily: FONT };

/* ── Nice Scale Algorithm ── */
function niceNum(range, round) {
  const exponent = Math.floor(Math.log10(range));
  const fraction = range / Math.pow(10, exponent);
  let niceFraction;
  if (round) {
    if (fraction < 1.5) niceFraction = 1;
    else if (fraction < 3) niceFraction = 2;
    else if (fraction < 7) niceFraction = 5;
    else niceFraction = 10;
  } else {
    if (fraction <= 1) niceFraction = 1;
    else if (fraction <= 2) niceFraction = 2;
    else if (fraction <= 5) niceFraction = 5;
    else niceFraction = 10;
  }
  return niceFraction * Math.pow(10, exponent);
}

function niceScale(dataMin, dataMax, tickCount = 5) {
  if (!isFinite(dataMin) || !isFinite(dataMax) || dataMin >= dataMax) {
    return { domain: [0, 1], ticks: [0, 0.25, 0.5, 0.75, 1], step: 0.25 };
  }
  const range = niceNum(dataMax - dataMin, false);
  const step = niceNum(range / (tickCount - 1), true);
  const niceMin = Math.floor(dataMin / step) * step;
  const niceMax = Math.ceil(dataMax / step) * step;
  const ticks = [];
  for (let v = niceMin; v <= niceMax + step * 0.01; v += step) {
    ticks.push(Math.round(v * 1e10) / 1e10);
  }
  return { domain: [niceMin, niceMax], ticks, step };
}

/* ── Auto-fit Domain Helper ── */
function fitDomain(data, keys) {
  if (!data || data.length === 0) return [0, 1];
  let min = Infinity;
  let max = -Infinity;
  for (const row of data) {
    for (const k of keys) {
      const v = row[k];
      if (v != null && isFinite(v)) {
        if (v < min) min = v;
        if (v > max) max = v;
      }
    }
  }
  if (!isFinite(min) || !isFinite(max)) return [0, 1];
  if (min === max) {
    const spread = Math.abs(max) * 0.1 || 1;
    return [min - spread, max + spread];
  }
  return [min, max];
}

/* ── Compute Axis with Zoom + niceScale ── */
function computeAxis(data, keys, zoom = 1, tickCount = 5) {
  const [rawMin, rawMax] = fitDomain(data, keys);
  const mid = (rawMin + rawMax) / 2;
  const halfRange = (rawMax - rawMin) / 2 / zoom;
  return niceScale(mid - halfRange, mid + halfRange, tickCount);
}

/* ── Universal Axis Formatter ── */
function fmtAxis(v) {
  const abs = Math.abs(v);
  if (abs === 0) return "0";
  if (abs >= 1000) return `${(v / 1000).toFixed(abs >= 10000 ? 0 : 1)}K`;
  return v.toFixed(abs < 10 ? 1 : 0);
}

/* ── Unit Formatters ── */
// 조원 (값: 십억원 → 조원)
function fmtTril(v) {
  if (v === 0) return "0";
  return (v / 1000).toFixed(Math.abs(v) >= 10000 ? 0 : 1);
}

// 억원 (값: 십억원 → 억원)
function fmtHundM(v) {
  if (v === 0) return "0";
  return (v * 10).toLocaleString();
}

// Tooltip value formatter
function fmtTooltipVal(dataKey, value) {
  if (typeof value !== "number") return value;
  const trilKeys = [
    "credit_balance_billion", "deposit_billion",
    "individual_billion", "foreign_billion", "institution_billion",
    "cum_individual", "cum_foreign", "cum_institution",
  ];
  if (trilKeys.includes(dataKey)) {
    return `${(value / 1000).toFixed(1)} 조원`;
  }
  if (dataKey === "forced_liq_billion") {
    return `${(value * 10).toLocaleString()} 억원`;
  }
  if (dataKey === "market_total_billion") {
    return `${value.toFixed(2)} 십억원`;
  }
  return value.toLocaleString();
}

// YAxis label helper
function yAxisLabel(text, side = "left") {
  return {
    value: text,
    angle: side === "left" ? -90 : 90,
    position: side === "left" ? "insideLeft" : "insideRight",
    style: { fill: C.muted, fontSize: 9, fontFamily: FONT },
  };
}

function fmtDate(d) {
  return d ? d.slice(5) : "";
}

/* ── Sub-components ── */

function SectionTitle({ children }) {
  return (
    <div
      style={{
        color: C.text,
        fontSize: 13,
        fontWeight: 700,
        marginBottom: 8,
        fontFamily: FONT,
      }}
    >
      {children}
    </div>
  );
}

function PanelBox({ children, style }) {
  return (
    <div
      style={{
        background: C.panel,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: 16,
        marginBottom: 12,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/* ── TermLabel with Hover Tooltip ── */
function TermLabel({ dataKey, color }) {
  const [show, setShow] = useState(false);
  const term = TERM[dataKey];
  if (!term) return <span style={{ color, fontSize: 10 }}>{dataKey}</span>;

  return (
    <span
      style={{ position: "relative", display: "inline-block", cursor: "default" }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <span style={{ color, fontSize: 10 }}>● {term.label}</span>
      {show && (
        <div
          style={{
            position: "absolute",
            bottom: "100%",
            left: "50%",
            transform: "translateX(-50%)",
            background: "#1a1a2e",
            border: `1px solid ${C.border}`,
            borderRadius: 6,
            padding: "8px 12px",
            fontSize: 11,
            color: C.text,
            whiteSpace: "nowrap",
            zIndex: 100,
            fontFamily: FONT,
            pointerEvents: "none",
            marginBottom: 4,
            boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
          }}
        >
          {term.desc}
        </div>
      )}
    </span>
  );
}

/* ── Custom Legend ── */
function CustomLegend({ payload }) {
  if (!payload) return null;
  return (
    <div
      style={{
        display: "flex",
        gap: 12,
        justifyContent: "center",
        flexWrap: "wrap",
        fontSize: 10,
        fontFamily: FONT,
      }}
    >
      {payload.map((entry) => (
        <TermLabel
          key={entry.dataKey || entry.value}
          dataKey={entry.dataKey}
          color={entry.color}
        />
      ))}
    </div>
  );
}

/* ── Custom Tooltip Content ── */
function CustomTooltipContent({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: C.panel,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        padding: "8px 12px",
        fontSize: 11,
        fontFamily: FONT,
      }}
    >
      <div style={{ color: C.muted, fontSize: 10, marginBottom: 4 }}>
        {label}
      </div>
      {payload.map((entry) => {
        const term = TERM[entry.dataKey];
        const displayName = term ? term.label : entry.name;
        return (
          <div
            key={entry.dataKey || entry.name}
            style={{ color: entry.color, marginBottom: 2 }}
          >
            {displayName}: {fmtTooltipVal(entry.dataKey, entry.value)}
          </div>
        );
      })}
    </div>
  );
}

/* ── Zoom Overlay (Domain-only: Drag + Wheel) ── */
/* TradingView 방식: Y축 domain만 변경 → SVG 찌그러짐 없음 */
const AXIS_W = 72; // Y축 틱 숫자 + 라벨 영역 너비
function ZoomOverlay({ zoom, onZoomChange, side = "left", fullWidth = false }) {
  const dragRef = useRef(null);
  const rafRef = useRef(null);
  const overlayRef = useRef(null);
  const [hovered, setHovered] = useState(false);

  // Refs for stable access inside non-passive wheel listener
  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;
  const cbRef = useRef(onZoomChange);
  cbRef.current = onZoomChange;

  const clampZoom = (z) => Math.max(0.2, Math.min(10, z));

  // Non-passive wheel listener — prevents page scroll on Y-axis area
  useEffect(() => {
    const el = overlayRef.current;
    if (!el) return;
    const handleWheel = (e) => {
      e.preventDefault();
      e.stopPropagation();
      const factor = e.deltaY > 0 ? 1 / 1.08 : 1.08;
      cbRef.current(clampZoom(zoomRef.current * factor));
    };
    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, []);

  return (
    <div
      ref={overlayRef}
      style={{
        position: "absolute",
        top: 0,
        [side]: 0,
        width: fullWidth ? "100%" : AXIS_W,
        height: "100%",
        cursor: "ns-resize",
        zIndex: 10,
        background: hovered ? "rgba(255,255,255,0.06)" : "transparent",
        transition: "background 0.15s",
      }}
      title="드래그/휠: Y축 줌 | 더블클릭: 리셋"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onPointerDown={(e) => {
        e.currentTarget.setPointerCapture(e.pointerId);
        dragRef.current = {
          startY: e.clientY,
          lastY: e.clientY,
          startZoom: zoom,
        };
      }}
      onPointerMove={(e) => {
        if (!dragRef.current) return;
        dragRef.current.lastY = e.clientY;
        if (rafRef.current) return;
        rafRef.current = requestAnimationFrame(() => {
          if (!dragRef.current) { rafRef.current = null; return; }
          const delta = dragRef.current.startY - dragRef.current.lastY;
          const newZoom = clampZoom(
            dragRef.current.startZoom * Math.exp(delta * 0.004),
          );
          onZoomChange(newZoom);
          rafRef.current = null;
        });
      }}
      onPointerUp={() => {
        if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
        dragRef.current = null;
      }}
      onDoubleClick={() => onZoomChange(1)}
    />
  );
}

/* ── Main Component ── */

export default function MarketPulse() {
  const [period, setPeriod] = useState("3M");

  // Brush indices
  const [creditBrush, setCreditBrush] = useState(null);
  const [flowsBrush, setFlowsBrush] = useState(null);

  // Zoom states (default 1.0, range 0.2~10)
  const [creditLeftZoom, setCreditLeftZoom] = useState(1);
  const [creditRightZoom, setCreditRightZoom] = useState(1);
  const [forcedLiqZoom, setForcedLiqZoom] = useState(1);
  const [flowsZoom, setFlowsZoom] = useState(1);
  const [shortsZoom, setShortsZoom] = useState(1);
  const [globalZooms, setGlobalZooms] = useState({ vix: 1, sp500: 1, wti: 1, usd_krw: 1 });


  // Investor flows view mode & filter
  const [flowsMode, setFlowsMode] = useState("cumulative");
  const [flowsFilter, setFlowsFilter] = useState(
    () => new Set(["individual", "foreign", "institution"]),
  );

  const days = PERIODS.find((p) => p.id === period)?.days ?? 9999;
  const market = useMemo(() => MARKET_DATA.slice(-days), [days]);
  const credit = useMemo(() => CREDIT_DATA.slice(-days), [days]);
  const flows = useMemo(() => INVESTOR_FLOWS.slice(-days), [days]);
  const global = useMemo(() => GLOBAL_DATA.slice(-days), [days]);
  const shorts = useMemo(() => SHORT_SELLING.slice(-days), [days]);

  // Reset brush and zoom when period changes
  const handlePeriod = useCallback((id) => {
    setPeriod(id);
    setCreditBrush(null);
    setFlowsBrush(null);
    setCreditLeftZoom(1);
    setCreditRightZoom(1);
    setForcedLiqZoom(1);
    setFlowsZoom(1);
    setShortsZoom(1);
    setGlobalZooms({ vix: 1, sp500: 1, wti: 1, usd_krw: 1 });
  }, []);

  // Investor flows filter toggle
  const toggleFilter = useCallback((key) => {
    setFlowsFilter((prev) => {
      if (key === "all") {
        return prev.size === 3
          ? new Set()
          : new Set(["individual", "foreign", "institution"]);
      }
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  // Visible slices based on brush
  const creditVisible = useMemo(() => {
    if (!creditBrush) return credit;
    return credit.slice(creditBrush.startIndex, creditBrush.endIndex + 1);
  }, [credit, creditBrush]);

  const flowsVisible = useMemo(() => {
    if (!flowsBrush) return flows;
    return flows.slice(flowsBrush.startIndex, flowsBrush.endIndex + 1);
  }, [flows, flowsBrush]);

  // Compute axes with zoom + niceScale
  const creditAxis = useMemo(
    () => computeAxis(creditVisible, ["credit_balance_billion"], creditLeftZoom),
    [creditVisible, creditLeftZoom],
  );
  const depositAxis = useMemo(
    () => computeAxis(creditVisible, ["deposit_billion"], creditRightZoom),
    [creditVisible, creditRightZoom],
  );
  const forcedLiqAxis = useMemo(
    () => computeAxis(creditVisible, ["forced_liq_billion"], forcedLiqZoom),
    [creditVisible, forcedLiqZoom],
  );
  // Cumulative flows data
  const cumFlows = useMemo(() => {
    let ci = 0, cf = 0, cn = 0;
    return flowsVisible.map((row) => {
      ci += row.individual_billion || 0;
      cf += row.foreign_billion || 0;
      cn += row.institution_billion || 0;
      return { ...row, cum_individual: ci, cum_foreign: cf, cum_institution: cn };
    });
  }, [flowsVisible]);

  // Active flow keys based on mode + filter
  const activeFlowKeys = useMemo(() => {
    const keys = [];
    const prefix = flowsMode === "cumulative" ? "cum_" : "";
    const suffix = flowsMode === "cumulative" ? "" : "_billion";
    if (flowsFilter.has("individual")) keys.push(`${prefix}individual${suffix}`);
    if (flowsFilter.has("foreign")) keys.push(`${prefix}foreign${suffix}`);
    if (flowsFilter.has("institution")) keys.push(`${prefix}institution${suffix}`);
    return keys;
  }, [flowsMode, flowsFilter]);

  const flowsAxis = useMemo(() => {
    const data = flowsMode === "cumulative" ? cumFlows : flowsVisible;
    if (activeFlowKeys.length === 0) return niceScale(0, 1, 5);
    return computeAxis(data, activeFlowKeys, flowsZoom);
  }, [flowsMode, cumFlows, flowsVisible, activeFlowKeys, flowsZoom]);

  const shortsAxis = useMemo(
    () => computeAxis(shorts, ["market_total_billion"], shortsZoom),
    [shorts, shortsZoom],
  );
  const globalAxes = useMemo(
    () => Object.fromEntries(
      ["vix", "sp500", "wti", "usd_krw"].map((k) => [
        k,
        computeAxis(global, [k], globalZooms[k], 3),
      ]),
    ),
    [global, globalZooms],
  );

  const latest = market[market.length - 1] || {};

  // Visible-range cumulative summary (for summary cards)
  const flowsSummary = useMemo(() => ({
    individual: flowsVisible.reduce((a, r) => a + (r.individual_billion || 0), 0),
    foreign: flowsVisible.reduce((a, r) => a + (r.foreign_billion || 0), 0),
    institution: flowsVisible.reduce((a, r) => a + (r.institution_billion || 0), 0),
  }), [flowsVisible]);

  // Short selling gov ban start date
  const banDate = useMemo(
    () => shorts.find((s) => s.gov_ban)?.date,
    [shorts],
  );

  const handleCreditBrush = useCallback((brush) => {
    setCreditBrush(brush);
  }, []);

  const handleFlowsBrush = useCallback((brush) => {
    setFlowsBrush(brush);
  }, []);

  return (
    <div style={{ fontFamily: FONT }}>
      {/* ── Period Selector ── */}
      <div style={{ display: "flex", gap: 2, marginBottom: 16 }}>
        {PERIODS.map((p) => (
          <button
            key={p.id}
            onClick={() => handlePeriod(p.id)}
            style={{
              background: period === p.id ? C.kospi : "transparent",
              color: period === p.id ? "#fff" : C.muted,
              border: `1px solid ${period === p.id ? C.kospi : C.border}`,
              borderRadius: 6,
              padding: "4px 12px",
              fontSize: 10,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: FONT,
              transition: "all 0.15s",
            }}
          >
            {p.id}
          </button>
        ))}
      </div>

      {/* ── Section 1a: 신용잔고 & 고객예탁금 ── */}
      <PanelBox>
        <SectionTitle>신용잔고 & 고객예탁금 (Credit & Deposit)</SectionTitle>
        <div style={{ position: "relative" }}>
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart
              data={credit}
              margin={{ top: 5, right: 20, bottom: 5, left: 10 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis
                dataKey="date"
                tickFormatter={fmtDate}
                {...axisProps}
              />
              <YAxis
                yAxisId="left"
                stroke={C.credit}
                fontSize={10}
                tickFormatter={fmtTril}
                domain={creditAxis.domain}
                ticks={creditAxis.ticks}
                allowDataOverflow={true}
                label={yAxisLabel("(조원)", "left")}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                stroke={C.deposit}
                fontSize={10}
                tickFormatter={fmtTril}
                domain={depositAxis.domain}
                ticks={depositAxis.ticks}
                allowDataOverflow={true}
                label={yAxisLabel("(조원)", "right")}
              />
              <Tooltip content={<CustomTooltipContent />} />
              <Legend content={<CustomLegend />} />
              <Line
                yAxisId="left"
                dataKey="credit_balance_billion"
                stroke={C.credit}
                strokeWidth={2}
                dot={false}
              />
              <Line
                yAxisId="right"
                dataKey="deposit_billion"
                stroke={C.deposit}
                strokeWidth={2}
                dot={false}
                strokeDasharray={
                  credit[credit.length - 1]?.estimated ? "5 3" : undefined
                }
              />
              <Brush
                dataKey="date"
                height={20}
                stroke={C.dim}
                fill={C.panel}
                tickFormatter={fmtDate}
                onChange={handleCreditBrush}
              />
            </ComposedChart>
          </ResponsiveContainer>
          <ZoomOverlay
            zoom={creditLeftZoom}
            onZoomChange={setCreditLeftZoom}
            side="left"
          />
          <ZoomOverlay
            zoom={creditRightZoom}
            onZoomChange={setCreditRightZoom}
            side="right"
          />
        </div>
        {credit[credit.length - 1]?.estimated && (
          <div
            style={{
              color: C.yellow,
              fontSize: 10,
              textAlign: "right",
              marginTop: 4,
              fontStyle: "italic",
            }}
          >
            * 점선 = 추정치 (T+2 지연)
          </div>
        )}
      </PanelBox>

      {/* ── Section 1b: 반대매매 ── */}
      <PanelBox>
        <SectionTitle>반대매매 (Forced Liquidation)</SectionTitle>
        <div style={{ position: "relative" }}>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart
              data={creditVisible}
              margin={{ top: 5, right: 20, bottom: 5, left: 10 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis dataKey="date" tickFormatter={fmtDate} {...axisProps} />
              <YAxis
                {...axisProps}
                tickFormatter={fmtHundM}
                domain={forcedLiqAxis.domain}
                ticks={forcedLiqAxis.ticks}
                allowDataOverflow={true}
                label={yAxisLabel("(억원)", "left")}
              />
              <Tooltip content={<CustomTooltipContent />} />
              <Legend content={<CustomLegend />} />
              <Bar
                dataKey="forced_liq_billion"
                fill={C.forcedLiq}
                opacity={0.8}
                barSize={6}
              />
            </BarChart>
          </ResponsiveContainer>
          <ZoomOverlay
            zoom={forcedLiqZoom}
            onZoomChange={setForcedLiqZoom}
            side="left"
          />
        </div>
      </PanelBox>

      {/* ── Section 2: 투자자 수급 ── */}
      <PanelBox>
        <SectionTitle>투자자 수급 (Investor Flows)</SectionTitle>

        {/* Summary Cards */}
        <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
          {[
            { key: "individual", label: "개인", color: C.individual },
            { key: "foreign", label: "외국인", color: C.foreign },
            { key: "institution", label: "기관", color: C.institution },
          ].map(({ key, label, color }) => {
            const val = flowsSummary[key];
            const tril = (val / 1000).toFixed(1);
            return (
              <div
                key={key}
                style={{
                  background: C.panel,
                  border: `1px solid ${C.border}`,
                  borderRadius: 8,
                  padding: "8px 14px",
                  flex: 1,
                  minWidth: 100,
                }}
              >
                <div style={{ color: C.muted, fontSize: 10, marginBottom: 2 }}>
                  {label}
                </div>
                <div
                  style={{
                    color: val >= 0 ? C.green : C.red,
                    fontSize: 15,
                    fontWeight: 700,
                    fontFamily: FONT,
                  }}
                >
                  {val >= 0 ? "+" : ""}{tril}
                  <span style={{ fontSize: 10, fontWeight: 400, color }}> 조원</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Mode Toggle + Filter Toggle */}
        <div style={{ display: "flex", gap: 12, marginBottom: 10, flexWrap: "wrap", alignItems: "center" }}>
          {/* View Mode */}
          <div style={{ display: "flex", gap: 2 }}>
            {[
              { id: "cumulative", label: "누적" },
              { id: "daily", label: "일자별" },
            ].map((m) => (
              <button
                key={m.id}
                onClick={() => setFlowsMode(m.id)}
                style={{
                  background: flowsMode === m.id ? C.kospi : "transparent",
                  color: flowsMode === m.id ? "#fff" : C.muted,
                  border: `1px solid ${flowsMode === m.id ? C.kospi : C.border}`,
                  borderRadius: 6,
                  padding: "3px 10px",
                  fontSize: 10,
                  fontWeight: 600,
                  cursor: "pointer",
                  fontFamily: FONT,
                  transition: "all 0.15s",
                }}
              >
                {m.label}
              </button>
            ))}
          </div>

          <div style={{ width: 1, height: 16, background: C.border }} />

          {/* Filter Toggle */}
          <div style={{ display: "flex", gap: 2 }}>
            {[
              { id: "all", label: "전체", color: C.muted },
              { id: "individual", label: "개인", color: C.individual },
              { id: "foreign", label: "외국인", color: C.foreign },
              { id: "institution", label: "기관", color: C.institution },
            ].map((f) => {
              const active = f.id === "all" ? flowsFilter.size === 3 : flowsFilter.has(f.id);
              return (
                <button
                  key={f.id}
                  onClick={() => toggleFilter(f.id)}
                  style={{
                    background: active ? f.color + "22" : "transparent",
                    color: active ? f.color : C.dim,
                    border: `1px solid ${active ? f.color + "66" : C.border}`,
                    borderRadius: 6,
                    padding: "3px 10px",
                    fontSize: 10,
                    fontWeight: 600,
                    cursor: "pointer",
                    fontFamily: FONT,
                    transition: "all 0.15s",
                  }}
                >
                  {f.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Chart */}
        <div style={{ position: "relative" }}>
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart
              data={flowsMode === "cumulative" ? cumFlows : flowsVisible}
              margin={{ top: 5, right: 20, bottom: 5, left: 10 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis dataKey="date" tickFormatter={fmtDate} {...axisProps} />
              <YAxis
                {...axisProps}
                tickFormatter={fmtTril}
                domain={flowsAxis.domain}
                ticks={flowsAxis.ticks}
                allowDataOverflow={true}
                label={yAxisLabel("(조원)", "left")}
              />
              <Tooltip content={<CustomTooltipContent />} />
              <Legend content={<CustomLegend />} />
              <ReferenceLine y={0} stroke={C.dim} />

              {flowsMode === "cumulative" ? (
                <>
                  {flowsFilter.has("individual") && (
                    <Area
                      type="monotone"
                      dataKey="cum_individual"
                      stroke={C.individual}
                      fill={C.individual}
                      fillOpacity={0.15}
                      strokeWidth={2}
                      dot={false}
                    />
                  )}
                  {flowsFilter.has("foreign") && (
                    <Area
                      type="monotone"
                      dataKey="cum_foreign"
                      stroke={C.foreign}
                      fill={C.foreign}
                      fillOpacity={0.15}
                      strokeWidth={2}
                      dot={false}
                    />
                  )}
                  {flowsFilter.has("institution") && (
                    <Area
                      type="monotone"
                      dataKey="cum_institution"
                      stroke={C.institution}
                      fill={C.institution}
                      fillOpacity={0.15}
                      strokeWidth={2}
                      dot={false}
                    />
                  )}
                </>
              ) : (
                <>
                  {flowsFilter.has("individual") && (
                    <Area
                      type="monotone"
                      dataKey="individual_billion"
                      stroke={C.individual}
                      fill={C.individual}
                      fillOpacity={0.1}
                      strokeWidth={1.5}
                      dot={false}
                    />
                  )}
                  {flowsFilter.has("foreign") && (
                    <Area
                      type="monotone"
                      dataKey="foreign_billion"
                      stroke={C.foreign}
                      fill={C.foreign}
                      fillOpacity={0.1}
                      strokeWidth={1.5}
                      dot={false}
                    />
                  )}
                  {flowsFilter.has("institution") && (
                    <Area
                      type="monotone"
                      dataKey="institution_billion"
                      stroke={C.institution}
                      fill={C.institution}
                      fillOpacity={0.1}
                      strokeWidth={1.5}
                      dot={false}
                    />
                  )}
                </>
              )}

              <Brush
                dataKey="date"
                height={20}
                stroke={C.dim}
                fill={C.panel}
                tickFormatter={fmtDate}
                onChange={handleFlowsBrush}
              />
            </ComposedChart>
          </ResponsiveContainer>
          <ZoomOverlay
            zoom={flowsZoom}
            onZoomChange={setFlowsZoom}
            side="left"
          />
        </div>
      </PanelBox>

      {/* ── Section 3: 공매도 ── */}
      <PanelBox>
        <SectionTitle>공매도 (Short Selling)</SectionTitle>
        <div style={{ position: "relative" }}>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart
              data={shorts}
              margin={{ top: 5, right: 20, bottom: 5, left: 10 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis dataKey="date" tickFormatter={fmtDate} {...axisProps} />
              <YAxis
                {...axisProps}
                tickFormatter={fmtAxis}
                domain={shortsAxis.domain}
                ticks={shortsAxis.ticks}
                allowDataOverflow={true}
                label={yAxisLabel("(십억원)", "left")}
              />
              <Tooltip content={<CustomTooltipContent />} />
              <Legend content={<CustomLegend />} />
              <Line
                dataKey="market_total_billion"
                stroke={C.red}
                strokeWidth={2}
                dot={false}
              />
              {banDate && (
                <ReferenceLine
                  x={banDate}
                  stroke={C.yellow}
                  strokeDasharray="5 3"
                  label={{
                    value: "공매도 금지",
                    fill: C.yellow,
                    fontSize: 10,
                    fontFamily: FONT,
                  }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
          <ZoomOverlay
            zoom={shortsZoom}
            onZoomChange={setShortsZoom}
            side="left"
          />
        </div>
      </PanelBox>

      {/* ── Section 4: 글로벌 컨텍스트 ── */}
      <PanelBox>
        <SectionTitle>글로벌 컨텍스트 (Global Context)</SectionTitle>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 12,
          }}
        >
          {[
            { key: "vix", label: "VIX", color: C.red },
            { key: "sp500", label: "S&P 500", color: C.green },
            { key: "wti", label: "WTI (USD)", color: "#a78bfa" },
            { key: "usd_krw", label: "USD/KRW", color: C.yellow },
          ].map(({ key, label, color }) => (
            <div key={key}>
              <div style={{ color: C.muted, fontSize: 10, marginBottom: 4 }}>
                {label}:{" "}
                <span style={{ color: C.text, fontWeight: 600 }}>
                  {global[global.length - 1]?.[key]}
                </span>
              </div>
              <div style={{ position: "relative" }}>
                <ResponsiveContainer width="100%" height={90}>
                  <LineChart
                    data={global}
                    margin={{ top: 2, right: 4, bottom: 2, left: 4 }}
                  >
                    <XAxis dataKey="date" hide />
                    <YAxis
                      domain={globalAxes[key]?.domain ?? ["auto", "auto"]}
                      ticks={globalAxes[key]?.ticks}
                      allowDataOverflow={true}
                      hide
                    />
                    <Line
                      dataKey={key}
                      stroke={color}
                      strokeWidth={1.5}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
                <ZoomOverlay
                  zoom={globalZooms[key]}
                  onZoomChange={(z) => setGlobalZooms((prev) => ({ ...prev, [key]: z }))}
                  side="left"
                  fullWidth
                />
              </div>
            </div>
          ))}
        </div>
      </PanelBox>

      {/* ── Section 5: DRAM (Phase 2 placeholder) ── */}
      <PanelBox style={{ opacity: 0.5 }}>
        <SectionTitle>DRAM Price Trend</SectionTitle>
        <div
          style={{
            color: C.dim,
            fontSize: 11,
            padding: "20px 0",
            textAlign: "center",
          }}
        >
          Manual input required — Phase 2+
        </div>
      </PanelBox>

      {/* ── Section 6: 이벤트 로그 ── */}
      <PanelBox>
        <SectionTitle>이벤트 로그 (Event Log)</SectionTitle>
        <div style={{ maxHeight: 260, overflow: "auto" }}>
          {EVENTS.map((evt, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                gap: 10,
                padding: "6px 0",
                borderBottom:
                  i < EVENTS.length - 1
                    ? `1px solid ${C.border}`
                    : "none",
                fontSize: 11,
                alignItems: "center",
              }}
            >
              <span style={{ color: C.dim, minWidth: 52, flexShrink: 0 }}>
                {evt.date.slice(5)}
              </span>
              <span
                style={{
                  color:
                    evt.type === "government_action"
                      ? C.yellow
                      : evt.type === "global"
                        ? C.foreign
                        : evt.type === "flow"
                          ? C.individual
                          : evt.type === "credit"
                            ? C.credit
                            : C.kospi,
                  minWidth: 56,
                  flexShrink: 0,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  fontSize: 9,
                }}
              >
                {evt.type.replace(/_/g, " ")}
              </span>
              <span style={{ color: C.text }}>{evt.desc}</span>
            </div>
          ))}
        </div>
      </PanelBox>
    </div>
  );
}
