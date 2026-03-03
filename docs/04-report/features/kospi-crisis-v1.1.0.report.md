# KOSPI Crisis Detector v1.1.0 완성 보고서

> **Summary**: Phase 2 UX 전면 개선 — 한글화, 단위 통일, FX 제거, 시뮬레이터 간소화, TradingView volume 차트
>
> **Created**: 2026-03-04
> **Status**: Completed

---

## 1. 개요 (Overview)

### 1.1 기능명
**KOSPI Crisis Detector v1.1.0 — Phase 2 Cohort & Forced Liquidation UX 전면 개선**

### 1.2 기간
- **Phase 2 초기 구현**: 2026-03-04 (v1.0.3 — kospi-crisis-phase2 PDCA)
- **UX 리뷰 & 개선**: 2026-03-04
- **v1.1.0 완성**: 2026-03-04

### 1.3 목표
Phase 2 첫 구현 후 5라운드 사용자 피드백을 반영하여 초보자 친화적 대시보드 완성:
1. 용어 오류 수정 (반대매매 130% 고정 → 증권사별 상이 120~140%)
2. FX(환율) 예측 완전 제거 (정부 개입 변수로 노이즈 과다)
3. 트리거맵 한글화 + 자기설명적 헤더
4. 시뮬레이터 Loop A 고정 + 외국인 매도 제거
5. 단위 통일 (십억원/B → 조·억원)
6. 전체 폰트 크기 증가
7. TradingView volume 스타일 차트 (반대매매 하단 30%)

---

## 2. 구현 범위 (Implementation Scope)

### 2.1 수정 파일

| 파일 | 변경량 | 주요 변경 |
|------|:------:|----------|
| `shared/terms.jsx` | +71줄 | TERM 6개 추가, 3개 수정, fmtBillion 헬퍼, TermHint 컴포넌트 |
| `CohortAnalysis.jsx` | 533→703줄 | 전면 리뉴얼: 3 섹션 한글화·단위통일·UX 개선 |

### 2.2 변경되지 않은 파일
- `data/kospi_data.js` — Phase 2 초기 구현에서 이미 COHORT_DATA 포함, v1.1.0에서 변경 없음
- `KospiApp.jsx` — Tab B 라우팅 이미 완료
- `compute_models.py` — Phase 2 초기 구현에서 완료
- `MarketPulse.jsx` — 영향 없음
- `colors.js` — 변경 없음

---

## 3. 주요 변경사항 (Key Changes)

### 3.1 용어 사전 확장 (shared/terms.jsx)

**신규 TERM 6개:**
- `shock_pct`: 하락폭 (Shock %)
- `expected_kospi`: 예상 KOSPI (Expected)
- `forced_liq`: 반대매매 — "(증권사별 상이, 약 120~140% 미만)"
- `loop_a`: 반대매매 연쇄 (Forced Liq Loop)
- `initial_shock`: 초기 충격 (Initial Shock)
- `max_rounds`: 반복 횟수 (Max Rounds)

**수정 TERM 3개:**
- `margin_call`: desc 대폭 보강 — "경고 단계. 기한 내 미충족 시 반대매매(강제 청산)로 전환. 곧 반대매매될 수 있는 잠재적 위험 규모"
- `collateral_ratio`: 마진콜→반대매매 순서 명시
- `forced_liq` (신규): 증권사별 상이 120~140% 범위 명시

**신규 헬퍼:**
- `fmtBillion(v)`: 십억원 raw → 조원/억원 표시 변환

**신규 컴포넌트:**
- `TermHint`: 테이블 헤더용 "?" hover tooltip (범용, CohortAnalysis에서는 overflow 이슈로 미사용)

### 3.2 Section 1: 코호트 분포 차트

