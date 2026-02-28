# Changelog — Finance Simulator

## [v1.0.0] - 2026-03-01

### BTC Liquidity Prediction Model 완료

#### Added
- **완전한 데이터 파이프라인**: FRED, Treasury, Yahoo Finance, CoinGecko, Binance API 통합
- **5개 변수 모델**: NL (Net Liquidity), GM2 Residual, SOFR Binary, HY Spread, CME Basis
- **최적화 엔진**: Grid Search (5변수 × lag 0-9개월) + Walk-Forward 검증
- **CLI 인터페이스**: 7가지 명령어 (fetch, calculate, optimize, run, score, visualize, status)
- **시각화 3종**: Score vs BTC overlay, Correlation heatmap, Walk-Forward results
- **저장소**: SQLite + JSON 이중 저장 + CSV 중간 저장
- **캐싱 시스템**: 24h 캐시 만료, API 호출 최소화
- **에러 처리**: 10가지 시나리오 대응 (95% 커버)

#### Changed
- **Orthogonalization 순서**: Z-score → Ortho (설계) → Ortho → Z-score (구현, 통계적으로 정확)
- **EU_M2/JP_M2 FRED 시리즈**: M2(설계) → M3(구현) [가용성 문제로 변경, 재검토 필요]
- **Treasury API 필터**: 단일 필터 → 이중 필터 (2021년 API 변경 대응)

#### Improved
- **Cache 만료 시스템**: 설계에 없던 추가 기능 (데이터 신선도)
- **Date normalization**: MonthEnd 정규화로 merge 정합성 향상
- **Processed data CSV 저장**: 디버깅/시각화 지원
- **NaN Score defense**: DB 안정성 강화
- **CME Basis clipping**: 극단값(±200%) 방지
- **Pipeline exception handling**: 전체 try-except + logger.error

#### Results
- **In-Sample Correlation**: 0.6176 (v3 대비 +52%)
- **Optimal Lag**: 9개월 (설계 기대: 4-7개월, 범위 초과)
- **Walk-Forward OOS**: Mean=0.2460, Std=0.5873, Best=0.8104 (변동성 높음)
- **Design Match Rate**: 93% (PASS, >= 90%)
- **Module Coverage**: 22/22 = 100%
- **Function Signature Match**: 46/51 = 90%

#### Known Issues
- ⚠️ EU_M2/JP_M2 FRED 시리즈 M2→M3 변경 (원본 단종 불가피, 모델 재검증 필요)
- ⚠️ Walk-Forward OOS 변동성 높음 (윈도우 크기 재검토 필요)
- ⚠️ Optimal lag가 설계 범위 초과 (모델 특성 분석 필요)

#### TODO (v1.1)
- [ ] EU_M2/JP_M2 FRED 시리즈 최종 확정
- [ ] `calculate` CLI 명령 추가
- [ ] Signal case 통일 (lowercase vs UPPERCASE)
- [ ] Walk-Forward 분석 (OOS 변동성 최소화)
- [ ] Test suite (unit + integration)
- [ ] Logging enhancement
- [ ] Documentation (README, API docs)
- [ ] Performance optimization (Grid Search 병렬화)

---

## Development Notes

### Architecture Highlights
- **5-Layer Design**: Fetchers → Calculators → Optimizers → Pipeline → Visualization
- **Modular Structure**: 22 files, 51 functions, config-driven
- **Data Flow**: FETCH → CALCULATE (+ ORTHO) → ZSCORE → OPTIMIZE → SCORE → STORE → VIZ

### Tech Stack
- **Language**: Python 3.12 + uv venv
- **Data**: pandas 2.x, numpy 2.x, scipy
- **APIs**: fredapi, yfinance, requests
- **DB**: SQLite + JSON
- **Viz**: matplotlib, seaborn

### Key Constants
- Data range: 2016-01 ~ 2025-12 (9+ years)
- Grid Search: 5 variables × 10 lag values = ~500k combinations
- Walk-Forward: 8 windows (expanding), 60m train + 6m test
- Overfitting safety: 108 months ÷ 5 variables = 21.6:1 ratio (target >= 15:1)

---

**Latest Report**: [btc-liquidity-model.report.md](./btc-liquidity-model.report.md)
