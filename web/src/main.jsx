import React, { useState, lazy, Suspense, Component } from 'react';
import ReactDOM from 'react-dom/client';

// BTC (direct import — existing code untouched)
import App from './App';
import AppV2 from './AppV2';

// KOSPI (lazy load for bundle splitting)
const KospiApp = lazy(() => import('./simulators/kospi/KospiApp'));

/* ── Error Boundary ── */
class ErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div style={{ background: "#020617", color: "#f87171", padding: 40,
          fontFamily: "'JetBrains Mono', monospace", minHeight: "100vh" }}>
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>Runtime Error</h2>
          <pre style={{ color: "#e2e8f0", fontSize: 12, whiteSpace: "pre-wrap" }}>
            {this.state.error.message}
          </pre>
          <pre style={{ color: "#64748b", fontSize: 10, marginTop: 8, whiteSpace: "pre-wrap" }}>
            {this.state.error.stack}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

const FONT = "'JetBrains Mono', monospace";

const SIMULATORS = [
  { id: "btc", label: "BTC Liquidity", color: "#f59e0b" },
  { id: "kospi", label: "KOSPI Crisis", color: "#ef4444" },
];

function Root() {
  const [sim, setSim] = useState("kospi");
  const [btcVer, setBtcVer] = useState("v2");

  return (
    <>
      {/* ── Simulator Select Bar ── fixed top */}
      <div style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 9999,
        display: "flex", alignItems: "center", gap: 4,
        background: "#020617", borderBottom: "1px solid #1e293b",
        padding: "6px 16px", height: 40,
      }}>
        <span style={{ color: "#64748b", fontSize: 11, fontFamily: FONT, marginRight: 8 }}>
          FINANCE SIM
        </span>

        {/* Simulator buttons */}
        {SIMULATORS.map(s => (
          <button key={s.id} onClick={() => setSim(s.id)} style={{
            background: sim === s.id ? s.color : "transparent",
            color: sim === s.id ? (s.id === "btc" ? "#000" : "#fff") : "#94a3b8",
            border: "none", borderRadius: 6, padding: "4px 14px",
            fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: FONT,
            transition: "all 0.15s",
          }}>{s.label}</button>
        ))}

        {/* BTC sub-toggle: v1 / v2 */}
        {sim === "btc" && (
          <div style={{ marginLeft: 8, display: "flex", gap: 2,
            background: "#0f172a", borderRadius: 6, border: "1px solid #334155", padding: 2 }}>
            {["v1", "v2"].map(v => (
              <button key={v} onClick={() => setBtcVer(v)} style={{
                background: btcVer === v ? "#7c3aed" : "transparent",
                color: btcVer === v ? "#fff" : "#64748b",
                border: "none", borderRadius: 4, padding: "2px 10px",
                fontSize: 10, fontWeight: 700, cursor: "pointer", fontFamily: FONT,
              }}>{v}</button>
            ))}
          </div>
        )}
      </div>

      {/* ── Simulator Content ── */}
      <div style={{ paddingTop: 40 }}>
        {sim === "btc" && (btcVer === "v1" ? <App /> : <AppV2 />)}
        {sim === "kospi" && (
          <Suspense fallback={
            <div style={{ background: "#020617", minHeight: "100vh", display: "flex",
              alignItems: "center", justifyContent: "center", color: "#94a3b8",
              fontFamily: FONT, fontSize: 14 }}>
              Loading KOSPI Crisis Detector...
            </div>
          }>
            <KospiApp />
          </Suspense>
        )}
      </div>
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <Root />
    </ErrorBoundary>
  </React.StrictMode>
);