| 항목 | 변경 전 | 변경 후 |
|------|--------|--------|
| Tooltip 커서 | 하얀 박스 | `cursor={false}` — 박스 제거 |
| 잔고 라벨 | `{amount}B` | `fmtBillion(amount)` (조원/억원) |
| Tooltip 단위 | 십억원 | 조원/억원 |
| 폰트 크기 | 10-13px | 11-15px |

### 3.3 Section 2: 트리거맵 리뉴얼

| 항목 | 변경 전 | 변경 후 |
|------|--------|--------|
| 가이드 박스 | 없음 | 3줄 한글 설명 추가 |
| 헤더 | 영어 (Shock, Expected KOSPI...) | 한글 자기설명적 (하락폭, 마진콜(추가 입금 요구 D+2)...) |
| FX 컬럼 | Expected FX 존재 | **완전 삭제** |
| hover 설명 | TermHint "?" (작동 안 함) | 삭제 → 헤더 자체에 설명 포함 |
| 단위 | `(v/1000).toFixed(1) 조` | `fmtBillion()` 통일 |
| 폰트 크기 | 10-11px | 12px |

### 3.4 Section 3: 시뮬레이터 전면 리뉴얼

| 항목 | 변경 전 | 변경 후 |
|------|--------|--------|
| 가이드 박스 | 없음 | 반대매매 연쇄 개념 + 외국인 매도 면책 |
| Loop Mode | A/B/AB 토글 | **A 고정** (토글 제거) |
| 컨트롤 라벨 | 영어 | 한글(영어) — "초기 충격 (Initial Shock)" |
| 시나리오 프리셋 | 없음 | 3버튼: "소폭 조정 -5%" / "급락 -15%" / "대폭락 -30%" |
| 흡수율 | 보수적/중립/낙관/직접 | **"자동 (Auto)"** 추가 + 보수적/중립/낙관/직접 |
| Auto 흡수율 | 미구현 | 최근 5일 개인+금투 매수 비율 기반 자동 산출 |
| 차트 Bar | 전체 높이 | TradingView volume 스타일 (하단 30%) |
| 차트 Line | strokeWidth 2 | strokeWidth 2.5, dot r=4 (protagonist) |
| 결과 카드 | 영어 (Final KOSPI, FX...) | 한글 (최종 KOSPI, 총 하락폭, 수렴 라운드) |
| 결과 FX | Final FX 카드 | **삭제** |
| 결과 테이블 | 영어 헤더 + B/T 단위 | 한글 헤더 + fmtBillion() |
| 외국인 매도 | Foreign Sell 컬럼 | **삭제** |
| 폰트 크기 | 9-12px | 11-15px |

### 3.5 Auto 흡수율 구현 (설계문서 반영)

```js
const autoAbsorption = useMemo(() => {
  const recentFlows = INVESTOR_FLOWS.slice(-5);
  const avgRetailBuy = recentFlows.reduce(
    (s, f) => s + Math.max(0, f.retail_billion), 0
  ) / recentFlows.length;
  const tradingValue = MARKET_DATA.slice(-5).reduce(
    (s, d) => s + d.trading_value_billion, 0
  ) / 5;
  const buyRatio = tradingValue > 0 ? avgRetailBuy / tradingValue : 0;
  let absorption = Math.max(0.1, Math.min(0.9, buyRatio * 2));
  const lastShort = SHORT_SELLING[SHORT_SELLING.length - 1];
  if (lastShort?.gov_ban) absorption = Math.max(0.6, absorption);
  return +absorption.toFixed(2);
}, []);
```

**데이터 소스**: INVESTOR_FLOWS (retail_billion), MARKET_DATA (trading_value_billion), SHORT_SELLING (gov_ban)

### 3.6 TradingView Volume 스타일 차트

```jsx
// 반대매매 Bar: 하단 30% (Y축 domain 3.3배 확대)
<YAxis yAxisId="right" orientation="right" hide
  domain={[0, (dataMax) => Math.max(Math.ceil(dataMax * 3.3), 1)]} />
<Bar yAxisId="right" dataKey="forced_liq" fill={C.danger} opacity={0.35} />

// KOSPI Line: protagonist (위에 렌더링)
<Line yAxisId="left" dataKey="price" stroke={C.kospi} strokeWidth={2.5}
  dot={{ r: 4, fill: C.kospi }} />
```

