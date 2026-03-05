import { useState, useMemo, useCallback } from "react";
import { C } from "./colors";
import {
  MARKET_DATA, CREDIT_DATA, GLOBAL_DATA, INVESTOR_FLOWS,
  SHORT_SELLING, META,
} from "./data/kospi_data";

const FONT = "'JetBrains Mono', monospace";
const PAGE_SIZE = 50;

const pctFmt = v => v != null ? `${v > 0 ? "+" : ""}${v.toFixed(2)}%` : "—";
const pctColor = v => v > 0 ? C.green : v < 0 ? C.red : C.muted;
const numFmt = v => v != null ? v.toLocaleString() : "—";
const decFmt = (d = 2) => v => v != null ? v.toFixed(d) : "—";

const COLUMN_GROUPS = [
  {
    group: "시장",
    color: C.kospi,
    columns: [
      { key: "date", label: "날짜", align: "left", fmt: v => v, width: 90 },
      { key: "kospi", label: "KOSPI", align: "right", fmt: numFmt },
      { key: "kospi_change_pct", label: "KOSPI%", align: "right", fmt: pctFmt, color: pctColor },
      { key: "samsung", label: "삼성전자", align: "right", fmt: numFmt },
      { key: "samsung_change_pct", label: "삼성%", align: "right", fmt: pctFmt, color: pctColor },
      { key: "hynix", label: "SK하닉", align: "right", fmt: numFmt },
      { key: "hynix_change_pct", label: "하닉%", align: "right", fmt: pctFmt, color: pctColor },
      { key: "volume", label: "거래량", align: "right", fmt: v => v != null ? (v / 1e6).toFixed(1) + "M" : "—" },
      { key: "trading_value_billion", label: "거래대금(B)", align: "right", fmt: decFmt(1) },
    ],
  },
  {
    group: "신용/예탁",
    color: "#e67e22",
    columns: [
      { key: "credit_balance_billion", label: "신용잔고(B)", align: "right", fmt: numFmt },
      { key: "deposit_billion", label: "예탁금(B)", align: "right", fmt: numFmt },
      { key: "forced_liq_billion", label: "반대매매(B)", align: "right", fmt: numFmt },
      { key: "estimated", label: "추정", align: "center", fmt: v => v ? "est" : "" },
    ],
  },
  {
    group: "투자자 수급",
    color: "#3498db",
    columns: [
      { key: "individual_billion", label: "개인(B)", align: "right", fmt: numFmt, color: pctColor },
      { key: "financial_invest_billion", label: "금투(B)", align: "right", fmt: numFmt, color: pctColor },
      { key: "retail_billion", label: "개인+금투(B)", align: "right", fmt: numFmt, color: pctColor },
      { key: "foreign_billion", label: "외국인(B)", align: "right", fmt: numFmt, color: pctColor },
      { key: "institution_billion", label: "기관(B)", align: "right", fmt: numFmt, color: pctColor },
    ],
  },
  {
    group: "글로벌",
    color: "#9b59b6",
    columns: [
      { key: "usd_krw", label: "USD/KRW", align: "right", fmt: decFmt(1) },
      { key: "wti", label: "WTI", align: "right", fmt: decFmt(2) },
      { key: "vix", label: "VIX", align: "right", fmt: decFmt(2) },
      { key: "sp500", label: "S&P500", align: "right", fmt: decFmt(1) },
    ],
  },
  {
    group: "야간 (Overnight)",
    color: "#1abc9c",
    columns: [
      { key: "ewy_close", label: "EWY", align: "right", fmt: decFmt(2) },
      { key: "ewy_change_pct", label: "EWY%", align: "right", fmt: pctFmt, color: pctColor },
      { key: "koru_close", label: "KORU", align: "right", fmt: decFmt(2) },
      { key: "koru_change_pct", label: "KORU%", align: "right", fmt: pctFmt, color: pctColor },
      { key: "sp500_change_pct", label: "SPY%", align: "right", fmt: pctFmt, color: pctColor },
    ],
  },
  {
    group: "공매도",
    color: "#e74c3c",
    columns: [
      { key: "short_billion", label: "공매도(B)", align: "right", fmt: numFmt },
      { key: "gov_ban", label: "금지", align: "center", fmt: v => v ? "BAN" : "" },
    ],
  },
];

const ALL_COLUMNS = COLUMN_GROUPS.flatMap(g => g.columns);

function PanelBox({ children, style }) {
  return (
    <div style={{
      background: C.panel, border: `1px solid ${C.border}`,
      borderRadius: 10, padding: 18, marginBottom: 14, ...style,
    }}>{children}</div>
  );
}

