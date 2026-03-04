# Design: KOSPI Phase 4.1 — Real Data Source Integration

> Feature: `kospi-phase4.1-data-sources` | Version: 4.1 | Created: 2026-03-04
> Plan Reference: `docs/01-plan/features/kospi-phase4.1-data-sources.plan.md`

---

## 1. Module Design

### 1.1 `kospi/scripts/ecos_fetcher.py`

ECOS 802Y001 table daily stock market data fetcher.

**API Endpoint**: `https://ecos.bok.or.kr/api/StatisticSearch/{KEY}/json/kr/{start_idx}/{end_idx}/802Y001/D/{start}/{end}/{item_code}`

**Item Codes**:

| Code | Field | Raw Unit | Stored Unit |
|------|-------|----------|-------------|
| `0001000` | kospi | - | float (index) |
| `0089000` | kosdaq | - | float (index) |
| `0030000` | foreign_net_million | million KRW | billion KRW (/1000) |
| `0087000` | volume_thousand | 1000 shares | 1000 shares |
| `0088000` | trading_value_million | million KRW | billion KRW (/1000) |
| `0183000` | market_cap_billion | billion KRW | billion KRW |

**Pagination**: 1000 rows per page, auto-paginate until total exhausted.
**Rate limit**: 0.2s between items, 0.3s between item code batches.

```python
def fetch_ecos_daily(start: str, end: str) -> dict[str, dict]:
    # Returns {"2025-02-20": {"kospi": 2654.06, "foreign_net_billion": -2.88, ...}}
```

### 1.2 `kospi/scripts/naver_scraper.py`

Naver Finance sise_deposit page scraper for customer deposit and credit balance.

**URL**: `https://finance.naver.com/sise/sise_deposit.naver?page={n}`
**Encoding**: euc-kr
**Unit**: billion KRW (raw: billion KRW, stored as-is after /10 conversion from raw)
**Date format**: 2-digit year (`26.02.27`) parsed with `%y.%m.%d`

**Table structure** (11 columns):
| Col | Field |
|-----|-------|
| 0 | Date |
| 1 | Customer deposit (billion KRW) |
| 2 | Deposit change |
| 3 | Credit balance (billion KRW) |
| 4 | Credit change |
| 5-10 | Fund data (equity, mixed, bond) |

**Pagination**: Reverse chronological (newest first). Stop when date < start.
**Rate limit**: 0.3s between pages.

```python
def fetch_naver_deposit_credit(start: str, end: str) -> dict[str, dict]:
    # Returns {"2026-02-27": {"deposit_billion": 118748.8, "credit_balance_billion": 32188.1}}
```

### 1.3 `kospi/scripts/krx_auth.py`

KRX login session manager + pykrx HTTP monkey-patch.

**Login flow**:
1. GET login page (cookie acquisition)
2. GET SSO JSP
3. POST login credentials
4. Handle CD011 duplicate login (skipDup=Y)
5. Verify via StatusCheck (CD001 or JSESSIONID)

**pykrx injection**: Replace `webio.Post.read` and `webio.Get.read` with authenticated session methods that return raw `requests.Response` objects (matching pykrx's expected return type).

### 1.4 `kospi/scripts/fetch_daily.py` Modifications

**New functions**:
- `_init_env()`: Load `.env` from project root parent
- `_init_krx()`: KRX login + pykrx session injection (graceful failure)

**Modified `build_snapshot()`**:
- New parameters: `ecos_data`, `naver_data`
- Priority: ECOS kospi/kosdaq > yfinance
- ECOS foreign_net as pykrx fallback
- Naver credit/deposit fills previously-null fields
- Market cap from ECOS (billion -> trillion conversion)

**Modified `run_range()`**:
- 5-step pipeline: env → KRX → ECOS batch → Naver batch → yfinance batch → per-day merge
- Progress reporting with step numbers

---

## 2. Data Schema

### 2.1 Snapshot Enrichment

```json
{
  "market": {
    "kospi": {
      "close": 6244.13,          // ECOS (was: yfinance)
      "volume": 116606000,        // ECOS volume_thousand * 1000
      "trading_value_billion": 549.39  // NEW: from ECOS
    },
    "kospi_market_cap_trillion": 51463.73  // NEW: from ECOS
  },
  "credit": {
    "total_balance_billion": 32188.1,   // NEW: from Naver (was: null)
    "estimated": false
  },
  "deposit": {
    "customer_deposit_billion": 118748.8, // NEW: from Naver (was: null)
    "estimated": false
  },
  "investor_flows": {
    "market_total": {
      "foreign_billion": -70.8    // ECOS fallback when pykrx fails
    }
  }
}
```

---

## 3. Error Handling

| Scenario | Behavior |
|----------|----------|
| ECOS_API_KEY missing | Skip ECOS, use yfinance only |
| KRX login failure | Skip pykrx session injection, use raw pykrx |
| Naver page timeout | Break pagination, return partial results |
| pykrx returns empty | Use ECOS foreign_net as fallback |
| yfinance empty | Continue with ECOS data only |

---

**Status**: Implemented