---

## 4. 삭제 항목 (Removed Features)

| 항목 | 위치 | 삭제 사유 |
|------|------|----------|
| expected_fx 컬럼 | 트리거맵 | 정부 개입 변수로 예측 노이즈 과다 |
| Loop B (환율 연쇄) | 시뮬레이터 | FX 제거에 따른 연쇄 삭제 |
| Loop A+B Combined | 시뮬레이터 | Loop A 단독 운영 |
| TermHint 사용 | 트리거맵 헤더 | overflow:auto 컨테이너에서 tooltip 클리핑 |
| Foreign Sell | 결과 카드/테이블 | FX 제거에 따라 무의미 |
| Final FX 카드 | 시뮬레이션 결과 | FX 완전 제거 |
| expected_fx TERM | terms.jsx | 미추가 (불필요) |
| loop_b TERM | terms.jsx | 미추가 (불필요) |

---

## 5. 사용자 피드백 대응 기록

| # | 피드백 | 대응 | 라운드 |
|---|--------|------|:------:|
| 1 | 반대매매 130% 고정 표기 오류 | desc에 "증권사별 상이 120~140%" 명시 | R1 |
| 2 | 트리거맵/시뮬레이터에서 FX 제거 | expected_fx 컬럼·TERM·결과 전부 삭제 | R1 |
| 3 | 마진콜 vs 반대매매 차이 명확화 | margin_call desc 보강, 트리거맵 헤더에 "(추가 입금 요구 D+2)" | R1 |
| 4 | 트리거맵 헤더 중복 표기 | TermLabel 사용 → TermHint 변경 → 자기설명적 텍스트로 최종 해결 | R1→R2 |
| 5 | 연쇄모드 A 고정, A+B 삭제 | loopMode="A" 하드코딩, Loop B/AB 토글 제거 | R1 |
| 6 | 외국인 매도 제거 + 면책 설명 | 가이드 박스에 면책 문구, 결과에서 foreign_sell 삭제 | R1 |
| 7 | TermHint hover 안 됨 | overflow:auto 클리핑 이슈 → TermHint 제거, 헤더 자기설명적 | R2 |
| 8 | 폰트 크기 전체 증가 | 모든 컴포넌트 1-2px 증가 (9→11, 10→12, 13→15 등) | R2 |
| 9 | 반대매매 Bar가 KOSPI Line 압도 | TradingView volume 스타일 (하단 30%, opacity 0.35) | R3 |

---

## 6. Gap 분석 결과

### 6.1 Phase 2 초기 구현 (v1.0.3 기준)
- **Match Rate**: 98.9% (94 항목 중 93 match, 1 intentional change)
- **Status**: PASS

### 6.2 v1.1.0 UX 개선
- Plan 대비 구현 완전 일치
- 5라운드 피드백 9건 전부 반영
- 빌드 에러 없음

---

## 7. 성과 지표 (Metrics)

### 7.1 구현 규모

| 항목 | 수치 |
|------|:----:|
| 수정 파일 수 | 2 |
| terms.jsx 추가 줄 | +71 |
| CohortAnalysis.jsx 변경 | 533→703줄 (전면 리뉴얼) |
| 신규 TERM 항목 | 6개 |
| 수정 TERM 항목 | 3개 |
| 신규 헬퍼 함수 | 1개 (fmtBillion) |
| 신규 컴포넌트 | 1개 (TermHint) |
| 삭제 기능 | 8개 (FX 관련 전부) |

### 7.2 UX 개선 지표