export default function RawDataTable() {
  const [sortKey, setSortKey] = useState("date");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(0);
  const [filterFrom, setFilterFrom] = useState("");
  const [filterTo, setFilterTo] = useState("");
  const [visibleGroups, setVisibleGroups] = useState(() =>
    Object.fromEntries(COLUMN_GROUPS.map(g => [g.group, true]))
  );

  const toggleGroup = useCallback((group) => {
    setVisibleGroups(prev => ({ ...prev, [group]: !prev[group] }));
  }, []);

  // Merge all data into flat rows
  const allRows = useMemo(() => {
    const creditMap = {};
    for (const c of CREDIT_DATA) creditMap[c.date] = c;
    const globalMap = {};
    for (const g of GLOBAL_DATA) globalMap[g.date] = g;
    const flowMap = {};
    for (const f of INVESTOR_FLOWS) flowMap[f.date] = f;
    const shortMap = {};
    for (const s of SHORT_SELLING) shortMap[s.date] = s;

    return MARKET_DATA.map(m => {
      const gl = globalMap[m.date] || {};
      const cr = creditMap[m.date] || {};
      const fl = flowMap[m.date] || {};
      const sh = shortMap[m.date] || {};
      return {
        date: m.date,
        kospi: m.kospi,
        samsung: m.samsung,
        hynix: m.hynix,
        kospi_change_pct: m.kospi_change_pct,
        samsung_change_pct: m.samsung_change_pct,
        hynix_change_pct: m.hynix_change_pct,
        volume: m.volume,
        trading_value_billion: m.trading_value_billion,
        credit_balance_billion: cr.credit_balance_billion ?? null,
        deposit_billion: cr.deposit_billion ?? null,
        forced_liq_billion: cr.forced_liq_billion ?? null,
        estimated: cr.estimated ?? false,
        individual_billion: fl.individual_billion ?? null,
        financial_invest_billion: fl.financial_invest_billion ?? null,
        retail_billion: fl.retail_billion ?? null,
        foreign_billion: fl.foreign_billion ?? null,
        institution_billion: fl.institution_billion ?? null,
        usd_krw: gl.usd_krw ?? null,
        wti: gl.wti ?? null,
        vix: gl.vix ?? null,
        sp500: gl.sp500 ?? null,
        ewy_close: gl.ewy_close ?? null,
        ewy_change_pct: gl.ewy_change_pct ?? null,
        koru_close: gl.koru_close ?? null,
        koru_change_pct: gl.koru_change_pct ?? null,
        sp500_change_pct: gl.sp500_change_pct ?? null,
        short_billion: sh.market_total_billion ?? null,
        gov_ban: sh.gov_ban ?? false,
      };
    });
  }, []);

  // Filter
  const filtered = useMemo(() => {
    let rows = allRows;
    if (filterFrom) rows = rows.filter(r => r.date >= filterFrom);
    if (filterTo) rows = rows.filter(r => r.date <= filterTo);
    return rows;
  }, [allRows, filterFrom, filterTo]);

  // Sort
  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      const va = a[sortKey], vb = b[sortKey];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === "string") return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
      return sortDir === "asc" ? va - vb : vb - va;
    });
    return arr;
  }, [filtered, sortKey, sortDir]);

  // Paginate
  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const pageRows = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const handleSort = useCallback((key) => {
    if (sortKey === key) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
    setPage(0);
  }, [sortKey]);

  // Visible columns
  const visibleColumns = useMemo(() => {
    const cols = [];
    for (const g of COLUMN_GROUPS) {
      if (g.group === "시장") {
        // 날짜는 항상 표시
        cols.push(g.columns[0]);
        if (visibleGroups[g.group]) {
          cols.push(...g.columns.slice(1));
        }
      } else if (visibleGroups[g.group]) {
        cols.push(...g.columns);
      }
    }
    return cols;
  }, [visibleGroups]);

  // CSV Download
  const downloadCSV = useCallback(() => {
    const headers = ALL_COLUMNS.map(c => c.label).join(",");
    const rows = sorted.map(row =>
      ALL_COLUMNS.map(c => {
        const v = row[c.key];
        return v != null ? String(v) : "";
      }).join(",")
    );
    const csv = [headers, ...rows].join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `kospi_raw_data_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [sorted]);

  // Data coverage stats
  const coverage = useMemo(() => {
    const total = allRows.length;
    const fields = [
      { label: "KOSPI", count: allRows.filter(r => r.kospi != null).length },
      { label: "신용잔고", count: allRows.filter(r => r.credit_balance_billion != null).length },
      { label: "예탁금", count: allRows.filter(r => r.deposit_billion != null).length },
      { label: "투자자", count: allRows.filter(r => r.individual_billion != null).length },
      { label: "EWY%", count: allRows.filter(r => r.ewy_change_pct != null).length },
      { label: "KORU%", count: allRows.filter(r => r.koru_change_pct != null).length },
    ];
    return { total, fields };
  }, [allRows]);

  return (
    <div>
      <PanelBox>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, flexWrap: "wrap", gap: 10 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: C.text, fontFamily: FONT }}>
            원시 데이터 (Raw Data) — 전체 파이프라인
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <input
              type="date" value={filterFrom} onChange={e => { setFilterFrom(e.target.value); setPage(0); }}
              style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 6, padding: "4px 8px",
                color: C.text, fontSize: 11, fontFamily: FONT }}
            />
            <span style={{ color: C.dim, fontSize: 11 }}>~</span>
            <input
              type="date" value={filterTo} onChange={e => { setFilterTo(e.target.value); setPage(0); }}
              style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 6, padding: "4px 8px",
                color: C.text, fontSize: 11, fontFamily: FONT }}
            />
            <button onClick={downloadCSV} style={{
              background: C.kospi, color: "#fff", border: "none", borderRadius: 6,
              padding: "5px 14px", fontSize: 11, fontWeight: 600, cursor: "pointer", fontFamily: FONT,
            }}>CSV 다운로드</button>
          </div>
        </div>

        {/* Coverage Stats */}
        <div style={{ display: "flex", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
          {coverage.fields.map(f => (
            <div key={f.label} style={{
              fontSize: 10, fontFamily: FONT, color: C.muted,
              background: C.bg, borderRadius: 4, padding: "3px 8px",
            }}>
              {f.label}: <span style={{ color: f.count === coverage.total ? C.green : f.count > 0 ? "#f39c12" : C.dim }}>
                {f.count}/{coverage.total}
              </span>
            </div>
          ))}
        </div>

        {/* Group Toggle */}
        <div style={{ display: "flex", gap: 4, marginBottom: 12, flexWrap: "wrap" }}>
          {COLUMN_GROUPS.map(g => (
            <button key={g.group} onClick={() => toggleGroup(g.group)} style={{
              background: visibleGroups[g.group] ? g.color + "22" : C.bg,
              color: visibleGroups[g.group] ? g.color : C.dim,
              border: `1px solid ${visibleGroups[g.group] ? g.color + "55" : C.border}`,
              borderRadius: 4, padding: "3px 10px", fontSize: 10, fontWeight: 600,
              cursor: "pointer", fontFamily: FONT, transition: "all 0.15s",
            }}>{g.group} ({g.columns.length})</button>
          ))}
        </div>

        <div style={{ fontSize: 11, color: C.muted, marginBottom: 10, fontFamily: FONT }}>
          {sorted.length}행 | 기간: {sorted.length > 0 ? `${sorted[sorted.length - 1]?.date || ""} ~ ${sorted[0]?.date || ""}` : "—"}
          {" | "}출처: {META.data_source} | 마지막: {META.last_date}
        </div>

        {/* Table */}
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11, fontFamily: FONT }}>
            <thead>
              <tr>
                {visibleColumns.map(col => (
                  <th key={col.key} onClick={() => handleSort(col.key)} style={{
                    padding: "8px 5px",
                    textAlign: col.align,
                    color: sortKey === col.key ? C.text : C.muted,
                    fontWeight: 600, fontSize: 9,
                    borderBottom: `1px solid ${C.border}`,
                    cursor: "pointer", userSelect: "none",
                    whiteSpace: "nowrap",
                    background: sortKey === col.key ? "rgba(255,255,255,0.03)" : "transparent",
                  }}>
                    {col.label}
                    {sortKey === col.key && (
                      <span style={{ marginLeft: 2, fontSize: 8 }}>
                        {sortDir === "asc" ? "\u25B2" : "\u25BC"}
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageRows.map((row, i) => (
                <tr key={row.date} style={{
                  background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.015)",
                }}>
                  {visibleColumns.map(col => {
                    const v = row[col.key];
                    const cellColor = col.color ? col.color(v) : C.text;
                    return (
                      <td key={col.key} style={{
                        padding: "5px 5px",
                        textAlign: col.align,
                        color: cellColor,
                        borderBottom: `1px solid ${C.border}22`,
                        whiteSpace: "nowrap",
                        fontSize: 10,
                      }}>
                        {col.fmt(v)}
                      </td>
                    );
                  })}
                </tr>
              ))}
              {pageRows.length === 0 && (
                <tr>
                  <td colSpan={visibleColumns.length} style={{ padding: 20, textAlign: "center", color: C.dim }}>
                    데이터가 없습니다
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{
            display: "flex", justifyContent: "center", gap: 6, marginTop: 14, alignItems: "center",
          }}>
            <button onClick={() => setPage(0)} disabled={page === 0} style={pgBtn(page === 0)}>{"<<"}</button>
            <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} style={pgBtn(page === 0)}>{"<"}</button>
            <span style={{ fontSize: 11, color: C.muted, fontFamily: FONT, padding: "0 8px" }}>
              {page + 1} / {totalPages}
            </span>
            <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} style={pgBtn(page >= totalPages - 1)}>{">"}</button>
            <button onClick={() => setPage(totalPages - 1)} disabled={page >= totalPages - 1} style={pgBtn(page >= totalPages - 1)}>{">>"}</button>
          </div>
        )}
      </PanelBox>
    </div>
  );
}

function pgBtn(disabled) {
  return {
    background: disabled ? C.bg : C.panel,
    color: disabled ? C.dim : C.text,
    border: `1px solid ${C.border}`,
    borderRadius: 4, padding: "4px 10px",
    fontSize: 11, fontFamily: "'JetBrains Mono', monospace",
    cursor: disabled ? "default" : "pointer",
    opacity: disabled ? 0.5 : 1,
  };
}
