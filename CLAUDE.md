# Finance Simulator — BTC Liquidity Prediction Model

> v1.0.0 | BTC 가격 방향성 선행 예측 시뮬레이터

## Project Overview
글로벌 유동성 지표(5개 변수)를 기반으로 BTC 가격의 큰 흐름을 5-9개월 선행 예측하는 모델.
실제 데이터 크롤링 파이프라인 포함.

## v1.0.0 Results
- **In-Sample Correlation**: 0.6176
- **Optimal Lag**: 9개월
- **Walk-Forward OOS**: 9 windows, mean=0.246
- **Best Weights**: NL=0.5, GM2=0.0, SOFR=-4.0, HY=-0.5, CME=0.0
- **Design-Implementation Match Rate**: 93% (PASS)

## Core Variables (v4.0)
1. **NL Level** — Net Liquidity (WALCL - TGA - RRP), 미국 유동성
2. **GM2 Residual** — 미국 외 글로벌 유동성 (직교화)
3. **SOFR Binary** — 위기 감지 (SOFR - IORB > 20bps)
4. **HY Spread Level** — 신용 스프레드, 위험선호 (FRED BAMLH0A0HYM2)
5. **CME Basis** — 기관 포지셔닝 (선물-현물 연율화)

## Key Design Principles
- BTC를 target으로 직접 최적화 금지 — 유동성 지수 독립 구성 → 사후 검증
- 파형 매칭: `corr(score, log₁₀(BTC))` 최대화
- 12m MA detrend → z-score 표준화
- 과적합 방지: 변수 수 × 15 <= 데이터 포인트

## Tech Stack
Python 3.12 | uv (venv) | pandas | fredapi | yfinance | scipy | matplotlib | SQLite

## Data Sources
- FRED API: WALCL, RRP, SOFR, IORB, M2/M3 시리즈, HY Spread
- Treasury Fiscal Data API: TGA (키 불필요, dual filter for 2021-10 변경)
- Yahoo Finance: DXY, BTC, CME BTC Futures
- CoinGecko/Binance: BTC 현물 fallback

## CLI
```bash
python main.py fetch       # 데이터 수집만
python main.py optimize    # 전체 최적화 (fetch + calc + grid search + walk-forward)
python main.py run         # 주간 업데이트 (저장된 가중치 사용)
python main.py score       # 현재 Score만 계산
python main.py visualize   # 차트 생성
python main.py status      # 모델 상태 확인
```

## Key Implementation Notes
- FRED EU_M2/JP_M2: 원본 M2 단종 → M3 대체 (MABMM301EZM189S, MABMM301JPM189S)
- TGA: 2021-10 기점 account_type 명칭 변경 → dual filter 대응
- 날짜 정규화: 모든 변수 MonthEnd(0)로 통일 후 merge (FRED 월초 vs resample 월말 불일치 방지)
- 캐시: 24h 만료, 만료 캐시 fallback 지원

## PDCA Status
- **Phase**: Completed (v1.0.0)
- **Match Rate**: 93%
- **Documents**: docs/01-plan/, docs/02-design/, docs/03-analysis/, docs/04-report/
