# Plan: kospi-v1.4.0-stock-price-cohort

> 종목 가격 기반 코호트 상태 판정 + Beta 증폭 시뮬레이션 — 반대매매 현실 반영

## 1. 배경 (Problem Statement)

### 현재 모델의 핵심 괴리
v1.3.0에서 종목별 가중 코호트(StockCohortManager)를 도입했으나, **상태 판정(status)이 여전히 KOSPI 지수 기준**으로 이루어짐.

**실제 사례 (2026-03-03 → 03-04)**:
- 2/26 삼성전자 ~22만원대 진입 코호트 존재
- 3/3: KOSPI -7.25%, **삼성전자 -10%+** (개별주는 지수보다 크게 하락)
- 담보비율 (삼성 기준): `(198,000/220,000) / 0.60 ≈ 1.50` → A군 maintenance(1.40) 근접, 추가 하락 시 즉시 반대매매
- **실제**: 3/4 프리장에서 반대매매 추정 물량 대량 출회
- **모델**: KOSPI -7.25%만 반영 → 담보비율 1.55로 계산 → "주의" 판정 (현실과 괴리)

### 근본 원인
```
Cohort.status(current_kospi)          ← KOSPI 지수로 판정
Cohort.collateral_ratio(current_kospi) ← KOSPI 지수로 비율 계산
StockCohortManager.get_stock_summary(current_kospi) ← 종목 builder인데도 KOSPI 전달
```

개별주식 신용거래는 **해당 종목 가격**으로 담보비율이 결정되는데, 모델은 지수를 사용.

## 2. 목표 (Goals)

1. **종목 가격 기반 상태 판정**: 각 종목 코호트는 해당 종목 종가로 담보비율 계산
2. **Hybrid Beta 증폭**: 종목별 KOSPI 대비 7거래일 하이브리드 beta (하방 60% + 상방 40%)
3. **정규화된 트리거맵**: 충격% 입력 → 종목별 beta 적용 → **가중합이 정확히 입력 충격%과 일치**
4. **Residual 역산**: Top 10 기여분을 빼고 남은 충격을 기타 종목에 배분
5. **백테스트 검증**: 기준일 선택 → 직전 7일 beta 산출 → 시뮬 vs 실제 비교

## 3. 핵심 설계 (Key Design Decisions)

### 3-1. Cohort 확장: entry_stock_price 필드

```python
@dataclass
class Cohort:
    # 기존
    entry_kospi: float
    entry_samsung: float
    entry_hynix: float
    # 신규: 범용 종목 진입가
    entry_stock_price: float = 0  # 해당 종목 종가 (종목별 builder용)
```

### 3-2. 종목 가격 기반 status 메서드

```python
def status_by_stock(self, current_stock_price: float, margin_rate: float = 0.40) -> str:
    """종목 종가 기반 담보비율 → 상태 판정."""
    if self.entry_stock_price == 0:
        return self.status(current_stock_price, margin_rate)  # fallback to index
    ratio = (current_stock_price / self.entry_stock_price) / (1 - margin_rate)
    # 분포 기반 판정 (기존 로직 재활용)
    ...
```

### 3-3. Hybrid Beta 모델 (확정)

**파라미터**:
- 기간: **7거래일** (기준일 직전)
- 방식: **하이브리드** — 하방 60% + 상방 40%
- 필터: |KOSPI 일간수익률| > 0.1% (0% 근처 노이즈 제거)
- Clip: beta 범위 0.5 ~ 3.0
- Fallback: 하락일 ≤1일이면 단순 비율 평균으로 전환

```python
def compute_hybrid_beta(stock_returns, kospi_returns, lookback=7):
    """하이브리드 Beta: 하방 60% + 상방 40%.

    Args:
        stock_returns: [r1, r2, ...] 종목 일간 수익률 (최근 lookback일)
        kospi_returns: [r1, r2, ...] KOSPI 일간 수익률 (최근 lookback일)
    """
    downside_ratios = []
    upside_ratios = []

    for s_ret, k_ret in zip(stock_returns, kospi_returns):
        if abs(k_ret) < 0.001:  # 0.1% 필터
            continue
        ratio = s_ret / k_ret
        if k_ret < 0:
            downside_ratios.append(ratio)
        else:
            upside_ratios.append(ratio)

    # Fallback: 하락일 부족 시
    if len(downside_ratios) <= 1:
        all_ratios = downside_ratios + upside_ratios
        beta = mean(all_ratios) if all_ratios else 1.0
    else:
        down_beta = mean(downside_ratios)
        up_beta = mean(upside_ratios) if upside_ratios else down_beta
        beta = 0.6 * down_beta + 0.4 * up_beta

    return clip(beta, 0.5, 3.0)
```

