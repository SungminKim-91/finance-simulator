import { useState, useMemo } from "react";
import {
  ComposedChart, Line, Area, Bar, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, ReferenceArea, BarChart,
  LineChart,
} from "recharts";
import { DATA, XCORR, WALK_FORWARD, WEIGHTS, META } from "./data";

/* ── Color Palette ── */
const C = {
  bg: "#020617", panel: "#0f172a", border: "#1e293b", borderHi: "#334155",
  text: "#e2e8f0", muted: "#94a3b8", dim: "#64748b",
  btc: "#f59e0b", btcSub: "#fbbf24",
  score: "#22d3ee", scoreSub: "#06b6d4",
  nl: "#3b82f6", gm2: "#8b5cf6", sofr: "#ef4444", hy: "#f97316", cme: "#10b981",
  green: "#4ade80", red: "#f87171", purple: "#a78bfa",
};

const VAR_COLORS = {
  NL_level: C.nl, GM2_resid: C.gm2, SOFR_binary: C.sofr,
  HY_level: C.hy, CME_basis: C.cme,
};
const VAR_LABELS = {
  NL_level: "Net Liquidity", GM2_resid: "GM2 Residual", SOFR_binary: "SOFR Binary",
  HY_level: "HY Spread", CME_basis: "CME Basis",
};

/* ── Custom Tooltip ── */
const Tip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div style={{ background: C.panel, border: `1px solid ${C.borderHi}`, borderRadius: 8, padding: "10px 14px", color: C.text, fontSize: 12, lineHeight: 1.8, maxWidth: 240 }}>
      <div style={{ fontWeight: 700, color: C.muted, marginBottom: 2 }}>{d.date}</div>
      <div>BTC: <span style={{ color: C.btc, fontWeight: 700 }}>${d.btc?.toLocaleString()}</span></div>
      {d.shiftScoreRaw != null && <div>Score: <span style={{ color: C.score, fontWeight: 700 }}>{d.shiftScoreRaw > 0 ? "+" : ""}{d.shiftScoreRaw.toFixed(3)}</span></div>}
      {d.log_btc != null && <div>log₁₀(BTC): <span style={{ color: C.btcSub, fontWeight: 700 }}>{d.log_btc.toFixed(4)}</span></div>}
    </div>
  );
};

const VarTip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div style={{ background: C.panel, border: `1px solid ${C.borderHi}`, borderRadius: 8, padding: "10px 14px", color: C.text, fontSize: 11, lineHeight: 1.8, maxWidth: 220 }}>
      <div style={{ fontWeight: 700, color: C.muted, marginBottom: 2 }}>{d.date}</div>
      {Object.entries(VAR_COLORS).map(([k, c]) => (
        d[k] != null && <div key={k}>{VAR_LABELS[k]}: <span style={{ color: c, fontWeight: 700 }}>{d[k] > 0 ? "+" : ""}{d[k].toFixed(3)}</span></div>
      ))}
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

