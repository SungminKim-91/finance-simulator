/**
 * KospiHeader — 공통 헤더 컴포넌트
 *
 * 탭 전환 시에도 항상 표시되는 시장 현황 헤더.
 * 표시: KOSPI | 삼성전자 | SK하이닉스 | USD/KRW | VIX | 업데이트 시각
 * Phase 2+: CrisisGauge (위기점수 게이지) 추가 예정
 */
import { C } from "./colors";
import { MARKET_DATA, GLOBAL_DATA, META } from "./data/kospi_data";

const FONT = "'JetBrains Mono', monospace";

function MetricCard({ label, value, change, inverted = false }) {
  const color =
    change == null || change === 0
      ? C.muted
      : (inverted ? change < 0 : change > 0)
        ? C.green
        : C.red;
  const arrow = change > 0 ? "+" : "";

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        padding: "4px 12px",
        minWidth: 90,
      }}
    >
      <div style={{ color: C.muted, fontSize: 9, marginBottom: 1 }}>
        {label}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
        <span style={{ color: C.text, fontSize: 14, fontWeight: 700 }}>
          {typeof value === "number" ? value.toLocaleString() : value ?? "—"}
        </span>
        {change != null && (
          <span style={{ color, fontSize: 10 }}>
            {arrow}{change.toFixed(2)}%
          </span>
        )}
      </div>
    </div>
  );
}

export default function KospiHeader() {
  const latest = MARKET_DATA[MARKET_DATA.length - 1] || {};
  const latestG = GLOBAL_DATA[GLOBAL_DATA.length - 1] || {};

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 2,
        padding: "6px 16px",
        background: C.panel,
        borderBottom: `1px solid ${C.border}`,
        fontFamily: FONT,
        flexWrap: "wrap",
        position: "sticky",
        top: 40,
        zIndex: 101,
      }}
    >
      {/* Phase 2+: <CrisisGauge score={CRISIS_SCORE.current} /> */}

      <MetricCard
        label="KOSPI"
        value={latest.kospi}
        change={latest.kospi_change_pct}
      />
      <div style={{ width: 1, height: 24, background: C.border }} />
      <MetricCard
        label="삼성전자"
        value={latest.samsung}
        change={latest.samsung_change_pct}
      />
      <div style={{ width: 1, height: 24, background: C.border }} />
      <MetricCard
        label="SK하이닉스"
        value={latest.hynix}
        change={latest.hynix_change_pct}
      />
      <div style={{ width: 1, height: 24, background: C.border }} />
      <MetricCard
        label="USD/KRW"
        value={latestG.usd_krw}
        change={null}
        inverted
      />
      <div style={{ width: 1, height: 24, background: C.border }} />
      <MetricCard label="VIX" value={latestG.vix} change={null} />

      <div style={{ flex: 1 }} />

      <div style={{ color: C.dim, fontSize: 9, padding: "0 4px" }}>
        {META.last_updated?.slice(0, 16).replace("T", " ")}
        {META.data_source === "sample" && (
          <span style={{ color: C.yellow, marginLeft: 6 }}>[SAMPLE]</span>
        )}
      </div>
    </div>
  );
}
