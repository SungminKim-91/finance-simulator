import { useState, useMemo } from "react";
import {
  ComposedChart, Line, Area, Bar, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, ReferenceArea, BarChart,
  LineChart, ScatterChart, Scatter,
} from "recharts";
import {
  INDEX_DATA, METHODS, XCORR_V2, CWS_PROFILE,
  BOOTSTRAP, CPCV, SUCCESS, META_V2,
} from "./data_v2";

/* ── Color Palette ── */
const C = {
  bg: "#020617", panel: "#0f172a", border: "#1e293b", borderHi: "#334155",
  text: "#e2e8f0", muted: "#94a3b8", dim: "#64748b",
  btc: "#f59e0b", btcSub: "#fbbf24",
  index: "#22d3ee", indexSub: "#06b6d4",
  nl: "#3b82f6", gm2: "#8b5cf6", hy: "#f97316", cme: "#10b981",
  green: "#4ade80", red: "#f87171", purple: "#a78bfa",
  yellow: "#facc15", cyan: "#22d3ee", pink: "#f472b6",
  mda: "#3b82f6", sbd: "#8b5cf6", cos: "#10b981", tau: "#f97316",
};

const C_struct = "#60a5fa";  // blue-400 — structural (slow)
const C_tact = "#fb923c";    // orange-400 — tactical (fast)

const VAR_COLORS = { NL_level: C.nl, GM2_resid: C.gm2, HY_level: C.hy, CME_basis: C.cme };
const VAR_SHORT = { NL_level: "NL", GM2_resid: "GM2", HY_level: "HY", CME_basis: "CME" };

/* ── Tooltip ── */
const IndexTip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div style={{ background: C.panel, border: `1px solid ${C.borderHi}`, borderRadius: 8, padding: "10px 14px", color: C.text, fontSize: 12, lineHeight: 1.8, maxWidth: 280 }}>
      <div style={{ fontWeight: 700, color: C.muted, marginBottom: 2 }}>{d.date}</div>
      {d.log_btc != null && <div>BTC: <span style={{ color: C.btc, fontWeight: 700 }}>${Math.round(10 ** d.log_btc).toLocaleString()}</span></div>}
      {d.shiftIndex != null && <div>Structural: <span style={{ color: C_struct, fontWeight: 700 }}>{d.shiftIndex > 0 ? "+" : ""}{d.shiftIndex.toFixed(3)}</span>
        <span style={{ color: C.dim, fontSize: 10 }}> (NL+GM2, shifted)</span></div>}
      {d.smoothTact != null && <div>Tactical: <span style={{ color: C_tact, fontWeight: 700 }}>{d.smoothTact > 0 ? "+" : ""}{d.smoothTact.toFixed(3)}</span>
        <span style={{ color: C.dim, fontSize: 10 }}> (-HY, EMA)</span></div>}
      {d.combined != null && <div>Combined: <span style={{ color: C.cyan, fontWeight: 700 }}>{d.combined > 0 ? "+" : ""}{d.combined.toFixed(3)}</span>
        <span style={{ color: C.dim, fontSize: 10 }}> (70/30)</span></div>}
      {d.match != null && <div>Direction: <span style={{ color: d.match ? C.green : C.red, fontWeight: 700 }}>{d.match ? "MATCH" : "MISMATCH"}</span></div>}
    </div>
  );
};

/* ── Pearson Correlation ── */
function pearson(arr, kx, ky) {
  const p = arr.filter(d => d[kx] != null && d[ky] != null);
  const n = p.length;
  if (n < 5) return 0;
  const mx = p.reduce((s, d) => s + d[kx], 0) / n;
  const my = p.reduce((s, d) => s + d[ky], 0) / n;
  let nm = 0, d1 = 0, d2 = 0;
  p.forEach(d => { nm += (d[kx] - mx) * (d[ky] - my); d1 += (d[kx] - mx) ** 2; d2 += (d[ky] - my) ** 2; });
  return d1 && d2 ? nm / Math.sqrt(d1 * d2) : 0;
}

/* ── Pass/Fail Badge ── */
const Badge = ({ pass, label, value }) => (
  <div style={{
    background: pass ? "rgba(74,222,128,0.1)" : "rgba(248,113,113,0.1)",
    border: `1px solid ${pass ? C.green : C.red}`,
    borderRadius: 6, padding: "4px 10px", fontSize: 11, display: "inline-flex", alignItems: "center", gap: 6,
  }}>
    <span style={{ color: pass ? C.green : C.red, fontWeight: 700 }}>{pass ? "PASS" : "FAIL"}</span>
    <span style={{ color: C.muted }}>{label}</span>
    {value != null && <span style={{ color: C.text, fontWeight: 600 }}>{value}</span>}
  </div>
);

