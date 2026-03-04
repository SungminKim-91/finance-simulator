/**
 * KOSPI Crisis Detector — Sample Data
 * export_web.py 실행 시 실제 데이터로 교체됨.
 *
 * @generated sample data for development
 */

// --- Helpers ---
function bizDays(start, n) {
  const dates = [];
  const d = new Date(start + "T00:00:00");
  while (dates.length < n) {
    if (d.getDay() !== 0 && d.getDay() !== 6) {
      dates.push(d.toISOString().slice(0, 10));
    }
    d.setDate(d.getDate() + 1);
  }
  return dates;
}

// Deterministic pseudo-random (mulberry32)
function mulberry32(seed) {
  return function () {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rng = mulberry32(42);

function walk(start, drift, vol, n) {
  const out = [start];
  for (let i = 1; i < n; i++) {
    out.push(out[i - 1] * (1 + drift + vol * (rng() - 0.5)));
  }
  return out;
}

// --- Generate 42 business days (~2 months) ---
const DATES = bizDays("2026-01-02", 42);
const N = DATES.length;

const kospi = walk(2580, -0.001, 0.04, N);
const kosdaq = walk(780, -0.0015, 0.035, N);
const samsung = walk(65000, -0.0012, 0.028, N);
const hynix = walk(170000, -0.0008, 0.032, N);
const usdKrw = walk(1420, 0.0008, 0.012, N);
const wti = walk(72, 0.0005, 0.025, N);
const vix = walk(18, 0.003, 0.06, N);
const sp500 = walk(5800, -0.0003, 0.015, N);
const creditBase = walk(20500, 0.002, 0.025, N);
const depositBase = walk(55000, -0.001, 0.03, N);

// Inject credit shock events: day 15 surge (+3%), day 30 plunge (-3%)
if (N > 15) creditBase[15] *= 1.03;
if (N > 30) creditBase[30] *= 0.97;
// Propagate shock forward
for (let i = 16; i < N && i <= 20; i++) creditBase[i] = creditBase[i - 1] * (1 + 0.002 + 0.025 * (rng() - 0.5));
for (let i = 31; i < N && i <= 35; i++) creditBase[i] = creditBase[i - 1] * (1 + 0.002 + 0.025 * (rng() - 0.5));

// --- Exports ---

export const MARKET_DATA = DATES.map((date, i) => ({
  date,
  kospi: Math.round(kospi[i]),
  kosdaq: Math.round(kosdaq[i]),
  samsung: Math.round(samsung[i] / 100) * 100,
  hynix: Math.round(hynix[i] / 1000) * 1000,
  kospi_change_pct:
    i > 0 ? +((kospi[i] / kospi[i - 1] - 1) * 100).toFixed(2) : 0,
  samsung_change_pct:
    i > 0 ? +((samsung[i] / samsung[i - 1] - 1) * 100).toFixed(2) : 0,
  hynix_change_pct:
    i > 0 ? +((hynix[i] / hynix[i - 1] - 1) * 100).toFixed(2) : 0,
  volume: Math.round(400000000 + rng() * 200000000),
  trading_value_billion: Math.round(8000 + rng() * 5000),
}));

export const CREDIT_DATA = DATES.map((date, i) => ({
  date,
  credit_balance_billion: Math.round(creditBase[i]),
  deposit_billion: Math.round(depositBase[i]),
  forced_liq_billion: Math.round(30 + rng() * 350),
  estimated: i >= N - 2,
}));

export const INVESTOR_FLOWS = DATES.map((date) => {
  const indiv = Math.round(-4000 + rng() * 10000);
  const finInvest = Math.round(-500 + rng() * 2000); // 금투(ETF): 개인의 ~20%
  const foreign = Math.round(-5000 + rng() * 8000);
  const noise = Math.round((rng() - 0.5) * 500);
  return {
    date,
    individual_billion: indiv,
    financial_invest_billion: finInvest,
    retail_billion: indiv + finInvest, // 개인+금투 합산
    foreign_billion: foreign,
    institution_billion: -(indiv + finInvest + foreign) + noise,
  };
});

export const GLOBAL_DATA = DATES.map((date, i) => ({
  date,
  usd_krw: +usdKrw[i].toFixed(1),
  wti: +wti[i].toFixed(2),
  vix: +vix[i].toFixed(2),
  sp500: +sp500[i].toFixed(1),
}));

export const SHORT_SELLING = DATES.map((date, i) => ({
  date,
  market_total_billion: +(rng() * 3).toFixed(2),
  gov_ban: i >= 35,
}));

// --- Cohort Data (Phase 2) ---

const MARGIN_DISTRIBUTION = { 0.40: 0.35, 0.45: 0.35, 0.50: 0.25, 0.60: 0.05 };
const MAINTENANCE_RATIO = 1.40;
const FORCED_LIQ_RATIO = 1.30;
const IMPACT_COEFFICIENT = 1.5;

function buildCohorts(mode) {
  const cohorts = []; // { entry_date, entry_kospi, amount }
  for (let i = 1; i < N; i++) {
    const delta = creditBase[i] - creditBase[i - 1];
    if (delta > 0) {
      cohorts.push({
        entry_date: DATES[i],
        entry_kospi: Math.round(kospi[i]),
        amount: Math.round(delta),
      });
    } else if (delta < 0) {
      let remaining = Math.abs(Math.round(delta));
      const order = mode === "LIFO" ? [...cohorts].reverse() : cohorts;
      for (const c of order) {
        if (remaining <= 0) break;
        const repay = Math.min(remaining, c.amount);
        c.amount -= repay;
        remaining -= repay;
      }
      // remove empty cohorts
      for (let j = cohorts.length - 1; j >= 0; j--) {
        if (cohorts[j].amount <= 0) cohorts.splice(j, 1);
      }
    }
  }
  const currentKospi = Math.round(kospi[N - 1]);
  return cohorts.map((c) => {
    const pnl_pct = +((currentKospi - c.entry_kospi) / c.entry_kospi * 100).toFixed(2);
    // weighted avg collateral ratio across margin distribution
    let weightedRatio = 0;
    for (const [mr, w] of Object.entries(MARGIN_DISTRIBUTION)) {
      weightedRatio += ((currentKospi / c.entry_kospi) / (1 - Number(mr))) * w;
    }
    const ratio = +weightedRatio.toFixed(3);
    let status;
    if (ratio >= 1.60) status = "safe";
    else if (ratio >= MAINTENANCE_RATIO) status = "watch";
    else if (ratio >= FORCED_LIQ_RATIO) status = "marginCall";
    else status = "danger";
    return { ...c, pnl_pct, collateral_ratio: ratio, status };
  });
}

function buildPriceDistribution(cohorts) {
  const bins = {};
  for (const c of cohorts) {
    const bin = Math.floor(c.entry_kospi / 100) * 100;
    const key = `${bin}-${bin + 100}`;
    if (!bins[key]) bins[key] = { range: key, bin, safe: 0, watch: 0, marginCall: 0, danger: 0 };
    bins[key][c.status] += c.amount;
  }
  return Object.values(bins).sort((a, b) => a.bin - b.bin);
}

function buildTriggerMap(currentKospi, currentFx) {
  const shocks = [-3, -5, -10, -15, -20, -30];
  return shocks.map((shock) => {
    const expected_kospi = Math.round(currentKospi * (1 + shock / 100));
    const expected_fx = Math.round(currentFx * (1 + Math.abs(shock) * 0.3 / 100));
    // estimate margin_call & forced_liq from all active cohorts (LIFO)
    let margin_call = 0;
    let forced_liq = 0;
    const cohorts = buildCohorts("LIFO");
    for (const c of cohorts) {
      for (const [mr, w] of Object.entries(MARGIN_DISTRIBUTION)) {
        const ratio = (expected_kospi / c.entry_kospi) / (1 - Number(mr));
        if (ratio < FORCED_LIQ_RATIO) forced_liq += c.amount * w;
        else if (ratio < MAINTENANCE_RATIO) margin_call += c.amount * w;
      }
    }
    return {
      shock_pct: shock,
      expected_kospi,
      expected_fx,
      margin_call_billion: Math.round(margin_call),
      forced_liq_billion: Math.round(forced_liq),
    };
  });
}

const _currentKospi = Math.round(kospi[N - 1]);
const _currentFx = +usdKrw[N - 1].toFixed(1);
const _lifoCohorts = buildCohorts("LIFO");
const _fifoCohorts = buildCohorts("FIFO");
const _avgTradingValue = Math.round(
  MARKET_DATA.reduce((s, d) => s + d.trading_value_billion, 0) / N
);

export const COHORT_DATA = {
  lifo: _lifoCohorts,
  fifo: _fifoCohorts,
  price_distribution_lifo: buildPriceDistribution(_lifoCohorts),
  price_distribution_fifo: buildPriceDistribution(_fifoCohorts),
  trigger_map: buildTriggerMap(_currentKospi, _currentFx),
  current_kospi: _currentKospi,
  current_fx: _currentFx,
  avg_daily_trading_value_billion: _avgTradingValue,
  params: {
    margin_distribution: MARGIN_DISTRIBUTION,
    maintenance_ratio: MAINTENANCE_RATIO,
    forced_liq_ratio: FORCED_LIQ_RATIO,
    impact_coefficient: IMPACT_COEFFICIENT,
    fx_sensitivity: {
      low: { threshold: 1, multiplier: 0.5 },
      mid: { threshold: 2, multiplier: 1.0 },
      high: { threshold: 3, multiplier: 1.5 },
      extreme: { threshold: Infinity, multiplier: 2.0 },
    },
  },
};

// --- Crisis Score (Phase 3) ---

function classifyScore(s) {
  if (s >= 95) return "extreme";
  if (s >= 85) return "danger";
  if (s >= 70) return "warning";
  if (s >= 50) return "caution";
  return "normal";
}

const _scoreWalk = (() => {
  const out = [55];
  for (let i = 1; i < N; i++) {
    const target = 55 + (99 - 55) * (i / (N - 1));
    const pull = (target - out[i - 1]) * 0.1;
    const noise = (rng() - 0.5) * 4;
    out.push(Math.max(50, Math.min(99, out[i - 1] + pull + noise)));
  }
  return out.map(v => +v.toFixed(1));
})();

export const CRISIS_SCORE = {
  current: 99,
  classification: "extreme",
  weights: {
    leverage_heat: 0.10, flow_concentration: 0.08, price_deviation: 0.09,
    credit_acceleration: 0.08, deposit_inflow: 0.05, vix_level: 0.06,
    volume_explosion: 0.05, forced_liq_intensity: 0.08,
    credit_deposit_ratio: 0.04, dram_cycle: 0.03,
    credit_suspension: 0.12, institutional_selling: 0.10,
    retail_exhaustion: 0.08, bull_trap: 0.04,
  },
  indicators: {
    leverage_heat: { value: 78, raw: 0.042, desc: "신용/시총" },
    flow_concentration: { value: 65, raw: 2.1, desc: "개인편중" },
    price_deviation: { value: 82, raw: 0.94, desc: "MA200 괴리" },
    credit_acceleration: { value: 71, raw: 3.2, desc: "신용 증가속도" },
    deposit_inflow: { value: 45, raw: -1.5, desc: "예탁금 변화" },
    vix_level: { value: 68, raw: 28.5, desc: "VIX" },
    volume_explosion: { value: 72, raw: 1.8, desc: "거래폭증" },
    forced_liq_intensity: { value: 80, raw: 0.032, desc: "반대매매 강도" },
    credit_deposit_ratio: { value: 55, raw: 0.27, desc: "신용/예탁" },
    dram_cycle: { value: 40, raw: 5.2, desc: "DRAM 사이클" },
    credit_suspension: { value: 95, raw: 2, desc: "신용 중단" },
    institutional_selling: { value: 92, raw: -5887, desc: "기관 순매도" },
    retail_exhaustion: { value: 98, raw: 98.6, desc: "개인 매수력 감소" },
    bull_trap: { value: 85, raw: 1, desc: "불트랩" },
  },
  history: DATES.map((d, i) => ({
    date: d,
    score: _scoreWalk[i],
    classification: classifyScore(_scoreWalk[i]),
  })),
};

// --- Scenarios (Phase 3) ---

const _probHistory = (() => {
  const logits = [[-4.0, -1.5, 0.3, -0.3, -2.5]];
  for (let i = 1; i < N; i++) {
    const prev = logits[i - 1];
    logits.push(prev.map(v => v + (rng() - 0.5) * 0.3));
  }
  return logits.map(l => {
    const exps = l.map(v => Math.exp(v));
    const sum = exps.reduce((a, b) => a + b, 0);
    const probs = exps.map(v => +(v / sum).toFixed(3));
    const diff = +(1 - probs.reduce((a, b) => a + b, 0)).toFixed(3);
    probs[2] = +(probs[2] + diff).toFixed(3);
    return probs;
  });
})();

export const SCENARIOS = {
  scenarios: [
    { id: "S1", name: "연착륙",
      desc: "소멸. 2일 -19.3%와 양립 불가",
      kospi_range: [5400, 5800], current_prob: 0.00 },
    { id: "S2", name: "방어",
      desc: "이란 전쟁 진정 + 대규모 시장 안정 조치",
      kospi_range: [5000, 5400], current_prob: 0.08 },
    { id: "S3", name: "캐스케이드",
      desc: "Loop A + Loop C 4~8주 지속, 코호트 순차 붕괴",
      kospi_range: [4300, 5000], current_prob: 0.55 },
    { id: "S4", name: "전면위기",
      desc: "전쟁 장기화 + 유가 $100+ + Loop 가속",
      kospi_range: [3200, 4300], current_prob: 0.33 },
    { id: "S5", name: "펀더멘털 붕괴",
      desc: "DRAM 마이너스 + AI capex 삭감, 실적 전제 붕괴",
      kospi_range: [2500, 3200], current_prob: 0.04 },
  ],
  probability_history: DATES.map((d, i) => ({
    date: d,
    s1: _probHistory[i][0],
    s2: _probHistory[i][1],
    s3: _probHistory[i][2],
    s4: _probHistory[i][3],
    s5: _probHistory[i][4],
  })),
  key_drivers: [
    { indicator: "institutional_selling", observed: -5887, expected: -1000,
      z_score: -3.25, direction: "supporting", scenario: "S3" },
    { indicator: "retail_exhaustion", observed: 98.6, expected: 30,
      z_score: 4.57, direction: "supporting", scenario: "S3" },
    { indicator: "forced_liq_intensity", observed: 850, expected: 500,
      z_score: 2.33, direction: "supporting", scenario: "S3" },
  ],
};

// --- Historical Comparison (Phase 3) ---

const _overlayData = (() => {
  const out = [];
  let curPct = 0;
  let chinaPct = 0;
  for (let d = 0; d <= 60; d++) {
    out.push({
      day: d,
      current_pct: +curPct.toFixed(2),
      china_2015_pct: +chinaPct.toFixed(2),
    });
    curPct += (rng() - 0.55) * 1.2;
    curPct = Math.max(-25, Math.min(3, curPct));
    if (d < 20) chinaPct += (rng() - 0.65) * 1.5;
    else if (d < 40) chinaPct += (rng() - 0.45) * 0.8;
    else chinaPct += (rng() - 0.40) * 0.6;
    chinaPct = Math.max(-25, Math.min(3, chinaPct));
  }
  return out;
})();

export const HISTORICAL = {
  cases: [
    { id: "china_2015", name: "2015 중국발 폭락", peak_date: "2015-04-27",
      peak_kospi: 2173, bottom_kospi: 1829, drop_pct: -15.8, recovery_days: 89 },
  ],
  similarities: {
    china_2015: { dtw: 0.72, cosine: 0.68, hybrid: 0.70 },
  },
  overlay: _overlayData,
  indicator_comparison: [
    { indicator: "leverage_heat", label: "신용/시총", current: 4.2, china_2015: 3.8 },
    { indicator: "flow_concentration", label: "개인편중", current: 2.1, china_2015: 1.5 },
    { indicator: "price_deviation", label: "MA200 괴리", current: 0.94, china_2015: 1.02 },
    { indicator: "credit_acceleration", label: "신용 증가속도", current: 3.2, china_2015: 4.5 },
    { indicator: "deposit_inflow", label: "예탁금 변화", current: -1.5, china_2015: -2.3 },
    { indicator: "vix_level", label: "VIX", current: 28.5, china_2015: 24.3 },
    { indicator: "volume_explosion", label: "거래폭증", current: 1.8, china_2015: 2.5 },
    { indicator: "forced_liq_intensity", label: "반대매매 강도", current: 3.2, china_2015: 2.8 },
    { indicator: "credit_deposit_ratio", label: "신용/예탁", current: 0.27, china_2015: 0.22 },
    { indicator: "dram_cycle", label: "DRAM 사이클", current: 5.2, china_2015: -3.1 },
    { indicator: "credit_suspension", label: "신용 중단", current: 2, china_2015: 0 },
    { indicator: "institutional_selling", label: "기관 순매도", current: -5887, china_2015: -1200 },
    { indicator: "retail_exhaustion", label: "개인 매수력 감소", current: 98.6, china_2015: 45.0 },
    { indicator: "bull_trap", label: "불트랩", current: 1, china_2015: 0 },
  ],
};

// --- Defense Walls (v1.4) ---

export const DEFENSE_WALLS = [
  { id: "wall1", name: "개인 매수", status: "collapsed",
    detail: "792억/5.8조 = 98.6% 감소", capacity: 0.01 },
  { id: "wall2", name: "연기금/기관", status: "weakened",
    detail: "기관 합산 매도 전환 (-5,887억)", capacity: 0.35 },
  { id: "wall3", name: "한은 FX 개입", status: "active",
    detail: "1,475 방어 성공", capacity: 0.80 },
  { id: "wall4", name: "US 통화스왑", status: "destroyed",
    detail: "3/4 거절 확인", capacity: 0.00 },
  { id: "wall5", name: "IMF 지원", status: "standby",
    detail: "미발동 (외환보유고 $4,000억+)", capacity: 1.00 },
];

// --- Loop Status (v1.4) ---

export const LOOP_STATUS = {
  loop_a: {
    status: "active", name: "반대매매 캐스케이드",
    wave1: { time: "08:00-09:00", desc: "프리마켓 마진콜" },
    wave2: { time: "12:00-14:00", desc: "추가담보 마감 후 강제매도" },
    estimated_volume_billion: 500,
  },
  loop_c: {
    status: "active", name: "펀드 환매 캐스케이드",
    delay: "T+1~T+3",
    desc: "기관 -5,887억 중 환매 매도 추정 3,000~4,000억",
    estimated_volume_billion: 3500,
    confidence: "low",
  },
};

export const EVENTS = [
  {
    date: "2026-03-02",
    type: "market",
    desc: "KOSPI 2400 이탈, 서킷브레이커 발동 경고",
  },
  {
    date: "2026-02-28",
    type: "government_action",
    desc: "금융위원회 공매도 전면 금지 재발동 검토",
  },
  {
    date: "2026-02-25",
    type: "global",
    desc: "미국 2월 CPI 예상치 상회, Fed 금리 인하 불확실",
  },
  {
    date: "2026-02-20",
    type: "flow",
    desc: "외국인 20거래일 연속 순매도 (누적 -4.2조원)",
  },
  {
    date: "2026-02-14",
    type: "credit",
    desc: "신용잔고 21조 돌파, 2021년 이후 최대",
  },
  {
    date: "2026-02-10",
    type: "market",
    desc: "삼성전자 6만원 붕괴, 52주 신저가",
  },
  {
    date: "2026-02-05",
    type: "global",
    desc: "중국 CSI 300 -3.2%, 아시아 동반 하락",
  },
  {
    date: "2026-01-28",
    type: "government_action",
    desc: "한은 기준금리 25bp 인하 (3.25% -> 3.00%)",
  },
  {
    date: "2026-01-20",
    type: "flow",
    desc: "기관 프로그램 매도 5000억 이상",
  },
  {
    date: "2026-01-10",
    type: "market",
    desc: "KOSPI 연초 2580 출발, 전년 대비 -8%",
  },
];

export const META = {
  last_updated: "2026-03-03T16:35:00+09:00",
  last_date: "2026-03-03",
  data_source: "sample",
  data_quality: {
    credit_estimated_days: 2,
    missing_fields: ["dram_spot"],
  },
};
