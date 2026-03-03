# Plan: KOSPI Crisis Detector v1.1.0 — Phase 2 UX 개선

> Feature: `kospi-crisis` | Version: 1.1.0 | Created: 2026-03-04
> Previous: v1.0.2 (Phase 1 Market Pulse + 차트 가독성)

---

## 1. Overview

### 1.1 목적
Phase 2 (Cohort & Forced Liquidation) 첫 구현 후 사용자 UX 리뷰를 반영하여 초보자 친화적으로 전면 개선. 한글화, 단위 통일, 용어 설명 가이드, 시뮬레이터 간소화를 수행.

### 1.2 배경 (사용자 피드백 요약)
1. **코호트 차트**: hover 시 하얀 박스 과도 + 단위 불일치 (십억원/B 혼재 → 조·억원 통일 필요)
2. **트리거맵**: 영어 헤더만, 설명 없음 → 초보자 불친절
3. **시뮬레이터**: 모든 컨트롤 의미 불명, 설계문서의 Auto 흡수율 미구현
4. **용어 오류**: 반대매매 130% 고정 표기 → 증권사별 상이 (120~140%)
5. **FX 제거 요청**: 환율 예측 노이즈 과다 → 정부 개입 변수 불확실
6. **폰트 크기**: 전체적으로 너무 작음 (특히 시뮬레이터 설명)
7. **차트 가독성**: 반대매매 막대가 KOSPI 선 그래프를 압도

### 1.3 Scope
- **In Scope**: CohortAnalysis.jsx 전면 리뉴얼, shared/terms.jsx 용어·헬퍼 확장
- **Out of Scope**: MarketPulse.jsx 변경 없음, Python 백엔드 변경 없음, 신규 탭 추가 없음

---

## 2. 변경 항목

### 2.1 shared/terms.jsx — 용어 사전 확장 + 단위 헬퍼

#### A. 신규 TERM 추가 (6개)
| key | label | desc |
|-----|-------|------|
| shock_pct | 하락폭 (Shock %) | KOSPI가 현재가 대비 몇 % 하락하는 시나리오 |
| expected_kospi | 예상 KOSPI (Expected) | 해당 하락폭 적용 시 예상 KOSPI 지수 |
| forced_liq | 반대매매 (Forced Liq) | 담보유지비율 미달 시 증권사가 강제로 주식을 매도하는 것 (증권사별 상이, 약 120~140% 미만) |
| loop_a | 반대매매 연쇄 (Forced Liq Loop) | 주가하락 → 담보부족 → 강제매도 → 추가하락의 연쇄 |
| initial_shock | 초기 충격 (Initial Shock) | 시뮬레이션 시작 시 KOSPI에 가하는 최초 하락률 (%) |
| max_rounds | 반복 횟수 (Max Rounds) | 연쇄 반응이 몇 번 반복되는지. 보통 3-5회에 수렴 |

#### B. 기존 TERM 수정 (3개)
| key | 변경 내용 |
|-----|----------|
| margin_call | desc 보강: "경고 단계. 기한 내 미충족 시 반대매매로 전환. 곧 반대매매될 수 있는 잠재적 위험 규모" |
| forced_liq_billion | desc 유지 (Market Pulse용) |
| collateral_ratio | desc에 마진콜→반대매매 순서 명시 |

#### C. fmtBillion 헬퍼 함수 (신규 export)
```js
export function fmtBillion(v) {
  if (v >= 1000) return `${(v / 1000).toFixed(1)}조원`;
  if (v > 0) return `${Math.round(v * 10).toLocaleString()}억원`;
  return "-";
}
```

#### D. TermHint 컴포넌트 (신규)
테이블 헤더용 "?" 아이콘 + hover tooltip. 단, CohortAnalysis에서는 overflow 이슈로 미사용 → 자기설명적 헤더로 대체.

---

### 2.2 CohortAnalysis.jsx — Section 1 (코호트 분포)

#### A. Tooltip 하얀 박스 제거
```jsx
<Tooltip content={<CohortTooltip />} cursor={false} wrapperStyle={{ outline: "none" }} />
```

#### B. 단위 통일 (십억원/B → 조·억원)
- CohortBarLabel: `fmtBillion(entry.amount)` 사용
- CohortTooltip: `fmtBillion(d.amount)` 사용
- 요약 카드: `fmtBillion()` 통일

---

### 2.3 CohortAnalysis.jsx — Section 2 (트리거맵) 리뉴얼

#### A. 가이드 박스 추가
트리거 맵 개념 설명 박스 (한글, 3줄 요약)

