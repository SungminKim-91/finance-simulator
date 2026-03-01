import React, { useState } from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import AppV2 from './AppV2';

function Root() {
  const [version, setVersion] = useState("v2");

  return (
    <>
      {/* Version Toggle — fixed top-right */}
      <div style={{
        position: "fixed", top: 12, right: 16, zIndex: 9999,
        display: "flex", gap: 2, background: "#0f172a", borderRadius: 8,
        border: "1px solid #334155", padding: 3,
      }}>
        <button onClick={() => setVersion("v1")} style={{
          background: version === "v1" ? "#f59e0b" : "transparent",
          color: version === "v1" ? "#000" : "#94a3b8",
          border: "none", borderRadius: 6, padding: "4px 12px", fontSize: 11,
          fontWeight: 700, cursor: "pointer", fontFamily: "'JetBrains Mono', monospace",
        }}>v1.0</button>
        <button onClick={() => setVersion("v2")} style={{
          background: version === "v2" ? "#7c3aed" : "transparent",
          color: version === "v2" ? "#fff" : "#94a3b8",
          border: "none", borderRadius: 6, padding: "4px 12px", fontSize: 11,
          fontWeight: 700, cursor: "pointer", fontFamily: "'JetBrains Mono', monospace",
        }}>v2.0</button>
      </div>
      {version === "v1" ? <App /> : <AppV2 />}
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