### 3-4. 정규화 (대전제 보장)

**대전제**: `KOSPI 충격% = Σ(종목i 충격% × 종목i KOSPI가중치)`

```python
def normalize_shocks(raw_betas, weights, kospi_shock_pct):
    """종목별 beta를 정규화하여 가중합 = kospi_shock_pct 보장.

    1) raw_shock_i = kospi_shock_pct × beta_i
    2) raw_weighted = Σ(raw_shock_i × weight_i)  (Top 10만)
    3) normalizer = kospi_shock_pct / raw_weighted
    4) adjusted_shock_i = raw_shock_i × normalizer
    5) 검증: Σ(adjusted_shock_i × weight_i) == kospi_shock_pct ✓
    """
```

### 3-5. Residual 역산

Top 10의 정규화된 충격 기여분을 빼고, 나머지를 Residual에 배분:

```
residual_shock = (kospi_shock - Σ(top10_shock_i × top10_weight_i)) / residual_weight
```

- Top 10 가중치 합 ~85% → Residual ~15%
- 정규화 후 이미 Top 10의 가중합 = kospi_shock이므로, residual_shock = kospi_shock × (residual 보정계수)
- 실제로는 정규화 과정에서 residual도 포함하면 자동 해결

### 3-6. 백테스트 흐름 (개선)

```
사용자 입력: 기준일=2/27, 충격=-7%
    ↓
Step 1: 2/27 직전 7거래일 데이터 조회 (2/18~2/26)
    ↓
Step 2: Top 10 각 종목 hybrid beta 산출
    - 삼성: beta=1.4, 하닉: beta=1.8, 현대차: beta=0.6 ...
    ↓
Step 3: 정규화 → adjusted_shock per stock
    - 삼성: -9.1%, 하닉: -11.7%, 현대차: -3.9% ...
    - 검증: Σ(adj_shock × weight) = -7.00% ✓
    ↓
Step 4: 각 종목 코호트에 adjusted_shock 적용
    - 삼성 22만원 코호트 → 현재가 200,200원 → -9.1% → 181,982원
    - 담보비율: 181,982 / 220,000 / 0.60 = 1.38 < 1.40 → margin_call!
    ↓
Step 5: 반대매매 물량 산출 + 실제 D+1~D+5와 비교
```

### 3-7. 데이터 흐름 변경

```
[기존] process_day → entry_kospi 저장 → status(current_kospi)
[변경] process_day → entry_stock_price 저장 → status_by_stock(current_stock_price)

[기존 트리거맵] shock% → 모든 종목 동일 shock%
[변경 트리거맵] shock% → beta 정규화 → 종목별 차등 shock% → 가중합=shock%
```

## 4. 변경 범위 (Scope)

### Python Backend (kospi/scripts/)

| 파일 | 변경 | 설명 |
|------|------|------|
| `compute_models.py` | **수정** | Cohort.entry_stock_price, status_by_stock(), compute_hybrid_beta(), normalize_shocks(), StockCohortManager 개선 |
| `fetch_daily.py` | **수정** | Top 10 종목별 일간 종가 수집, timeseries에 stock_prices 포함 |
| `naver_scraper.py` | **수정** | fetch_stock_daily_prices() — yfinance batch로 Top 10 종가 시계열 |
| `export_web.py` | **수정** | STOCK_CREDIT에 beta, stock_prices, normalized_shocks 포함 |
| `constants.py` | **수정** | BETA_LOOKBACK=7, BETA_DOWNSIDE_WEIGHT=0.6, BETA_CLIP=(0.5, 3.0) |

### Frontend (web/src/simulators/kospi/)

| 파일 | 변경 | 설명 |
|------|------|------|
| `CohortAnalysis.jsx` | **수정** | StockCreditBreakdown beta 컬럼, 종목별 상태 색상, 트리거맵 종목별 차등 충격 표시 |
| `data/kospi_data.js` | **재생성** | STOCK_CREDIT 구조 변경 (betas, stock_prices, normalized_trigger_map) |
| `shared/terms.jsx` | **수정** | beta, hybrid_beta, normalized_shock 용어 추가 |

