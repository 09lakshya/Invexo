import React, { useState, useEffect, useCallback } from "react";
import Head from "next/head";
import Link from "next/link";
import Navbar from "../components/Navbar";
import API from "../services/api";

const HORIZONS = ["1h", "1d", "3d"];
const REGIMES = [
  { key: "", label: "All regimes" },
  { key: "trending", label: "Trending" },
  { key: "range_bound", label: "Range-bound" },
];
const BUCKETS = ["", "35-50", "50-65", "65-80", "80-95"];

function pct(v) {
  return v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${v}%`;
}

function StatTile({ label, value, sub, positive }) {
  return (
    <div className="glass" style={{ padding: "18px 20px", flex: "1 1 150px", minWidth: "150px", boxShadow: "var(--shadow-card)" }}>
      <div style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-muted)", marginBottom: "6px" }}>
        {label}
      </div>
      <div style={{ fontSize: "1.4rem", fontWeight: 800, fontFamily: "'Space Grotesk', sans-serif", color: positive === undefined ? "var(--text-primary)" : positive ? "var(--green)" : "var(--red)" }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "4px" }}>{sub}</div>}
    </div>
  );
}

// A compact hit-rate + return grid for one breakdown (overall / regime / bucket).
function BreakdownTable({ title, groups }) {
  const rows = Object.entries(groups || {});
  if (!rows.length) return null;
  return (
    <div className="glass" style={{ padding: "20px", boxShadow: "var(--shadow-card)", marginBottom: "16px" }}>
      <h3 style={{ fontSize: "0.85rem", fontWeight: 700, marginBottom: "14px", fontFamily: "'Space Grotesk', sans-serif" }}>{title}</h3>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem", minWidth: "460px" }}>
          <thead>
            <tr style={{ color: "var(--text-muted)", textAlign: "left" }}>
              <th style={{ padding: "6px 10px", fontWeight: 700 }}></th>
              {HORIZONS.map((h) => (
                <th key={h} style={{ padding: "6px 10px", fontWeight: 700, textTransform: "uppercase", fontSize: "0.68rem", letterSpacing: "0.05em" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([name, hz]) => (
              <tr key={name} style={{ borderTop: "1px solid var(--border-subtle)" }}>
                <td style={{ padding: "10px", fontWeight: 700, textTransform: "capitalize" }}>{name.replace("_", " ")}</td>
                {HORIZONS.map((h) => {
                  const cell = hz?.[h] || {};
                  const hr = cell.hit_rate;
                  const ar = cell.avg_return_pct;
                  return (
                    <td key={h} style={{ padding: "10px" }}>
                      {cell.evaluated ? (
                        <div>
                          <div style={{ fontWeight: 800, color: hr >= 50 ? "var(--green)" : "var(--red)" }}>
                            {hr}% <span style={{ fontWeight: 500, color: "var(--text-muted)", fontSize: "0.72rem" }}>hit</span>
                          </div>
                          <div style={{ fontSize: "0.72rem", color: ar > 0 ? "var(--green)" : "var(--red)" }}>
                            {pct(ar)} avg · n={cell.evaluated}
                          </div>
                        </div>
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DirBadge({ direction }) {
  const map = { long: ["var(--green)", "var(--green-dim)", "▲ Long"], short: ["var(--red)", "var(--red-dim)", "▼ Short"], neutral: ["var(--text-muted)", "var(--surface-hover)", "• Neutral"] };
  const [color, bg, label] = map[direction] || map.neutral;
  return <span style={{ padding: "3px 9px", borderRadius: "7px", fontSize: "0.7rem", fontWeight: 700, color, background: bg, whiteSpace: "nowrap" }}>{label}</span>;
}

export default function TrackRecordPage() {
  const [stats, setStats] = useState(null);
  const [list, setList] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ ticker: "", regime: "", bucket: "", start: "", end: "" });

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const load = useCallback(async () => {
    setLoading(true);
    const params = {};
    Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
    try {
      const [statsRes, listRes] = await Promise.all([
        API.get("/ledger/stats", { params }),
        API.get("/ledger/signals", { params: { ...params, limit: 100 } }),
      ]);
      setStats(statsRes.data);
      setList(listRes.data);
    } catch (e) {
      setStats(null);
      setList(null);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  const overall1d = stats?.overall?.["1d"];
  const overall3d = stats?.overall?.["3d"];
  const overall1h = stats?.overall?.["1h"];
  const hasData = stats && stats.total_signals > 0;

  const exportUrl = () => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => { if (v) params.append(k, v); });
    return `${apiBase}/ledger/export.csv?${params.toString()}`;
  };

  return (
    <>
      <Head>
        <title>Track Record | Invexo</title>
        <meta name="description" content="The consensus predictor's live, measured track record — hit rate and realized return per regime, confidence bucket and horizon." />
      </Head>

      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />
        <div className="page-wrapper" style={{ marginTop: "20px" }}>
          {/* Header */}
          <div style={{ textAlign: "center", marginBottom: "28px" }} className="animate-fadeInUp">
            <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "clamp(2rem, 5vmin, 3rem)", fontWeight: 800, letterSpacing: "-0.02em", marginBottom: "12px" }}>
              Track <span className="text-gradient">Record</span>
            </h1>
            <p style={{ color: "var(--text-muted)", fontSize: "1rem", maxWidth: "640px", margin: "0 auto" }}>
              Every signal the consensus predictor emits is logged immutably and scored against realized prices at 1-hour, 1-day and 3-day horizons. These are measured outcomes — never simulated.
            </p>
          </div>

          {/* Headline tiles */}
          <div style={{ display: "flex", gap: "14px", flexWrap: "wrap", marginBottom: "24px" }} className="animate-fadeInUp animate-delay-100">
            <StatTile label="Signals Logged" value={hasData ? stats.total_signals.toLocaleString("en-IN") : "0"} sub="immutable ledger rows" />
            <StatTile label="1-Day Hit Rate" value={overall1d?.evaluated ? `${overall1d.hit_rate}%` : "—"} sub={`${overall1d?.evaluated || 0} scored · ${pct(overall1d?.avg_return_pct)} avg`} positive={overall1d?.hit_rate >= 50} />
            <StatTile label="3-Day Hit Rate" value={overall3d?.evaluated ? `${overall3d.hit_rate}%` : "—"} sub={`${overall3d?.evaluated || 0} scored · ${pct(overall3d?.avg_return_pct)} avg`} positive={overall3d?.hit_rate >= 50} />
            <StatTile label="1-Hour Hit Rate" value={overall1h?.evaluated ? `${overall1h.hit_rate}%` : "—"} sub={`${overall1h?.evaluated || 0} scored · ${pct(overall1h?.avg_return_pct)} avg`} positive={overall1h?.hit_rate >= 50} />
          </div>

          {/* Filters */}
          <div className="glass" style={{ padding: "16px 20px", boxShadow: "var(--shadow-card)", marginBottom: "20px", display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "flex-end" }}>
            <FilterField label="Ticker">
              <input value={filters.ticker} onChange={(e) => setFilters((f) => ({ ...f, ticker: e.target.value }))} placeholder="e.g. RELIANCE" style={inputStyle} />
            </FilterField>
            <FilterField label="Regime">
              <select value={filters.regime} onChange={(e) => setFilters((f) => ({ ...f, regime: e.target.value }))} style={inputStyle}>
                {REGIMES.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
              </select>
            </FilterField>
            <FilterField label="Confidence">
              <select value={filters.bucket} onChange={(e) => setFilters((f) => ({ ...f, bucket: e.target.value }))} style={inputStyle}>
                {BUCKETS.map((b) => <option key={b} value={b}>{b || "All buckets"}</option>)}
              </select>
            </FilterField>
            <FilterField label="From">
              <input type="date" value={filters.start} onChange={(e) => setFilters((f) => ({ ...f, start: e.target.value }))} style={inputStyle} />
            </FilterField>
            <FilterField label="To">
              <input type="date" value={filters.end} onChange={(e) => setFilters((f) => ({ ...f, end: e.target.value }))} style={inputStyle} />
            </FilterField>
            <a href={exportUrl()} style={{ ...inputStyle, textDecoration: "none", color: "var(--accent)", border: "1px solid var(--accent)", background: "var(--accent-dim)", fontWeight: 700, cursor: "pointer" }}>
              Export CSV ↓
            </a>
          </div>

          {loading ? (
            <div className="glass" style={{ padding: "40px", textAlign: "center", boxShadow: "var(--shadow-card)" }}>
              <div style={{ width: "40px", height: "40px", margin: "0 auto 12px", borderRadius: "50%", border: "3px solid var(--surface-hover)", borderTopColor: "var(--accent)", animation: "spin 0.9s linear infinite" }} />
              <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Loading track record…</p>
            </div>
          ) : !hasData ? (
            <div className="glass" style={{ padding: "40px", textAlign: "center", boxShadow: "var(--shadow-card)" }}>
              <h3 style={{ fontWeight: 700, marginBottom: "8px" }}>No signals logged yet</h3>
              <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", maxWidth: "480px", margin: "0 auto" }}>
                The ledger fills as the scheduled session scans run. Outcomes appear once each horizon (1h / 1d / 3d) has elapsed and prices are available.
              </p>
            </div>
          ) : (
            <>
              {/* Breakdowns */}
              <BreakdownTable title="Overall — hit rate & avg realized return per horizon" groups={{ overall: stats.overall }} />
              <BreakdownTable title="By market regime" groups={stats.by_regime} />
              <BreakdownTable title="By confidence bucket" groups={stats.by_confidence_bucket} />

              {/* Signal table */}
              <div className="glass" style={{ padding: "20px", boxShadow: "var(--shadow-card)" }}>
                <h3 style={{ fontSize: "0.85rem", fontWeight: 700, marginBottom: "14px", fontFamily: "'Space Grotesk', sans-serif" }}>
                  Signals {list?.total ? `(${list.count} of ${list.total})` : ""}
                </h3>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem", minWidth: "760px" }}>
                    <thead>
                      <tr style={{ color: "var(--text-muted)", textAlign: "left", fontSize: "0.68rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                        <th style={thStyle}>Time (UTC)</th>
                        <th style={thStyle}>Stock</th>
                        <th style={thStyle}>Direction</th>
                        <th style={thStyle}>Conf.</th>
                        <th style={thStyle}>Regime</th>
                        <th style={thStyle}>Entry</th>
                        <th style={thStyle}>1h</th>
                        <th style={thStyle}>1d</th>
                        <th style={thStyle}>3d</th>
                      </tr>
                    </thead>
                    <tbody>
                      {list.signals.map((s) => (
                        <tr key={s.signal_id} style={{ borderTop: "1px solid var(--border-subtle)" }}>
                          <td style={{ ...tdStyle, color: "var(--text-muted)", whiteSpace: "nowrap" }}>{(s.signal_ts || "").replace("T", " ").slice(0, 16)}</td>
                          <td style={tdStyle}>
                            <Link href={`/stock/${s.symbol.replace(".NS", "").replace(".BO", "")}`} style={{ fontWeight: 800, color: "inherit", textDecoration: "none", fontFamily: "'Space Grotesk', sans-serif" }}>
                              {s.symbol.replace(".NS", "").replace(".BO", "")}
                            </Link>
                          </td>
                          <td style={tdStyle}><DirBadge direction={s.direction} /></td>
                          <td style={{ ...tdStyle, fontWeight: 700 }}>{s.confidence != null ? `${s.confidence}%` : "—"}</td>
                          <td style={{ ...tdStyle, textTransform: "capitalize", color: "var(--text-muted)" }}>{(s.regime || "").replace("_", " ")}</td>
                          <td style={tdStyle}>₹{s.entry_price?.toLocaleString("en-IN")}</td>
                          {HORIZONS.map((h) => {
                            const o = s.outcomes?.[h];
                            if (!o) return <td key={h} style={{ ...tdStyle, color: "var(--text-muted)" }}>·</td>;
                            const color = o.hit === 1 ? "var(--green)" : o.hit === 0 ? "var(--red)" : "var(--text-muted)";
                            return <td key={h} style={{ ...tdStyle, color, fontWeight: 700 }}>{pct(o.return_pct)}</td>;
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {/* Methodology */}
          <div className="glass animate-fadeInUp animate-delay-200" style={{ padding: "24px", marginTop: "24px", boxShadow: "var(--shadow-card)" }}>
            <h3 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "10px", fontFamily: "'Space Grotesk', sans-serif" }}>How the ledger works</h3>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", lineHeight: 1.6 }}>
              A scheduled scan runs the consensus predictor over a fixed watchlist several times each session and appends one immutable row per signal — direction, confidence, market regime, indicator states and sentiment at that moment. Each signal is later scored against realized prices at 1-hour, 1-day and 3-day horizons for return %, hit/miss and worst adverse move. A short signal is counted as a win when price falls. Hit rates are always shown with the realized return beside them.
            </p>
            <p style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "12px", opacity: 0.8 }}>
              Invexo is not SEBI registered. This is an educational tool, not investment advice.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}

const inputStyle = {
  padding: "8px 12px",
  borderRadius: "10px",
  border: "1px solid var(--border-medium)",
  background: "var(--search-bg)",
  color: "var(--text-primary)",
  fontSize: "0.82rem",
  fontFamily: "inherit",
  outline: "none",
};
const thStyle = { padding: "6px 10px", fontWeight: 700 };
const tdStyle = { padding: "10px", fontWeight: 500 };

function FilterField({ label, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "5px" }}>
      <label style={{ fontSize: "0.66rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)" }}>{label}</label>
      {children}
    </div>
  );
}
