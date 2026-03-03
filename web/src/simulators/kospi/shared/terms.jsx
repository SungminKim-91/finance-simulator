import { useState } from "react";
import { C } from "../colors";

const FONT = "'JetBrains Mono', monospace";

/* ── Korean Term Dictionary ── */
export const TERM = {
  /* Market Pulse terms */
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
  retail_billion: {
    label: "개인+금투 (Retail)",
    desc: "개인투자자 + 금융투자(ETF) 합산 순매수/순매도 금액",
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
  cum_retail: {
    label: "개인+금투 누적 (Cum. Retail)",
    desc: "개인+금투 합산 누적 순매수 금액",
  },
  cum_foreign: {
    label: "외국인 누적 (Cum. Foreign)",
    desc: "외국인투자자 누적 순매수 금액",
  },
  cum_institution: {
    label: "기관 누적 (Cum. Institution)",
    desc: "기관투자자 누적 순매수 금액",
  },

  /* Cohort & Forced Liquidation terms */
  cohort: {
    label: "코호트 (Cohort)",
    desc: "같은 시점에 신용매수한 투자자 그룹. 진입 시점별 손익·위험도가 다름",
  },
  collateral_ratio: {
    label: "담보비율 (Collateral Ratio)",
    desc: "담보가치 ÷ 대출금. 유지비율 미달 시 마진콜 → 반대매매 순서로 진행",
  },
  margin_call: {
    label: "마진콜 (Margin Call)",
    desc: "담보유지비율 미달 시 증권사가 추가 담보 입금을 요구하는 경고 단계. 기한 내 미충족 시 반대매매(강제 청산)로 전환. 곧 반대매매될 수 있는 잠재적 위험 규모",
  },
  status_safe: {
    label: "안전 (Safe)",
    desc: "담보비율 160% 이상. 충분한 여유",
  },
  status_watch: {
    label: "주의 (Watch)",
    desc: "담보비율 140-160%. 추가 하락 시 마진콜 가능",
  },
  status_marginCall: {
    label: "마진콜 (Margin Call)",
    desc: "담보비율 130-140%. 추가 담보 입금 필요",
  },
  status_danger: {
    label: "위험 (Danger)",
    desc: "담보비율 130% 미만. 반대매매 임박 또는 진행 중",
  },
  trigger_map: {
    label: "트리거 맵 (Trigger Map)",
    desc: "KOSPI 하락폭별 예상 마진콜·반대매매 규모 표",
  },
  absorption_rate: {
    label: "시장흡수율 (Absorption)",
    desc: "반대매매 물량 중 시장이 충격 없이 소화하는 비율 (0=전량충격, 1=완전흡수)",
  },
  fx_loop: {
    label: "환율 루프 (FX Loop)",
    desc: "주가 하락 → 환율 상승 → 외국인 매도 → 추가 하락의 악순환",
  },

  /* Trigger Map terms */
  shock_pct: {
    label: "하락폭 (Shock %)",
    desc: "KOSPI가 현재가 대비 몇 % 하락하는 시나리오",
  },
  expected_kospi: {
    label: "예상 KOSPI (Expected)",
    desc: "해당 하락폭 적용 시 예상 KOSPI 지수",
  },
  /* Simulator terms */
  forced_liq: {
    label: "반대매매 (Forced Liq)",
    desc: "담보유지비율 미달 시 증권사가 강제로 주식을 매도하는 것 (증권사별 상이, 약 120~140% 미만)",
  },
  loop_a: {
    label: "반대매매 연쇄 (Forced Liq Loop)",
    desc: "주가하락 → 담보부족 → 강제매도 → 추가하락의 연쇄",
  },
  initial_shock: {
    label: "초기 충격 (Initial Shock)",
    desc: "시뮬레이션 시작 시 KOSPI에 가하는 최초 하락률 (%)",
  },
  max_rounds: {
    label: "반복 횟수 (Max Rounds)",
    desc: "연쇄 반응이 몇 번 반복되는지. 보통 3-5회에 수렴",
  },
};

/* ── Unit Formatter: 십억원 → 조원/억원 ── */
export function fmtBillion(v) {
  if (v >= 1000) return `${(v / 1000).toFixed(1)}조원`;
  if (v > 0) return `${Math.round(v * 10).toLocaleString()}억원`;
  return "-";
}

/* ── TermLabel with Hover Tooltip ── */
export function TermLabel({ dataKey, color }) {
  const [show, setShow] = useState(false);
  const term = TERM[dataKey];
  if (!term) return <span style={{ color, fontSize: 10 }}>{dataKey}</span>;

  return (
    <span
      style={{ position: "relative", display: "inline-block", cursor: "default" }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <span style={{ color, fontSize: 10 }}>{"\u25CF"} {term.label}</span>
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

/* ── TermHint — "?" icon with hover tooltip (for table headers) ── */
export function TermHint({ dataKey }) {
  const [show, setShow] = useState(false);
  const term = TERM[dataKey];
  if (!term) return null;
  return (
    <span
      style={{ position: "relative", display: "inline-block", cursor: "help", marginLeft: 2 }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <span style={{ color: C.dim, fontSize: 9, fontWeight: 400 }}>?</span>
      {show && (
        <div
          style={{
            position: "absolute",
            bottom: "calc(100% + 4px)",
            left: "50%",
            transform: "translateX(-50%)",
            background: "#1a1a2e",
            border: `1px solid ${C.border}`,
            borderRadius: 6,
            padding: "8px 12px",
            fontSize: 11,
            color: C.text,
            whiteSpace: "normal",
            minWidth: 200,
            maxWidth: 320,
            zIndex: 200,
            fontFamily: FONT,
            pointerEvents: "none",
            boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
            lineHeight: 1.5,
            textAlign: "left",
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: 2, color: C.text }}>{term.label}</div>
          <div style={{ color: C.muted }}>{term.desc}</div>
        </div>
      )}
    </span>
  );
}

/* ── Custom Legend ── */
export function CustomLegend({ payload }) {
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
export function CustomTooltipContent({ active, payload, label }) {
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

/* ── Tooltip Value Formatter ── */
export function fmtTooltipVal(dataKey, value) {
  if (typeof value !== "number") return value;
  const trilKeys = [
    "credit_balance_billion", "deposit_billion",
    "individual_billion", "retail_billion", "foreign_billion", "institution_billion",
    "cum_individual", "cum_retail", "cum_foreign", "cum_institution",
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