/* ── Main App ── */
export default function App() {
  const [shift, setShift] = useState(META.optimal_lag);
  const [tab, setTab] = useState("main"); // main | vars | wf

  /* Shift score data by lag — clip extreme SOFR outliers for chart readability */
  const chartData = useMemo(() => {
    return DATA.map((d, i) => {
      const si = i - shift;
      const has = si >= 0 && si < DATA.length;
      const raw = has ? DATA[si].score : null;
      return {
        ...d,
        shiftScore: raw != null ? Math.max(-3, Math.min(3, raw)) : null,
        shiftScoreRaw: raw,
      };
    });
  }, [shift]);

  /* Live correlation at current shift (uses raw unclipped score) */
  const corr = useMemo(() => pearson(chartData, "shiftScoreRaw", "log_btc"), [chartData]);

  /* G-1: Bull/Bear phase regions for background shading */
  const phases = useMemo(() => {
    const regions = [];
    let start = null;
    let ptype = null;
    chartData.forEach((d, i) => {
      if (d.shiftScore == null) return;
      const cur = d.shiftScore > 0 ? "bull" : "bear";
      if (cur !== ptype) {
        if (start !== null) regions.push({ start, end: i, ptype });
        start = i;
        ptype = cur;
      }
    });
    if (start !== null) regions.push({ start, end: chartData.length - 1, ptype });
    return regions;
  }, [chartData]);

  const labelDate = (v) => chartData[parseInt(v)]?.date || "";

  /* Walk-Forward bar data */
  const wfData = WALK_FORWARD.windows.map(w => ({
    name: `W${w.window}`,
    corr: w.correlation,
    fill: w.correlation >= 0 ? C.green : C.red,
  }));

  /* G-5: Walk-Forward Std */
  const wfStd = useMemo(() => {
    const mean = WALK_FORWARD.mean_oos_corr;
    return Math.sqrt(WALK_FORWARD.windows.reduce((s, w) => s + (w.correlation - mean) ** 2, 0) / WALK_FORWARD.windows.length);
  }, []);

  /* G-3: Cumulative OOS data — running average correlation + BTC log return per window */
  const cumulOOS = useMemo(() => {
    let sumCorr = 0;
    return WALK_FORWARD.windows.map((w, i) => {
      sumCorr += w.correlation;
      const cumAvg = sumCorr / (i + 1);
      // Extract test period dates and compute BTC return
      const testEnd = w.test_range?.split(" ~ ")[1];
      const testStart = w.test_range?.split(" ~ ")[0];
      const startRec = DATA.find(d => d.date === testStart);
      const endRec = DATA.find(d => d.date === testEnd);
      const btcReturn = startRec && endRec ? ((endRec.log_btc - startRec.log_btc) * 10) : 0; // scaled
      return {
        name: `W${w.window}`,
        testRange: w.test_range,
        cumAvgCorr: +cumAvg.toFixed(4),
        windowCorr: w.correlation,
        btcReturn: +btcReturn.toFixed(3),
      };
    });
  }, []);

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, fontFamily: "'JetBrains Mono', 'SF Mono', monospace", padding: "20px 16px" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>

        {/* ── Header ── */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: "#f8fafc", margin: 0 }}>
              BTC Liquidity Simulator <span style={{ fontSize: 12, color: C.dim, fontWeight: 400 }}>v1.0.0</span>
            </h1>
            <p style={{ fontSize: 11, color: C.dim, margin: "4px 0 0" }}>
              5-Variable Global Liquidity Index → BTC Price Direction (5-9m lead)
            </p>
          </div>
          {/* Signal Badge */}
          <div style={{
            background: META.signal === "BULLISH" ? "rgba(74,222,128,0.15)" : "rgba(248,113,113,0.15)",
            border: `1px solid ${META.signal === "BULLISH" ? C.green : C.red}`,
            borderRadius: 8, padding: "8px 16px", textAlign: "center",
          }}>
            <div style={{ fontSize: 10, color: C.muted }}>Current Signal</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: META.signal === "BULLISH" ? C.green : C.red }}>
              {META.signal}
            </div>
            <div style={{ fontSize: 10, color: C.dim }}>Score: {META.current_score.toFixed(2)}</div>
          </div>
        </div>

        {/* ── Tab Buttons ── */}
        <div style={{ display: "flex", gap: 4, marginBottom: 14 }}>
          {[["main", "Score vs BTC"], ["vars", "5 Variables"], ["wf", "Walk-Forward"]].map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)} style={{
              background: tab === k ? "#7c3aed" : C.border,
              color: tab === k ? "#fff" : C.muted,
              border: "none", borderRadius: 6, padding: "6px 14px", fontSize: 11,
              fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
            }}>{l}</button>
          ))}
        </div>

        {/* ══════════ TAB: Main Chart ══════════ */}
        {tab === "main" && (
          <>
            {/* Lag Slider */}
            <div style={{ display: "flex", gap: 12, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <button onClick={() => setShift(s => Math.max(0, s - 1))} style={{ background: C.borderHi, border: "none", color: C.text, borderRadius: 4, width: 26, height: 26, cursor: "pointer", fontSize: 15, fontFamily: "inherit" }}>-</button>
                <div style={{ background: C.border, borderRadius: 6, padding: "3px 10px", minWidth: 100, textAlign: "center" }}>
                  <span style={{ color: C.purple, fontWeight: 700, fontSize: 16 }}>{shift}</span>
                  <span style={{ color: C.dim, fontSize: 10, marginLeft: 4 }}>months lead</span>
                </div>
                <button onClick={() => setShift(s => Math.min(12, s + 1))} style={{ background: C.borderHi, border: "none", color: C.text, borderRadius: 4, width: 26, height: 26, cursor: "pointer", fontSize: 15, fontFamily: "inherit" }}>+</button>
              </div>
              <input type="range" min={0} max={12} value={shift} onChange={e => setShift(+e.target.value)}
                style={{ flex: 1, minWidth: 80, accentColor: C.purple, height: 3 }} />
            </div>

            {/* Correlation Badge */}
            <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
              <div style={{ background: C.border, borderRadius: 8, padding: "5px 12px", fontSize: 12 }}>
                <span style={{ color: C.score }}>Score</span>
                <span style={{ color: C.dim }}> vs log(BTC): </span>
                <span style={{ color: corr > 0.5 ? C.green : corr > 0.3 ? C.btcSub : C.muted, fontWeight: 700, fontSize: 14 }}>
                  r={corr.toFixed(3)}
                </span>
                <span style={{ color: C.dim, fontSize: 10 }}> @{shift}m</span>
              </div>
              <div style={{ background: C.border, borderRadius: 8, padding: "5px 12px", fontSize: 12 }}>
                <span style={{ color: C.dim }}>Optimal: </span>
                <span style={{ color: C.purple, fontWeight: 700 }}>lag={META.optimal_lag}m</span>
                <span style={{ color: C.dim }}> r=</span>
                <span style={{ color: C.green, fontWeight: 700 }}>{META.correlation.toFixed(4)}</span>
              </div>
              <div style={{ background: C.border, borderRadius: 8, padding: "5px 12px", fontSize: 12 }}>
                <span style={{ color: C.dim }}>Weights: </span>
                {Object.entries(WEIGHTS).map(([k, v]) => (
                  v !== 0 && <span key={k} style={{ color: VAR_COLORS[k], marginRight: 6 }}>
                    {k.replace("_level", "").replace("_resid", "").replace("_binary", "")}={v}
                  </span>
                ))}
              </div>
            </div>

            {/* Main Chart: Score vs BTC */}
            <div style={{ background: C.panel, borderRadius: 12, padding: "14px 8px 8px", border: `1px solid ${C.border}` }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#f8fafc", marginBottom: 2, paddingLeft: 4 }}>
                Liquidity Score vs BTC Price
              </div>
              <div style={{ fontSize: 10, color: C.dim, marginBottom: 6, paddingLeft: 4 }}>
                <span style={{ color: C.btc }}>&#9679; BTC ($, log scale)</span>
                <span style={{ marginLeft: 10, color: C.score }}>&#9679; Liquidity Score (shifted {shift}m)</span>
              </div>
              <ResponsiveContainer width="100%" height={420}>
                <ComposedChart data={chartData} margin={{ top: 8, right: 6, left: 0, bottom: 8 }}>
                  <defs>
                    <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={C.score} stopOpacity={0.12} />
                      <stop offset="50%" stopColor={C.score} stopOpacity={0} />
                      <stop offset="100%" stopColor={C.score} stopOpacity={0.06} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey={(_, i) => i} tickFormatter={labelDate} tick={{ fill: C.dim, fontSize: 9 }} interval={23} axisLine={{ stroke: C.borderHi }} tickLine={false} />
                  <YAxis yAxisId="l" tick={{ fill: C.btc, fontSize: 9 }} axisLine={false} tickLine={false}
                    tickFormatter={v => `$${Math.round(10 ** v).toLocaleString()}`}
                    domain={[2.4, 5.2]} width={58} />
                  <YAxis yAxisId="r" orientation="right" tick={{ fill: C.score, fontSize: 9 }} axisLine={false} tickLine={false}
                    domain={[-4, 4]} width={36} />
                  {/* G-1: Bull/Bear phase shading */}
                  {phases.map((p, i) => (
                    <ReferenceArea key={i} x1={p.start} x2={p.end} yAxisId="r"
                      fill={p.ptype === "bull" ? C.green : C.red} fillOpacity={0.05} strokeOpacity={0} />
                  ))}
                  <ReferenceLine yAxisId="r" y={0} stroke={C.borderHi} strokeDasharray="2 4" strokeOpacity={0.4} />
                  <Area yAxisId="r" dataKey="shiftScore" stroke="none" fill="url(#scoreGrad)" />
                  <Line yAxisId="l" dataKey="log_btc" stroke={C.btc} strokeWidth={2.2} dot={false} />
                  <Line yAxisId="r" dataKey="shiftScore" stroke={C.score} strokeWidth={1.8} dot={false} connectNulls />
                  <Tooltip content={<Tip />} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* Cross-Correlation Heatmap */}
            <div style={{ background: C.panel, borderRadius: 12, padding: "14px 14px 12px", border: `1px solid ${C.border}`, marginTop: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#f8fafc", marginBottom: 4 }}>
                Cross-Correlation: Score(t) vs log₁₀(BTC)(t+k)
              </div>
              <div style={{ fontSize: 10, color: C.dim, marginBottom: 10 }}>
                Click a cell to set the lag slider
              </div>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                {XCORR.map(({ lag, r }) => {
                  const bg = r > 0
                    ? `rgba(74,222,128,${Math.min(r * 1.4, 0.85)})`
                    : `rgba(248,113,113,${Math.min(Math.abs(r) * 1.4, 0.85)})`;
                  return (
                    <div key={lag} onClick={() => setShift(lag)} style={{
                      width: 68, height: 50, background: bg, borderRadius: 6,
                      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                      cursor: "pointer", border: shift === lag ? `2px solid ${C.purple}` : "2px solid transparent",
                      transition: "border 0.15s",
                    }}>
                      <div style={{ fontSize: 9, color: C.text }}>{lag}m</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: "#fff" }}>{r > 0 ? "+" : ""}{r.toFixed(3)}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Model Info */}
            <div style={{ background: C.border, borderRadius: 10, padding: 14, marginTop: 14, fontSize: 12, color: C.muted, lineHeight: 2 }}>
              <div style={{ color: "#f8fafc", fontWeight: 700, fontSize: 13, marginBottom: 6 }}>Model Summary</div>
              <div><span style={{ color: C.score }}>In-Sample Correlation</span>: r = {META.correlation.toFixed(4)} @ lag {META.optimal_lag}m</div>
              <div><span style={{ color: C.green }}>Walk-Forward OOS</span>: {WALK_FORWARD.n_windows} windows, mean r = {WALK_FORWARD.mean_oos_corr.toFixed(3)}</div>
              <div><span style={{ color: C.btc }}>Active Weights</span>: NL={WEIGHTS.NL_level}, SOFR={WEIGHTS.SOFR_binary}, HY={WEIGHTS.HY_level}</div>
              <div style={{ marginTop: 6, color: C.dim }}>Inactive (weight=0): GM2 Residual, CME Basis</div>
            </div>
          </>
        )}

        {/* ══════════ TAB: Variables ══════════ */}
        {tab === "vars" && (
          <div style={{ background: C.panel, borderRadius: 12, padding: "14px 8px 8px", border: `1px solid ${C.border}` }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#f8fafc", marginBottom: 2, paddingLeft: 4 }}>
              5 Variables (Z-Score)
            </div>
            <div style={{ fontSize: 10, color: C.dim, marginBottom: 6, paddingLeft: 4, display: "flex", gap: 10, flexWrap: "wrap" }}>
              {Object.entries(VAR_COLORS).map(([k, c]) => (
                <span key={k} style={{ color: c }}>&#9679; {VAR_LABELS[k]} (w={WEIGHTS[k]})</span>
              ))}
            </div>
            <ResponsiveContainer width="100%" height={450}>
              <ComposedChart data={DATA} margin={{ top: 8, right: 6, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey={(_, i) => i} tickFormatter={i => DATA[parseInt(i)]?.date || ""} tick={{ fill: C.dim, fontSize: 9 }} interval={23} axisLine={{ stroke: C.borderHi }} tickLine={false} />
                <YAxis tick={{ fill: C.muted, fontSize: 9 }} axisLine={false} tickLine={false} width={40} />
                <ReferenceLine y={0} stroke={C.borderHi} strokeDasharray="2 4" strokeOpacity={0.4} />
                {Object.entries(VAR_COLORS).map(([k, c]) => (
                  <Line key={k} dataKey={k} stroke={c} strokeWidth={1.5} dot={false} connectNulls
                    strokeOpacity={WEIGHTS[k] === 0 ? 0.3 : 1} />
                ))}
                <Tooltip content={<VarTip />} />
              </ComposedChart>
            </ResponsiveContainer>
            <div style={{ padding: "10px 8px", fontSize: 11, color: C.dim, lineHeight: 2 }}>
              <div><span style={{ color: C.nl, fontWeight: 700 }}>NL (w=0.5)</span>: Net Liquidity = WALCL - TGA - RRP. US domestic liquidity proxy.</div>
              <div><span style={{ color: C.sofr, fontWeight: 700 }}>SOFR (w=-4.0)</span>: Binary crisis detector. SOFR-IORB &gt; 20bps triggers -4x penalty.</div>
              <div><span style={{ color: C.hy, fontWeight: 700 }}>HY (w=-0.5)</span>: High Yield spread. Risk appetite measure (inverted: higher = worse).</div>
              <div style={{ color: C.dim, marginTop: 4 }}>GM2 Residual and CME Basis have weight 0 in current model (shown faded).</div>
            </div>
          </div>
        )}

        {/* ══════════ TAB: Walk-Forward ══════════ */}
        {tab === "wf" && (
          <>
            <div style={{ background: C.panel, borderRadius: 12, padding: "14px 14px 8px", border: `1px solid ${C.border}` }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#f8fafc", marginBottom: 2 }}>
                Walk-Forward Out-of-Sample Validation
              </div>
              <div style={{ fontSize: 10, color: C.dim, marginBottom: 10 }}>
                Expanding window: 60m min train / 6m test steps / {WALK_FORWARD.n_windows} windows
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={wfData} margin={{ top: 8, right: 20, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey="name" tick={{ fill: C.muted, fontSize: 10 }} axisLine={{ stroke: C.borderHi }} tickLine={false} />
                  <YAxis tick={{ fill: C.muted, fontSize: 10 }} axisLine={false} tickLine={false} domain={[-1, 1]} width={36} />
                  <ReferenceLine y={0} stroke={C.borderHi} />
                  <ReferenceLine y={WALK_FORWARD.mean_oos_corr} stroke={C.purple} strokeDasharray="4 4" label={{ value: `mean=${WALK_FORWARD.mean_oos_corr.toFixed(3)}`, fill: C.purple, fontSize: 10, position: "right" }} />
                  {/* G-5: Std deviation lines */}
                  <ReferenceLine y={WALK_FORWARD.mean_oos_corr + wfStd} stroke={C.dim} strokeDasharray="2 6" label={{ value: `+1σ`, fill: C.dim, fontSize: 9, position: "right" }} />
                  <ReferenceLine y={WALK_FORWARD.mean_oos_corr - wfStd} stroke={C.dim} strokeDasharray="2 6" label={{ value: `−1σ`, fill: C.dim, fontSize: 9, position: "right" }} />
                  <Bar dataKey="corr" radius={[4, 4, 0, 0]}>
                    {wfData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Bar>
                  <Tooltip formatter={v => v.toFixed(4)} contentStyle={{ background: C.panel, border: `1px solid ${C.borderHi}`, borderRadius: 8, color: C.text, fontSize: 12 }} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* G-3: Cumulative OOS Correlation vs BTC Return */}
            <div style={{ background: C.panel, borderRadius: 12, padding: "14px 14px 8px", border: `1px solid ${C.border}`, marginTop: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#f8fafc", marginBottom: 2 }}>
                Cumulative OOS Correlation vs BTC Return
              </div>
              <div style={{ fontSize: 10, color: C.dim, marginBottom: 10 }}>
                <span style={{ color: C.purple }}>&#9679; Cum. Avg Corr</span>
                <span style={{ marginLeft: 10, color: C.btc }}>&#9679; BTC Return (scaled)</span>
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={cumulOOS} margin={{ top: 8, right: 20, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey="name" tick={{ fill: C.muted, fontSize: 10 }} axisLine={{ stroke: C.borderHi }} tickLine={false} />
                  <YAxis tick={{ fill: C.muted, fontSize: 10 }} axisLine={false} tickLine={false} width={40} />
                  <ReferenceLine y={0} stroke={C.borderHi} />
                  <Line dataKey="cumAvgCorr" stroke={C.purple} strokeWidth={2.2} dot={{ fill: C.purple, r: 3 }} name="Cum. Avg Corr" />
                  <Line dataKey="btcReturn" stroke={C.btc} strokeWidth={1.5} dot={{ fill: C.btc, r: 3 }} strokeDasharray="4 2" name="BTC Return" />
                  <Tooltip contentStyle={{ background: C.panel, border: `1px solid ${C.borderHi}`, borderRadius: 8, color: C.text, fontSize: 11 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* WF Detail Table */}
            <div style={{ background: C.panel, borderRadius: 12, padding: 14, border: `1px solid ${C.border}`, marginTop: 14, overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
                <thead>
                  <tr style={{ color: C.muted, borderBottom: `1px solid ${C.borderHi}` }}>
                    <th style={{ padding: "6px 8px", textAlign: "left" }}>Window</th>
                    <th style={{ padding: "6px 8px", textAlign: "center" }}>Train</th>
                    <th style={{ padding: "6px 8px", textAlign: "center" }}>Test</th>
                    <th style={{ padding: "6px 8px", textAlign: "center" }}>N</th>
                    <th style={{ padding: "6px 8px", textAlign: "right" }}>Corr</th>
                    <th style={{ padding: "6px 8px", textAlign: "right" }}>p-value</th>
                  </tr>
                </thead>
                <tbody>
                  {WALK_FORWARD.windows.map(w => (
                    <tr key={w.window} style={{ borderBottom: `1px solid ${C.border}` }}>
                      <td style={{ padding: "6px 8px", color: C.text }}>{w.window}</td>
                      <td style={{ padding: "6px 8px", textAlign: "center", color: C.dim }}>{w.train_range}</td>
                      <td style={{ padding: "6px 8px", textAlign: "center", color: C.dim }}>{w.test_range}</td>
                      <td style={{ padding: "6px 8px", textAlign: "center", color: C.dim }}>{w.n_test}</td>
                      <td style={{ padding: "6px 8px", textAlign: "right", color: w.correlation >= 0 ? C.green : C.red, fontWeight: 700 }}>
                        {w.correlation > 0 ? "+" : ""}{w.correlation.toFixed(4)}
                      </td>
                      <td style={{ padding: "6px 8px", textAlign: "right", color: w.p_value < 0.05 ? C.btcSub : C.dim }}>
                        {w.p_value.toFixed(4)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr style={{ borderTop: `2px solid ${C.borderHi}` }}>
                    <td colSpan={4} style={{ padding: "8px 8px", color: C.muted, fontWeight: 700 }}>Mean OOS</td>
                    <td style={{ padding: "8px 8px", textAlign: "right", color: C.purple, fontWeight: 700, fontSize: 13 }}>
                      {WALK_FORWARD.mean_oos_corr.toFixed(3)}
                    </td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>

            <div style={{ background: C.border, borderRadius: 10, padding: 14, marginTop: 14, fontSize: 11, color: C.muted, lineHeight: 2 }}>
              <div style={{ color: "#f8fafc", fontWeight: 700, marginBottom: 4 }}>Walk-Forward Notes</div>
              <div>Windows 3-4 (2022 mid): Negative correlation due to COVID→rate-hike regime transition</div>
              <div>Windows 1-2, 7-9: Strong positive OOS correlation (0.47 ~ 0.81)</div>
              <div>6/9 windows show positive correlation — model generalizes across most regimes</div>
            </div>
          </>
        )}

        {/* ── Footer ── */}
        <div style={{ textAlign: "center", padding: "20px 0 10px", fontSize: 10, color: C.dim }}>
          BTC Liquidity Model v1.0.0 | Data: 2016-01 ~ 2025-12 ({DATA.length} months) | corr={META.correlation.toFixed(4)} @lag={META.optimal_lag}m
        </div>
      </div>
    </div>
  );
}