| 개선 항목 | 효과 |
|-----------|------|
| 한글화 | 영어 전용 → 한글(영어) 이중 표기로 초보자 접근성 대폭 향상 |
| 단위 통일 | B/십억원 혼재 → 조원/억원 통일로 직관성 향상 |
| 가이드 박스 | 3개 섹션 모두 한글 개념 설명 추가 |
| 시나리오 프리셋 | 슬라이더만 → 3개 원클릭 프리셋으로 진입장벽 감소 |
| Auto 흡수율 | 수동 입력 → 데이터 기반 자동 계산 (설계문서 반영) |
| TradingView volume | 반대매매 Bar 압도 → KOSPI Line protagonist 차트 |
| 폰트 증가 | 전체 1-2px 증가로 가독성 향상 |

---

## 8. 기술적 검토

### 8.1 긍정적 관찰

| 항목 | 설명 |
|------|------|
| 엔진 보존 | Loop B/AB 엔진 코드 삭제 없이 UI만 비활성화 → 향후 재활성화 용이 |
| 데이터 재사용 | INVESTOR_FLOWS, MARKET_DATA, SHORT_SELLING 기존 export 활용 |
| 패턴 일관성 | PanelBox, SectionTitle, ToggleGroup 등 MarketPulse 패턴 계승 |
| 단위 헬퍼 | fmtBillion()을 shared/terms.jsx에 배치 → 향후 다른 탭에서도 재사용 |

### 8.2 주의 사항

| 항목 | 현황 | 권장 |
|------|------|------|
| TermHint 미사용 | 코드는 terms.jsx에 존재하나 CohortAnalysis에서 미사용 | 향후 다른 컴포넌트에서 활용 가능, 유지 |
| FX 데이터 잔존 | kospi_data.js에 expected_fx 필드 존재 | UI에서만 미표시, 데이터 계산은 유지 |
| CohortAnalysis 크기 | 703줄 | Phase 3에서 컴포넌트 분리 검토 |

---

## 9. 버전 히스토리

| 버전 | 날짜 | 변경사항 | 상태 |
|------|------|---------|------|
| v1.0.0 | 2026-02 | Phase 1 Market Pulse 초기 구현 | Archived |
| v1.0.1 | 2026-03-01 | Y축 줌 UX 개편, 용어 사전 추가 | Completed |
| v1.0.2 | 2026-03-03 | 차트 가독성 전면 개선, DateRangeControl 통합 | Completed |
| v1.1.0 | 2026-03-04 | **Phase 2 UX 전면 개선** | **Completed (현재)** |

---

## 10. 관련 문서

| 문서 | 경로 |
|------|------|
| Plan (v1.1.0) | `docs/01-plan/features/kospi-crisis-v1.1.0.plan.md` |
| Plan (원본) | `docs/01-plan/features/kospi-crisis.plan.md` |
| Design | `docs/02-design/features/kospi-crisis.design.md` |
| Gap Analysis (Phase 2) | `docs/03-analysis/kospi-crisis-phase2.analysis.md` |
| Report (v1.0.2) | `docs/04-report/kospi-crisis.report.md` |
| Implementation | `web/src/simulators/kospi/CohortAnalysis.jsx`, `shared/terms.jsx` |
| Project Doc | `CLAUDE.md` |

---

## 11. 결론

**KOSPI Crisis Detector v1.1.0**은 Phase 2 Cohort & Forced Liquidation의 UX를 전면 개선한 버전입니다.

- 5라운드 사용자 피드백 9건 전부 반영
- 한글화 + 단위 통일 + 가이드 박스로 초보자 접근성 대폭 향상
- FX 제거 + Loop A 고정으로 시뮬레이터 간소화 (노이즈 감소)
- Auto 흡수율 설계문서 반영 완료
- TradingView volume 스타일로 차트 가독성 해결
- 빌드 에러 없음, Tab A↔B 전환 정상

**다음 마일스톤**: Phase 3 (Crisis Score + Historical Comparison) 또는 v1.1.1 마이너 UX 피드백 반영

---

**Report Status**: COMPLETED (2026-03-04)