#### B. 테이블 헤더 한글화 (자기설명적)
| 기존 (영어) | 변경 |
|------------|------|
| Shock | 하락폭 |
| Expected KOSPI | 예상 KOSPI |
| Expected FX | **삭제** |
| Margin Call | 마진콜 (추가 입금 요구 D+2) |
| Forced Liq. | 반대매매 (강제 청산) |

#### C. FX 컬럼 완전 제거
- expected_fx 열 삭제
- TERM에서 expected_fx 미추가

#### D. 단위 통일
모든 금액 `fmtBillion()` 사용

---

### 2.4 CohortAnalysis.jsx — Section 3 (시뮬레이터) 전면 리뉴얼

#### A. 가이드 박스 추가
- 반대매매 연쇄 개념 설명
- 외국인 매도 관련 면책: "환율·외국인 매도는 정부 개입 등 비선형 변수가 크므로 별도 시뮬레이션에서 제외"

#### B. Loop Mode 간소화
- Loop B (환율), A+B (동시) **제거** → Loop A (반대매매) 고정
- `loopMode = "A"` 하드코딩
- 엔진 코드는 보존 (향후 재활성화 가능)

#### C. 컨트롤 한글화 + 시나리오 프리셋
- **초기 충격**: 슬라이더 + 3개 프리셋 버튼 ("소폭 조정 -5%", "급락 -15%", "대폭락 -30%")
- **반복 횟수**: 슬라이더 + 안내 "보통 3~5회에 수렴합니다"
- 모든 라벨 한글(영어) 형식

#### D. Auto 흡수율 구현 (설계문서 반영)
```js
function computeAutoAbsorption(investorFlows, tradingValue, govBan) {
  const recentFlows = investorFlows.slice(-5);
  const avgRetailBuy = recentFlows.reduce(
    (s, f) => s + Math.max(0, f.retail_billion), 0
  ) / recentFlows.length;
  const buyRatio = tradingValue > 0 ? avgRetailBuy / tradingValue : 0;
  let absorption = Math.max(0.1, Math.min(0.9, buyRatio * 2));
  if (govBan) absorption = Math.max(0.6, absorption);
  return +absorption.toFixed(2);
}
```
- 데이터 소스: INVESTOR_FLOWS, MARKET_DATA, SHORT_SELLING (기존 export)
- 토글: "자동 (Auto)" / "보수적 (0.3)" / "중립 (0.5)" / "낙관 (0.7)" / "직접 입력"

#### E. 차트 TradingView Volume 스타일
- 반대매매 Bar: 하단 30% 영역 (Y축 domain 3.3배 확대)
- KOSPI Line: 상단 protagonist (strokeWidth 2.5, dot r=4)
- Bar opacity 0.35, Line 위에 렌더링

#### F. 결과 한글화
- 결과 카드: "최종 KOSPI", "총 하락폭", "수렴 라운드"
- 결과 테이블: 한글 헤더, fmtBillion() 단위

#### G. 전체 폰트 크기 증가
- SectionTitle: 13→15px
- 가이드 박스: 11→12/13px
- 요약 카드: label 9→11, value 16→18
- 테이블: 10-11→12px
- 슬라이더 라벨: 10→12px
- 버튼: 12→13px
- 하단 안내: 9→11px

---

## 3. 제거 항목

| 항목 | 사유 |
|------|------|
| expected_fx (트리거맵 컬럼) | 정부 개입 변수 과다 → 예측 노이즈 |
| Loop B (환율 연쇄) | FX 제거에 따른 연쇄 삭제 |
| Loop A+B Combined | Loop A 단독 운영 |
| TermHint (트리거맵 헤더) | overflow:auto 클리핑으로 tooltip 미노출 → 자기설명적 헤더로 대체 |
| 외국인 매도 (결과 컬럼/카드) | FX 제거에 따라 foreign_sell 삭제 |

---

## 4. 파일 변경 요약

| 파일 | 작업 |
|------|------|
| `shared/terms.jsx` | TERM 6개 추가, 3개 수정, fmtBillion 헬퍼, TermHint 컴포넌트 |
| `CohortAnalysis.jsx` | 전면 리뉴얼 (533줄 → 703줄): 3 섹션 모두 한글화·단위통일·UX 개선 |

---

## 5. 검증 기준

1. `npx vite build` — 빌드 에러 없음
2. Tab B Section 1 — 코호트 hover 시 하얀 박스 없음, 단위 조/억원
3. Tab B Section 2 — 가이드 박스 + 한글 헤더 + FX 없음
4. Tab B Section 3 — 가이드 박스, 한글 라벨, 시나리오 프리셋, Auto 흡수율, TradingView volume 차트
5. Tab A↔B 전환 시 에러 없음
