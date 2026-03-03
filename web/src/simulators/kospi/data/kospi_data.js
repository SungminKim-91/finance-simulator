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
