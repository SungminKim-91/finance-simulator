# Plan: KOSPI Phase 4.1 — Real Data Source Integration

> Feature: `kospi-phase4.1-data-sources` | Version: 4.1 | Created: 2026-03-04
> Parent: `kospi-crisis` Phase 4

---

## 1. Overview

### 1.1 Purpose
Phase 4 pipeline data source migration: replace placeholder `None` values with real data from ECOS (Bank of Korea), Naver Finance, and KRX-authenticated pykrx.

### 1.2 Problem Statement
- **Credit balance / Customer deposit**: KOFIA FREESIS is Flash SPA, no API available
- **Investor flows**: pykrx broken since 2025-02-27 KRX authentication change
- **Forced liquidation**: No public API exists

### 1.3 Data Sources Confirmed

| Required Data | Source | Verification |
|--------------|--------|-------------|
| KOSPI/KOSDAQ index | ECOS 802Y001 (Daily) | Tested |
| Samsung/SK Hynix | yfinance | Existing |
| USD/KRW, VIX, WTI, SPY | yfinance | Existing |
| Foreign net buy (billion KRW) | ECOS 802Y001 `0030000` | Tested |
| Volume / Trading value | ECOS 802Y001 `0087000`/`0088000` | Tested |
| Market capitalization | ECOS 802Y001 `0183000` | Tested |
| Customer deposit (billion KRW) | Naver sise_deposit | Tested |
| Credit balance (billion KRW) | Naver sise_deposit | Tested |
| Investor flows (individual/foreign/institution) | pykrx + KRX session | Partially working |
| Forced liquidation | No public source | OLS estimation maintained |

### 1.4 Scope
- **In Scope**: ECOS API integration, Naver scraping, KRX auth + pykrx injection, fetch_daily integration
- **Out of Scope**: Alternative investor flow source (beyond pykrx), real-time streaming, Vercel deployment

---

## 2. Architecture

### 2.1 Data Flow

```
                    ┌──────────┐
                    │  .env    │
                    │ API keys │
                    └────┬─────┘
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    ▼                    ▼                    ▼
┌────────┐        ┌──────────┐        ┌────────────┐
│  ECOS  │        │  Naver   │        │ KRX + pykrx│
│ 802Y001│        │sise_dep  │        │  session   │
│ 6 items│        │ scraping │        │  injection │
└───┬────┘        └────┬─────┘        └─────┬──────┘
    │                  │                    │
    ▼                  ▼                    ▼
┌─────────────────────────────────────────────────┐
│              fetch_daily.py                      │
│   build_snapshot(yf, ecos, naver)               │
│   Priority: ECOS > yfinance | Naver > None      │
└──────────────────────┬──────────────────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
        daily/*.json      timeseries.json
              │
              ▼
     compute_models → export_web → vite build
```

### 2.2 Environment Variables
- `ECOS_API_KEY`: Bank of Korea ECOS API key
- `KRX_USER_ID` / `KRX_USER_PW`: KRX data.krx.co.kr login
- `FRED_API_KEY`: Existing (BTC model)

---

## 3. Implementation Plan

### 3.1 File Changes

| File | Action | Description |
|------|--------|-------------|
| `kospi/requirements.txt` | Modify | +python-dotenv, +PublicDataReader |
| `kospi/scripts/krx_auth.py` | **New** | KRX login session + pykrx injection |
| `kospi/scripts/ecos_fetcher.py` | **New** | ECOS 802Y001 daily fetcher |
| `kospi/scripts/naver_scraper.py` | **New** | Naver deposit/credit scraper |
| `kospi/scripts/fetch_daily.py` | Modify | Integrate 3 sources into pipeline |

### 3.2 Data Priority
1. **Indices**: ECOS > yfinance
2. **Foreign net**: pykrx > ECOS fallback
3. **Individual/Institution**: pykrx only
4. **Deposit/Credit**: Naver only
5. **Forced liquidation**: OLS estimation only

---

## 4. Acceptance Criteria

- [ ] ECOS fetcher returns 7+ days for test range
- [ ] Naver scraper returns deposit + credit for test range
- [ ] KRX session acquires JSESSIONID
- [ ] Full pipeline: 280+ days with credit/deposit non-null
- [ ] compute_models + export_web succeed
- [ ] vite build passes

---

**Status**: Completed
**Next Phase**: Phase 4.2 (Alternative investor flow source) or Phase 5 (Deploy)