### 변경하지 않는 것
- 기존 KOSPI 기반 코호트 (Module A) — 호환성 유지, 병렬 운용
- MarketPulse.jsx (Tab A) — 변경 없음
- 기존 시뮬레이터 (Module B Loop A) — 향후 v1.5.0에서 종목별 시뮬 확장

## 5. 구현 순서 (Implementation Order)

1. **constants.py**: BETA_LOOKBACK, BETA_DOWNSIDE_WEIGHT, BETA_CLIP 상수 추가
2. **Cohort 확장**: entry_stock_price 필드 + status_by_stock() + collateral_ratio_by_stock()
3. **종목 일간 종가 수집**: fetch_stock_daily_prices() — Top 10 yfinance batch (7일+)
4. **Hybrid Beta 계산**: compute_hybrid_beta() — 하방 60% / 상방 40%, 0.1% 필터
5. **정규화 함수**: normalize_shocks() — 가중합=충격% 대전제 보장
6. **StockCohortManager 개선**: process_day에서 종목 종가→entry_stock_price, get_stock_summary에서 stock price 기반 status
7. **트리거맵 개선**: get_weighted_trigger_map()에서 종목별 beta 적용 + 정규화
8. **export_web**: STOCK_CREDIT에 betas, stock_prices, normalized_trigger_map 포함
9. **프론트엔드 UI**: beta 컬럼 + 종목별 차등 충격 표시 + 종목 가격 기반 상태 색상
10. **백테스트 검증**: 기준일 2/27, 충격 -7% → 3/3-3/4 실제와 비교

## 6. 성공 기준 (Success Criteria)

- [ ] 삼성전자 코호트가 종목 종가 기반으로 margin_call/forced_liq 판정
- [ ] KOSPI -7% 충격 시 삼성 beta=1.4 → 삼성 ~-9.1% (정규화 후)
- [ ] `Σ(종목 충격% × KOSPI가중치) = 입력 충격%` 대전제 검증 통과
- [ ] Residual 충격은 역산으로 자동 결정 (별도 beta 불필요)
- [ ] 3/4 반대매매 추정 물량과 모델 예측 방향 일치 (백테스트)
- [ ] 기존 KOSPI 기반 코호트와 병렬 비교 가능 (dual mode)
- [ ] UI에서 종목별 beta + 차등 충격% + 종목가 기반 상태 표시

## 7. 리스크 및 한계

| 리스크 | 대응 |
|--------|------|
| 개별 종목 신용잔고 데이터 없음 | 시가총액 비중 proxy 유지 (v1.3.0 동일) |
| yfinance 종가 API 불안정 | 캐시 + pykrx fallback |
| 7일 beta 노이즈 (특이일 영향) | clip(0.5, 3.0) + fallback to 단순평균 |
| 하락일 ≤1일 시 하이브리드 불가 | 자동 단순평균 전환 |
| Residual 역산 값이 비현실적 | clip + 경고 UI 표시 |
| 야간 갭 리스크 미반영 | v1.4.1에서 별도 구현 (아래 참조) |

## 8. v1.4.0 스코프 외 → v1.4.1 백로그: 야간 모니터링

> Beta 산출에 EWY를 섞으면 가정이 과다. 별도 야간 모니터링 지표로 분리.

### 야간 갭 리스크 문제
- 반대매매는 **D+1 시초가** 기준 체결 → D일 종가와 D+1 시가 사이 야간 갭이 핵심
- EWY ETF(미국장), KRX NXT(시간외) 변동이 익일 시가에 반영
- 현재 모델: D일 종가만 사용 → 야간 추가 하락 미반영

### v1.4.1 구현 예정
1. **데이터 수집**: EWY 종가 (yfinance `EWY`), KRX NXT 종가 (시간외 단일가)
2. **야간 갭 추정**: EWY 변동% → KOSPI 시가 갭 추정 계수 (별도 회귀)
3. **반대매매 경고 UI**: 현재 코호트 상태 + 갭 추정 → "내일 시초 반대매매 예상 규모"
4. **시뮬 입력 확장**: "KOSPI 충격% + 야간 추가 충격%" 이중 입력

### v1.4.0에서 EWY를 제외한 이유
- Beta는 **장중 동시 변동성**을 측정하는 것 — 야간 갭은 별개 현상
- EWY를 beta에 넣으면: 한국장 종가 → EWY 변동 → 다음날 시가 순환참조 위험
- 야간 지표는 **예측(forward-looking)** 성격 → beta(후행) 와 분리해야 깔끔