/* ══════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ══════════════════════════════════════════════════════════════ */
export default function AppV2() {
  const [shift, setShift] = useState(META_V2.optimal_lag);
  const [tab, setTab] = useState("index"); // index | methods | cws | robust
  const [showTactical, setShowTactical] = useState(false);
  const [showCombined, setShowCombined] = useState(false);
  const [smoothing, setSmoothing] = useState(6); // EMA window (months)

  /* ── Shift structural band by lag, tactical stays at realtime ── */
  const chartData = useMemo(() => {
    // Pass 1: compute structural (shifted) and tactical (realtime)
    const records = INDEX_DATA.map((d, i) => {
      const si = i - shift;
      const hasStruct = si >= 0 && si < INDEX_DATA.length;
      const structVal = hasStruct ? INDEX_DATA[si].structural : null;
      const tactVal = d.tactical;

      let match = null;
      if (structVal != null && d.log_btc != null && i > 0) {
        const prevBtc = INDEX_DATA[i - 1]?.log_btc;
        const prevStruct = (si - 1 >= 0) ? INDEX_DATA[si - 1]?.structural : null;
        if (prevBtc != null && prevStruct != null) {
          const dBtc = d.log_btc - prevBtc;
          const dStruct = structVal - prevStruct;
          match = (dBtc >= 0 && dStruct >= 0) || (dBtc < 0 && dStruct < 0);
        }
      }

      return { ...d, shiftIndex: structVal, tactical: tactVal, match };
    });

    // Pass 2: EMA smoothing on tactical (suppress HY spikes)
    const alpha = 2 / (smoothing + 1);
    let prev = null;
    for (let i = 0; i < records.length; i++) {
      const t = records[i].tactical;
      if (t == null) { records[i].smoothTact = null; continue; }
      if (prev == null) { records[i].smoothTact = t; prev = t; continue; }
      const sm = alpha * t + (1 - alpha) * prev;
      records[i].smoothTact = sm;
      prev = sm;
    }

    // Pass 3: combined = 0.7 * structural + 0.3 * smoothed tactical
    for (let i = 0; i < records.length; i++) {
      const s = records[i].shiftIndex;
      const st = records[i].smoothTact;
      records[i].combined = (s != null && st != null)
        ? 0.7 * s + 0.3 * st
        : null;
    }

    return records;
  }, [shift, smoothing]);

  /* Live correlation */
  const corr = useMemo(() => pearson(chartData, "shiftIndex", "log_btc"), [chartData]);

  /* MDA from chartData */
  const mda = useMemo(() => {
    const matches = chartData.filter(d => d.match != null);
    if (!matches.length) return 0;
    return matches.filter(d => d.match).length / matches.length;
  }, [chartData]);

  /* Direction match regions */
  const matchRegions = useMemo(() => {
    const regions = [];
    let start = null, curMatch = null;
    chartData.forEach((d, i) => {
      if (d.match == null) return;
      if (d.match !== curMatch) {
        if (start !== null) regions.push({ start, end: i, match: curMatch });
        start = i;
        curMatch = d.match;
      }
    });
    if (start !== null) regions.push({ start, end: chartData.length - 1, match: curMatch });
    return regions;
  }, [chartData]);

  const labelDate = (v) => chartData[parseInt(v)]?.date || "";

  /* Success summary */
  const successCount = Object.values(SUCCESS).filter(v => v?.pass).length;
  const totalCriteria = Object.keys(SUCCESS).length;

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, fontFamily: "'JetBrains Mono', 'SF Mono', monospace", padding: "20px 16px" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>

        {/* ── Header ── */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: "#f8fafc", margin: 0 }}>
              BTC Liquidity Simulator <span style={{ fontSize: 12, color: C.index, fontWeight: 600 }}>v2.0.0</span>
            </h1>
            <p style={{ fontSize: 11, color: C.dim, margin: "4px 0 0" }}>
              3-Stage Pipeline: BTC-blind PCA Index &rarr; Direction Validation &rarr; Robustness
            </p>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <div style={{
              background: C.panel, border: `1px solid ${C.border}`,
              borderRadius: 8, padding: "6px 14px", textAlign: "center",
            }}>
              <div style={{ fontSize: 10, color: C.muted }}>Method</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: C.index }}>{META_V2.method}</div>
            </div>
            <div style={{
              background: C.panel, border: `1px solid ${C.border}`,
              borderRadius: 8, padding: "6px 14px", textAlign: "center",
            }}>
              <div style={{ fontSize: 10, color: C.muted }}>Best CWS</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: C.purple }}>{META_V2.best_cws.toFixed(3)}</div>
            </div>
            <div style={{
              background: C.panel, border: `1px solid ${C.border}`,
              borderRadius: 8, padding: "6px 14px", textAlign: "center",
            }}>
              <div style={{ fontSize: 10, color: C.muted }}>Criteria</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: successCount === totalCriteria ? C.green : C.yellow }}>
                {successCount}/{totalCriteria}
              </div>
            </div>
          </div>
        </div>

        {/* ── Success Criteria Badges ── */}
        <div style={{ display: "flex", gap: 6, marginBottom: 14, flexWrap: "wrap" }}>
          {Object.entries(SUCCESS).map(([k, v]) => (
            <Badge key={k} pass={v.pass} label={k.replace(/_/g, " ")}
              value={typeof v.actual === "boolean" ? (v.actual ? "Yes" : "No") : typeof v.actual === "number" ? v.actual.toFixed(3) : String(v.actual)} />
          ))}
        </div>

        {/* ── Tab Buttons ── */}
        <div style={{ display: "flex", gap: 4, marginBottom: 14 }}>
          {[["index", "Index vs BTC"], ["methods", "Loadings"], ["cws", "CWS Profile"], ["robust", "Robustness"]].map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)} style={{
              background: tab === k ? "#7c3aed" : C.border,
              color: tab === k ? "#fff" : C.muted,
              border: "none", borderRadius: 6, padding: "6px 14px", fontSize: 11,
              fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
            }}>{l}</button>
          ))}
        </div>

        {/* ══════════ TAB: Index vs BTC ══════════ */}
        {tab === "index" && (
          <>
            {/* Lag Slider */}
            <div style={{ display: "flex", gap: 12, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <button onClick={() => setShift(s => Math.max(0, s - 1))} style={{ background: C.borderHi, border: "none", color: C.text, borderRadius: 4, width: 26, height: 26, cursor: "pointer", fontSize: 15, fontFamily: "inherit" }}>-</button>
                <div style={{ background: C.border, borderRadius: 6, padding: "3px 10px", minWidth: 100, textAlign: "center" }}>
                  <span style={{ color: C.purple, fontWeight: 700, fontSize: 16 }}>{shift}</span>
                  <span style={{ color: C.dim, fontSize: 10, marginLeft: 4 }}>months</span>
                </div>
                <button onClick={() => setShift(s => Math.min(15, s + 1))} style={{ background: C.borderHi, border: "none", color: C.text, borderRadius: 4, width: 26, height: 26, cursor: "pointer", fontSize: 15, fontFamily: "inherit" }}>+</button>
              </div>
              <input type="range" min={0} max={15} value={shift} onChange={e => setShift(+e.target.value)}
                style={{ flex: 1, minWidth: 80, accentColor: C.purple, height: 3 }} />
              {/* Tactical toggle */}
              <button onClick={() => { setShowTactical(v => !v); if (showTactical) setShowCombined(false); }} style={{
                background: showTactical ? "rgba(251,146,60,0.15)" : C.border,
                border: `1px solid ${showTactical ? C_tact : C.borderHi}`,
                borderRadius: 6, padding: "5px 12px", fontSize: 11,
                fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
                color: showTactical ? C_tact : C.dim,
                transition: "all 0.15s",
              }}>
                {showTactical ? "Tactical ON" : "Tactical OFF"}
                <span style={{ fontSize: 9, marginLeft: 4, opacity: 0.7 }}>(-HY)</span>
              </button>
              {/* Combine toggle — visible when tactical is on */}
              {showTactical && (
                <button onClick={() => setShowCombined(v => !v)} style={{
                  background: showCombined ? "rgba(34,211,238,0.15)" : C.border,
                  border: `1px solid ${showCombined ? C.cyan : C.borderHi}`,
                  borderRadius: 6, padding: "5px 12px", fontSize: 11,
                  fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
                  color: showCombined ? C.cyan : C.dim,
                  transition: "all 0.15s",
                }}>
                  {showCombined ? "Combined ON" : "Combine"}
                  <span style={{ fontSize: 9, marginLeft: 4, opacity: 0.7 }}>70/30</span>
                </button>
              )}
              {/* Smoothing slider — visible when combined is on */}
              {showCombined && (
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ fontSize: 9, color: C.dim }}>Smooth</span>
                  <input type="range" min={2} max={12} value={smoothing} onChange={e => setSmoothing(+e.target.value)}
                    style={{ width: 60, accentColor: C.cyan, height: 2 }} />
                  <span style={{ fontSize: 10, color: C.cyan, fontWeight: 700, minWidth: 20 }}>{smoothing}m</span>
                </div>
              )}
            </div>

            {/* Stats Row */}
            <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
              <div style={{ background: C.border, borderRadius: 8, padding: "5px 12px", fontSize: 12 }}>
                <span style={{ color: C_struct }}>Pearson r</span>
                <span style={{ color: C.dim }}> = </span>
                <span style={{ color: corr > 0 ? C.green : C.red, fontWeight: 700, fontSize: 14 }}>
                  {corr > 0 ? "+" : ""}{corr.toFixed(3)}
                </span>
                <span style={{ color: C.dim, fontSize: 10 }}> @{shift}m</span>
              </div>
              <div style={{ background: C.border, borderRadius: 8, padding: "5px 12px", fontSize: 12 }}>
                <span style={{ color: C.mda }}>MDA</span>
                <span style={{ color: C.dim }}> = </span>
                <span style={{ color: mda >= 0.6 ? C.green : mda >= 0.5 ? C.yellow : C.red, fontWeight: 700 }}>
                  {(mda * 100).toFixed(1)}%
                </span>
              </div>
              <div style={{ background: C.border, borderRadius: 8, padding: "5px 12px", fontSize: 12 }}>
                <span style={{ color: C.dim }}>Loadings: </span>
                {Object.entries(META_V2.loadings).map(([k, v]) => (
                  <span key={k} style={{ color: VAR_COLORS[k], marginRight: 6 }}>
                    {VAR_SHORT[k]}={v > 0 ? "+" : ""}{v.toFixed(2)}
                  </span>
                ))}
              </div>
            </div>

            {/* Main Chart */}
            <div style={{ background: C.panel, borderRadius: 12, padding: "14px 8px 8px", border: `1px solid ${C.border}` }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#f8fafc", marginBottom: 2, paddingLeft: 4 }}>
                Dual-Band Liquidity Index vs BTC Price
              </div>
              <div style={{ fontSize: 10, color: C.dim, marginBottom: 6, paddingLeft: 4 }}>
                <span style={{ color: C.btc }}>&#9679; BTC ($, log scale)</span>
                <span style={{ marginLeft: 10, color: C_struct, opacity: showCombined ? 0.4 : 1 }}>&#9679; Structural (NL+GM2, shifted {shift}m)</span>
                {showTactical && <span style={{ marginLeft: 10, color: C_tact, opacity: showCombined ? 0.4 : 1 }}>&#9679; Tactical (-HY, EMA {smoothing}m)</span>}
                {showCombined && <span style={{ marginLeft: 10, color: C.cyan, fontWeight: 700 }}>&#9679; Combined (70/30)</span>}
                <span style={{ marginLeft: 10, color: C.green }}>&#9632; Match</span>
                <span style={{ marginLeft: 6, color: C.red }}>&#9632; Mismatch</span>
              </div>
              <ResponsiveContainer width="100%" height={440}>
                <ComposedChart data={chartData} margin={{ top: 8, right: 6, left: 0, bottom: 8 }}>
                  <defs>
                    <linearGradient id="idxGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={C_struct} stopOpacity={0.12} />
                      <stop offset="50%" stopColor={C_struct} stopOpacity={0} />
                      <stop offset="100%" stopColor={C_struct} stopOpacity={0.06} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey={(_, i) => i} tickFormatter={labelDate} tick={{ fill: C.dim, fontSize: 9 }} interval={23} axisLine={{ stroke: C.borderHi }} tickLine={false} />
                  <YAxis yAxisId="l" tick={{ fill: C.btc, fontSize: 9 }} axisLine={false} tickLine={false}
                    tickFormatter={v => `$${Math.round(10 ** v).toLocaleString()}`}
                    domain={[2.4, 5.2]} width={58} />
                  <YAxis yAxisId="r" orientation="right" tick={{ fill: C_struct, fontSize: 9 }} axisLine={false} tickLine={false}
                    domain={[-5, 5]} width={36} />
                  {/* Direction match/mismatch shading */}
                  {matchRegions.map((r, i) => (
                    <ReferenceArea key={i} x1={r.start} x2={r.end} yAxisId="r"
                      fill={r.match ? C.green : C.red} fillOpacity={0.06} strokeOpacity={0} />
                  ))}
                  <ReferenceLine yAxisId="r" y={0} stroke={C.borderHi} strokeDasharray="2 4" strokeOpacity={0.4} />
                  <Area yAxisId="r" dataKey={showCombined ? "combined" : "shiftIndex"} stroke="none" fill="url(#idxGrad)" />
                  <Line yAxisId="l" dataKey="log_btc" stroke={C.btc} strokeWidth={2.2} dot={false} />
                  <Line yAxisId="r" dataKey="shiftIndex" stroke={C_struct}
                    strokeWidth={showCombined ? 1.0 : 1.8} dot={false} connectNulls
                    strokeOpacity={showCombined ? 0.3 : 1} />
                  {showTactical && (
                    <Line yAxisId="r" dataKey="smoothTact" stroke={C_tact}
                      strokeWidth={showCombined ? 1.0 : 1.5} dot={false} connectNulls
                      strokeDasharray="6 3" strokeOpacity={showCombined ? 0.3 : 0.85} />
                  )}
                  {showCombined && (
                    <Line yAxisId="r" dataKey="combined" stroke={C.cyan} strokeWidth={2.2} dot={false} connectNulls />
                  )}
                  <Tooltip content={<IndexTip />} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* Cross-Correlation Heatmap */}
            <div style={{ background: C.panel, borderRadius: 12, padding: "14px 14px 12px", border: `1px solid ${C.border}`, marginTop: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#f8fafc", marginBottom: 4 }}>
                Cross-Correlation Profile
              </div>
              <div style={{ fontSize: 10, color: C.dim, marginBottom: 10 }}>
                Click a cell to set lag &middot; All r {META_V2.all_positive ? "> 0" : "NOT all > 0"}
              </div>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                {XCORR_V2.map(({ lag, pearson_r, mda }) => {
                  const bg = pearson_r > 0
                    ? `rgba(74,222,128,${Math.min(pearson_r * 1.4, 0.85)})`
                    : `rgba(248,113,113,${Math.min(Math.abs(pearson_r) * 1.4, 0.85)})`;
                  return (
                    <div key={lag} onClick={() => setShift(lag)} style={{
                      width: 60, height: 55, background: bg, borderRadius: 6,
                      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                      cursor: "pointer", border: shift === lag ? `2px solid ${C.purple}` : "2px solid transparent",
                      transition: "border 0.15s",
                    }}>
                      <div style={{ fontSize: 9, color: C.text }}>{lag}m</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: "#fff" }}>{pearson_r > 0 ? "+" : ""}{pearson_r.toFixed(3)}</div>
                      <div style={{ fontSize: 8, color: "rgba(255,255,255,0.7)" }}>MDA:{(mda * 100).toFixed(0)}%</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}

        {/* ══════════ TAB: Method Loadings ══════════ */}
        {tab === "methods" && (
          <>
            {/* Loadings Bar Chart */}
            <div style={{ background: C.panel, borderRadius: 12, padding: "14px 14px 8px", border: `1px solid ${C.border}` }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#f8fafc", marginBottom: 2 }}>
                PCA Loadings (PC1, {(META_V2.explained_variance * 100).toFixed(1)}% variance explained)
              </div>
              <div style={{ fontSize: 10, color: C.dim, marginBottom: 10 }}>
                Variable importance in BTC-blind liquidity index (no target optimization)
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={Object.entries(META_V2.loadings).map(([k, v]) => ({
                  name: VAR_SHORT[k] || k,
                  loading: v,
                  fill: VAR_COLORS[k] || C.muted,
                }))} margin={{ top: 8, right: 20, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey="name" tick={{ fill: C.muted, fontSize: 11 }} axisLine={{ stroke: C.borderHi }} tickLine={false} />
                  <YAxis tick={{ fill: C.muted, fontSize: 10 }} axisLine={false} tickLine={false} domain={[-1, 1]} width={40} />
                  <ReferenceLine y={0} stroke={C.borderHi} />
                  <Bar dataKey="loading" radius={[4, 4, 0, 0]}>
                    {Object.entries(META_V2.loadings).map(([k], i) => (
                      <Cell key={i} fill={VAR_COLORS[k] || C.muted} />
                    ))}
                  </Bar>
                  <Tooltip formatter={v => v.toFixed(4)} contentStyle={{ background: C.panel, border: `1px solid ${C.borderHi}`, borderRadius: 8, color: C.text, fontSize: 12 }} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Bootstrap CI */}
            <div style={{ background: C.panel, borderRadius: 12, padding: "14px 14px 8px", border: `1px solid ${C.border}`, marginTop: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#f8fafc", marginBottom: 2 }}>
                Bootstrap Loading Stability (95% CI, n={BOOTSTRAP.n_valid})
              </div>
              <div style={{ fontSize: 10, color: C.dim, marginBottom: 10 }}>
                NL max rate: <span style={{ color: BOOTSTRAP.nl_max_rate > 0.95 ? C.green : C.yellow, fontWeight: 700 }}>{(BOOTSTRAP.nl_max_rate * 100).toFixed(1)}%</span>
                <span style={{ marginLeft: 8 }}>(target: &gt;95%)</span>
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={BOOTSTRAP.loadings.map(d => ({
                  name: VAR_SHORT[d.variable] || d.variable,
                  mean: d.mean,
                  ci_lower: d.ci_lower,
                  ci_upper: d.ci_upper,
                  range: d.ci_upper - d.ci_lower,
                  fill: VAR_COLORS[d.variable] || C.muted,
                  excludes_zero: d.excludes_zero,
                }))} margin={{ top: 8, right: 20, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey="name" tick={{ fill: C.muted, fontSize: 11 }} axisLine={{ stroke: C.borderHi }} tickLine={false} />
                  <YAxis tick={{ fill: C.muted, fontSize: 10 }} axisLine={false} tickLine={false} domain={[-1.2, 1.2]} width={40} />
                  <ReferenceLine y={0} stroke={C.borderHi} strokeDasharray="2 4" />
                  <Bar dataKey="mean" radius={[4, 4, 0, 0]}>
                    {BOOTSTRAP.loadings.map((d, i) => (
                      <Cell key={i} fill={VAR_COLORS[d.variable] || C.muted} fillOpacity={d.excludes_zero ? 1 : 0.4} />
                    ))}
                  </Bar>
                  <Tooltip
                    formatter={(v, name, props) => {
                      const d = props.payload;
                      return [`Mean: ${d.mean.toFixed(4)} [${d.ci_lower.toFixed(4)}, ${d.ci_upper.toFixed(4)}]`, "Loading"];
                    }}
                    contentStyle={{ background: C.panel, border: `1px solid ${C.borderHi}`, borderRadius: 8, color: C.text, fontSize: 11 }}
                  />
                </BarChart>
              </ResponsiveContainer>

              {/* CI Table */}
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11, marginTop: 8 }}>
                <thead>
                  <tr style={{ color: C.muted, borderBottom: `1px solid ${C.borderHi}` }}>
                    <th style={{ padding: "6px 8px", textAlign: "left" }}>Variable</th>
                    <th style={{ padding: "6px 8px", textAlign: "right" }}>Mean</th>
                    <th style={{ padding: "6px 8px", textAlign: "right" }}>95% CI Lower</th>
                    <th style={{ padding: "6px 8px", textAlign: "right" }}>95% CI Upper</th>
                    <th style={{ padding: "6px 8px", textAlign: "center" }}>Excl. Zero</th>
                  </tr>
                </thead>
                <tbody>
                  {BOOTSTRAP.loadings.map(d => (
                    <tr key={d.variable} style={{ borderBottom: `1px solid ${C.border}` }}>
                      <td style={{ padding: "6px 8px", color: VAR_COLORS[d.variable] || C.text, fontWeight: 600 }}>{VAR_SHORT[d.variable] || d.variable}</td>
                      <td style={{ padding: "6px 8px", textAlign: "right", color: C.text, fontWeight: 700 }}>{d.mean > 0 ? "+" : ""}{d.mean.toFixed(4)}</td>
                      <td style={{ padding: "6px 8px", textAlign: "right", color: C.dim }}>{d.ci_lower.toFixed(4)}</td>
                      <td style={{ padding: "6px 8px", textAlign: "right", color: C.dim }}>{d.ci_upper.toFixed(4)}</td>
                      <td style={{ padding: "6px 8px", textAlign: "center", color: d.excludes_zero ? C.green : C.red, fontWeight: 700 }}>
                        {d.excludes_zero ? "Yes" : "No"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Model Info */}
            <div style={{ background: C.border, borderRadius: 10, padding: 14, marginTop: 14, fontSize: 12, color: C.muted, lineHeight: 2 }}>
              <div style={{ color: "#f8fafc", fontWeight: 700, fontSize: 13, marginBottom: 6 }}>v2.0 Key Difference from v1.0</div>
              <div><span style={{ color: C.index }}>v2.0 (BTC-blind)</span>: PCA unsupervised &rarr; loadings reflect pure liquidity structure</div>
              <div><span style={{ color: C.btc }}>v1.0 (Grid Search)</span>: 88,209 weight combinations optimized against BTC &rarr; overfitted</div>
              <div style={{ marginTop: 6 }}>NL loading <span style={{ color: C.nl, fontWeight: 700 }}>+{META_V2.loadings.NL_level?.toFixed(3)}</span> is the dominant signal (v1.0: only 0.5 weight)</div>
            </div>
          </>
        )}

        {/* ══════════ TAB: CWS Profile ══════════ */}
        {tab === "cws" && (
          <>
            {/* CWS Composite Score by Lag */}
            <div style={{ background: C.panel, borderRadius: 12, padding: "14px 14px 8px", border: `1px solid ${C.border}` }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#f8fafc", marginBottom: 2 }}>
                Composite Waveform Score (CWS) by Lag
              </div>
              <div style={{ fontSize: 10, color: C.dim, marginBottom: 10 }}>
                CWS = 0.4&times;MDA + 0.3&times;(1-SBD) + 0.2&times;CosSim + 0.1&times;Tau &middot; Optimal: lag={META_V2.optimal_lag}
              </div>
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={CWS_PROFILE} margin={{ top: 8, right: 20, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey="lag" tick={{ fill: C.muted, fontSize: 10 }} axisLine={{ stroke: C.borderHi }} tickLine={false}
                    label={{ value: "Lag (months)", position: "insideBottom", offset: -4, fill: C.dim, fontSize: 10 }} />
                  <YAxis tick={{ fill: C.muted, fontSize: 10 }} axisLine={false} tickLine={false} width={40} />
                  <ReferenceLine y={META_V2.best_cws} stroke={C.purple} strokeDasharray="4 4"
                    label={{ value: `best=${META_V2.best_cws.toFixed(3)}`, fill: C.purple, fontSize: 10, position: "right" }} />
                  <Bar dataKey="mda_contrib" stackId="cws" fill={C.mda} name="MDA (40%)" />
                  <Bar dataKey="sbd_contrib" stackId="cws" fill={C.sbd} name="1-SBD (30%)" />
                  <Bar dataKey="cos_contrib" stackId="cws" fill={C.cos} name="CosSim (20%)" />
                  <Bar dataKey="tau_contrib" stackId="cws" fill={C.tau} name="Tau (10%)" radius={[4, 4, 0, 0]} />
                  <Tooltip contentStyle={{ background: C.panel, border: `1px solid ${C.borderHi}`, borderRadius: 8, color: C.text, fontSize: 11 }}
                    formatter={(v, name) => [v.toFixed(4), name]} />
                </BarChart>
              </ResponsiveContainer>
              {/* Legend */}
              <div style={{ display: "flex", gap: 14, justifyContent: "center", padding: "4px 0 8px", fontSize: 10 }}>
                <span style={{ color: C.mda }}>&#9632; MDA (40%)</span>
                <span style={{ color: C.sbd }}>&#9632; 1-SBD (30%)</span>
                <span style={{ color: C.cos }}>&#9632; CosSim (20%)</span>
                <span style={{ color: C.tau }}>&#9632; Tau (10%)</span>
              </div>
            </div>

            {/* Sub-metrics by Lag */}
            <div style={{ background: C.panel, borderRadius: 12, padding: "14px 14px 8px", border: `1px solid ${C.border}`, marginTop: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#f8fafc", marginBottom: 2 }}>
                Individual Metrics by Lag
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={XCORR_V2} margin={{ top: 8, right: 20, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey="lag" tick={{ fill: C.muted, fontSize: 10 }} axisLine={{ stroke: C.borderHi }} tickLine={false} />
                  <YAxis tick={{ fill: C.muted, fontSize: 10 }} axisLine={false} tickLine={false} domain={[-1, 1]} width={40} />
                  <ReferenceLine y={0} stroke={C.borderHi} strokeDasharray="2 4" />
                  <ReferenceLine y={0.5} stroke={C.dim} strokeDasharray="2 6" strokeOpacity={0.4} />
                  <Line dataKey="pearson_r" stroke={C.cyan} strokeWidth={2} dot={{ fill: C.cyan, r: 3 }} name="Pearson r" />
                  <Line dataKey="mda" stroke={C.mda} strokeWidth={2} dot={{ fill: C.mda, r: 3 }} name="MDA" />
                  <Line dataKey="cosine_sim" stroke={C.cos} strokeWidth={1.5} dot={{ fill: C.cos, r: 2 }} name="CosSim" strokeDasharray="4 2" />
                  <Line dataKey="kendall_tau" stroke={C.tau} strokeWidth={1.5} dot={{ fill: C.tau, r: 2 }} name="Kendall Tau" strokeDasharray="4 2" />
                  <Tooltip contentStyle={{ background: C.panel, border: `1px solid ${C.borderHi}`, borderRadius: 8, color: C.text, fontSize: 11 }}
                    formatter={(v) => v.toFixed(4)} />
                </LineChart>
              </ResponsiveContainer>
              <div style={{ display: "flex", gap: 14, justifyContent: "center", padding: "4px 0 8px", fontSize: 10 }}>
                <span style={{ color: C.cyan }}>&#9679; Pearson r</span>
                <span style={{ color: C.mda }}>&#9679; MDA</span>
                <span style={{ color: C.cos }}>&#9679; CosSim</span>
                <span style={{ color: C.tau }}>&#9679; Kendall Tau</span>
              </div>
            </div>

            {/* CWS Detail Table */}
            <div style={{ background: C.panel, borderRadius: 12, padding: 14, border: `1px solid ${C.border}`, marginTop: 14, overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
                <thead>
                  <tr style={{ color: C.muted, borderBottom: `1px solid ${C.borderHi}` }}>
                    <th style={{ padding: "6px 6px", textAlign: "center" }}>Lag</th>
                    <th style={{ padding: "6px 6px", textAlign: "right" }}>CWS</th>
                    <th style={{ padding: "6px 6px", textAlign: "right" }}>Pearson r</th>
                    <th style={{ padding: "6px 6px", textAlign: "right" }}>MDA</th>
                    <th style={{ padding: "6px 6px", textAlign: "right" }}>SBD</th>
                    <th style={{ padding: "6px 6px", textAlign: "right" }}>CosSim</th>
                    <th style={{ padding: "6px 6px", textAlign: "right" }}>Tau</th>
                  </tr>
                </thead>
                <tbody>
                  {XCORR_V2.map((row, i) => {
                    const cwsRow = CWS_PROFILE[i];
                    const isBest = row.lag === META_V2.optimal_lag;
                    return (
                      <tr key={row.lag} style={{ borderBottom: `1px solid ${C.border}`, background: isBest ? "rgba(124,58,237,0.1)" : "transparent" }}>
                        <td style={{ padding: "6px 6px", textAlign: "center", color: isBest ? C.purple : C.text, fontWeight: isBest ? 700 : 400 }}>{row.lag}</td>
                        <td style={{ padding: "6px 6px", textAlign: "right", color: C.purple, fontWeight: 700 }}>{cwsRow?.cws?.toFixed(4) || "-"}</td>
                        <td style={{ padding: "6px 6px", textAlign: "right", color: row.pearson_r >= 0 ? C.green : C.red }}>{row.pearson_r.toFixed(4)}</td>
                        <td style={{ padding: "6px 6px", textAlign: "right", color: row.mda >= 0.6 ? C.green : C.muted }}>{(row.mda * 100).toFixed(1)}%</td>
                        <td style={{ padding: "6px 6px", textAlign: "right", color: C.dim }}>{row.sbd.toFixed(4)}</td>
                        <td style={{ padding: "6px 6px", textAlign: "right", color: row.cosine_sim >= 0 ? C.green : C.red }}>{row.cosine_sim.toFixed(4)}</td>
                        <td style={{ padding: "6px 6px", textAlign: "right", color: C.dim }}>{row.kendall_tau.toFixed(4)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* ══════════ TAB: Robustness ══════════ */}
        {tab === "robust" && (
          <>
            {/* Granger Causality */}
            <div style={{ background: C.panel, borderRadius: 12, padding: 14, border: `1px solid ${C.border}` }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#f8fafc", marginBottom: 8 }}>
                Granger Causality Test
              </div>
              <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
                <div style={{ background: C.bg, borderRadius: 8, padding: "10px 16px", flex: 1, minWidth: 200 }}>
                  <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>Index &rarr; BTC (forward)</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: String(META_V2.granger.forward_significant).toLowerCase() === "true" ? C.green : C.red }}>
                    p = {Number(META_V2.granger.forward_p).toFixed(4)}
                  </div>
                  <div style={{ fontSize: 10, color: C.dim, marginTop: 2 }}>
                    {String(META_V2.granger.forward_significant).toLowerCase() === "true" ? "Significant (p < 0.05)" : "Not significant (p >= 0.05)"}
                  </div>
                </div>
                <div style={{ background: C.bg, borderRadius: 8, padding: "10px 16px", flex: 1, minWidth: 200 }}>
                  <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>BTC &rarr; Index (reverse)</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: String(META_V2.granger.reverse_significant).toLowerCase() === "true" ? C.red : C.green }}>
                    p = {Number(META_V2.granger.reverse_p).toFixed(4)}
                  </div>
                  <div style={{ fontSize: 10, color: C.dim, marginTop: 2 }}>
                    {String(META_V2.granger.reverse_significant).toLowerCase() === "true" ? "Significant (reverse causality!)" : "Not significant (good)"}
                  </div>
                </div>
                <div style={{ background: C.bg, borderRadius: 8, padding: "10px 16px", flex: 1, minWidth: 200 }}>
                  <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>Unidirectional</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: String(META_V2.granger.unidirectional).toLowerCase() === "true" ? C.green : C.yellow }}>
                    {String(META_V2.granger.unidirectional).toLowerCase() === "true" ? "YES" : "NO"}
                  </div>
                  <div style={{ fontSize: 10, color: C.dim, marginTop: 2 }}>
                    Target: Index &rarr; BTC only
                  </div>
                </div>
              </div>
            </div>

            {/* CPCV Distribution */}
            <div style={{ background: C.panel, borderRadius: 12, padding: "14px 14px 8px", border: `1px solid ${C.border}`, marginTop: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#f8fafc", marginBottom: 2 }}>
                Combinatorial Purged Cross-Validation (CPCV)
              </div>
              <div style={{ fontSize: 10, color: C.dim, marginBottom: 10 }}>
                {CPCV.n_paths} paths &middot; CWS Mean: <span style={{ color: C.purple, fontWeight: 700 }}>{CPCV.cws_mean?.toFixed(4)}</span>
                &plusmn; {CPCV.cws_std?.toFixed(4)}
                &middot; MDA Mean: <span style={{ color: C.mda, fontWeight: 700 }}>{(CPCV.mda_mean * 100)?.toFixed(1)}%</span>
              </div>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={(CPCV.cws_all || []).map((v, i) => ({
                  path: i + 1,
                  cws: v,
                  fill: v >= CPCV.cws_mean ? C.green : v >= 0.3 ? C.yellow : C.red,
                }))} margin={{ top: 8, right: 20, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey="path" tick={{ fill: C.dim, fontSize: 8 }} axisLine={{ stroke: C.borderHi }} tickLine={false}
                    label={{ value: "CPCV Path", position: "insideBottom", offset: -4, fill: C.dim, fontSize: 10 }} />
                  <YAxis tick={{ fill: C.muted, fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, 1.1]} width={36} />
                  <ReferenceLine y={CPCV.cws_mean} stroke={C.purple} strokeDasharray="4 4"
                    label={{ value: `mean=${CPCV.cws_mean?.toFixed(3)}`, fill: C.purple, fontSize: 9, position: "right" }} />
                  <Bar dataKey="cws" radius={[2, 2, 0, 0]}>
                    {(CPCV.cws_all || []).map((v, i) => (
                      <Cell key={i} fill={v >= CPCV.cws_mean ? C.green : v >= 0.3 ? C.yellow : C.red} fillOpacity={0.8} />
                    ))}
                  </Bar>
                  <Tooltip formatter={v => v.toFixed(4)} contentStyle={{ background: C.panel, border: `1px solid ${C.borderHi}`, borderRadius: 8, color: C.text, fontSize: 11 }} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Bootstrap Lag Distribution */}
            <div style={{ background: C.panel, borderRadius: 12, padding: 14, border: `1px solid ${C.border}`, marginTop: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#f8fafc", marginBottom: 8 }}>
                Bootstrap Lag Distribution (n={BOOTSTRAP.lag_distribution.n_samples})
              </div>
              <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
                {[
                  ["Mean", BOOTSTRAP.lag_distribution.mean, "m"],
                  ["Median", BOOTSTRAP.lag_distribution.median, "m"],
                  ["Mode", BOOTSTRAP.lag_distribution.mode, "m"],
                  ["95% CI", `${BOOTSTRAP.lag_distribution.ci_lower} ~ ${BOOTSTRAP.lag_distribution.ci_upper}`, "m"],
                ].map(([label, val, unit]) => (
                  <div key={label} style={{ background: C.bg, borderRadius: 8, padding: "8px 14px", minWidth: 100 }}>
                    <div style={{ fontSize: 10, color: C.muted }}>{label}</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: C.purple }}>{val}<span style={{ fontSize: 10, color: C.dim }}>{unit}</span></div>
                  </div>
                ))}
              </div>
            </div>

            {/* CPCV Best/Worst Path */}
            <div style={{ background: C.border, borderRadius: 10, padding: 14, marginTop: 14, fontSize: 12, color: C.muted, lineHeight: 2 }}>
              <div style={{ color: "#f8fafc", fontWeight: 700, fontSize: 13, marginBottom: 6 }}>Robustness Summary</div>
              <div>
                <span style={{ color: C.green }}>Best Path</span>:
                CWS={CPCV.best_path?.cws?.toFixed(4)},
                lag={CPCV.best_path?.optimal_lag},
                MDA={(CPCV.best_path?.mda * 100)?.toFixed(1)}%,
                r={CPCV.best_path?.pearson_r?.toFixed(4)}
              </div>
              <div>
                <span style={{ color: C.red }}>Worst Path</span>:
                CWS={CPCV.worst_path?.cws?.toFixed(4)},
                lag={CPCV.worst_path?.optimal_lag},
                MDA={(CPCV.worst_path?.mda * 100)?.toFixed(1)}%,
                r={CPCV.worst_path?.pearson_r?.toFixed(4)}
              </div>
              <div style={{ marginTop: 6 }}>
                All Positive Rate: <span style={{ color: CPCV.all_positive_rate > 0.5 ? C.green : C.red, fontWeight: 700 }}>{(CPCV.all_positive_rate * 100).toFixed(1)}%</span>
                of CPCV paths have all r &gt; 0
              </div>
            </div>
          </>
        )}

        {/* ── Footer ── */}
        <div style={{ textAlign: "center", padding: "20px 0 10px", fontSize: 10, color: C.dim }}>
          BTC Liquidity Model v2.0.0 | 3-Stage Pipeline ({META_V2.method}) | {INDEX_DATA.length} months | CWS={META_V2.best_cws.toFixed(3)} @lag={META_V2.optimal_lag}m
        </div>
      </div>
    </div>
  );
}
