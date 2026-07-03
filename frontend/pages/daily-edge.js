import React, { useState, useEffect } from "react";
import Head from "next/head";
import Link from "next/link";
import Navbar from "../components/Navbar";
import API from "../services/api";

const CAP_TABS = [
  { key: "large_cap", label: "Large Cap" },
  { key: "mid_cap", label: "Mid Cap" },
  { key: "small_cap", label: "Small Cap" },
];

function SignalBadge({ signal }) {
  const color =
    signal === "Bullish" ? "var(--green)" : signal === "Bearish" ? "var(--red)" : "var(--text-muted)";
  const bg =
    signal === "Bullish" ? "var(--green-dim)" : signal === "Bearish" ? "var(--red-dim)" : "var(--surface-hover)";
  return (
    <span
      style={{
        padding: "4px 10px",
        borderRadius: "8px",
        fontSize: "0.72rem",
        fontWeight: 700,
        color,
        background: bg,
        whiteSpace: "nowrap",
      }}
    >
      {signal === "Bullish" ? "▲" : signal === "Bearish" ? "▼" : "•"} {signal}
    </span>
  );
}

function EdgeBar({ lift }) {
  // lift: how many times more likely than the average stock (1.0 = average)
  const l = lift || 1;
  const fill = Math.max(8, Math.min(100, l * 50)); // 1.0x → 50%, 2.0x → 100%
  const color = l >= 1.35 ? "var(--green)" : l >= 1.15 ? "var(--accent)" : "var(--text-muted)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: "120px" }}>
      <div
        style={{
          flex: 1,
          height: "6px",
          borderRadius: "3px",
          background: "var(--surface-hover)",
          overflow: "hidden",
        }}
      >
        <div style={{ width: `${fill}%`, height: "100%", borderRadius: "3px", background: color }} />
      </div>
      <span style={{ fontSize: "0.78rem", fontWeight: 700, color, minWidth: "48px", textAlign: "right" }}>
        {l.toFixed(2)}×
      </span>
    </div>
  );
}

function StatTile({ label, value, sub, positive }) {
  return (
    <div
      className="glass"
      style={{ padding: "18px 20px", flex: "1 1 150px", minWidth: "150px", boxShadow: "var(--shadow-card)" }}
    >
      <div
        style={{
          fontSize: "0.68rem",
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          color: "var(--text-muted)",
          marginBottom: "6px",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: "1.4rem",
          fontWeight: 800,
          fontFamily: "'Space Grotesk', sans-serif",
          color: positive === undefined ? "var(--text-primary)" : positive ? "var(--green)" : "var(--red)",
        }}
      >
        {value}
      </div>
      {sub && <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "4px" }}>{sub}</div>}
    </div>
  );
}

export default function DailyEdgePage() {
  const [activeTab, setActiveTab] = useState("large_cap");
  const [picksData, setPicksData] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let retryTimer = null;

    const load = async () => {
      try {
        const [picksRes, statsRes] = await Promise.all([
          API.get("/predict/daily-picks"),
          API.get("/predict/daily-picks/stats").catch(() => null),
        ]);
        if (cancelled) return;
        setPicksData(picksRes.data);
        if (statsRes) setStats(statsRes.data);
        if (picksRes.data?.status !== "ready") {
          retryTimer = setTimeout(load, 6000);
        }
      } catch {
        if (!cancelled) retryTimer = setTimeout(load, 10000);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, []);

  const picks = picksData?.picks;
  const isUpdating = loading || picksData?.status !== "ready" || !picks;
  const bucket = picks?.[activeTab] || [];
  const realized = stats?.realized;
  const wf = stats?.model?.walk_forward;
  const hasRealized = realized && (realized.evaluated_5d > 0 || realized.evaluated_1d > 0);

  return (
    <>
      <Head>
        <title>Daily Edge | Invexo</title>
        <meta
          name="description"
          content="AI-ranked daily stock picks across large, mid and small caps, with measured historical accuracy."
        />
      </Head>

      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />

        <div className="page-wrapper" style={{ marginTop: "20px" }}>
          {/* Header */}
          <div style={{ textAlign: "center", marginBottom: "32px" }} className="animate-fadeInUp">
            <h1
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: "clamp(2rem, 5vmin, 3rem)",
                fontWeight: 800,
                letterSpacing: "-0.02em",
                marginBottom: "12px",
              }}
            >
              Daily <span className="text-gradient">Edge</span>
            </h1>
            <p style={{ color: "var(--text-muted)", fontSize: "1rem", maxWidth: "640px", margin: "0 auto" }}>
              A cross-sectional AI model ranks {picks?.universe_size || "250+"} liquid NSE stocks every day and
              surfaces the ones most likely to outperform — with its real track record shown below.
            </p>
            {picks?.as_of && (
              <p style={{ color: "var(--text-muted)", fontSize: "0.75rem", marginTop: "8px" }}>
                Signals computed from market data as of {picks.as_of}
              </p>
            )}
          </div>

          {/* Accuracy stats strip */}
          <div
            style={{ display: "flex", gap: "14px", flexWrap: "wrap", marginBottom: "28px" }}
            className="animate-fadeInUp animate-delay-100"
          >
            {hasRealized ? (
              <>
                <StatTile
                  label="5-Day Hit Rate"
                  value={realized.hit_rate_5d !== null ? `${realized.hit_rate_5d}%` : "—"}
                  sub={`${realized.evaluated_5d} picks evaluated · last ${realized.window_days} days`}
                  positive={realized.hit_rate_5d >= 50}
                />
                <StatTile
                  label="Avg 5-Day Return"
                  value={realized.avg_ret_5d_pct !== null ? `${realized.avg_ret_5d_pct > 0 ? "+" : ""}${realized.avg_ret_5d_pct}%` : "—"}
                  sub="across all evaluated picks"
                  positive={realized.avg_ret_5d_pct > 0}
                />
                <StatTile
                  label="Next-Day Hit Rate"
                  value={realized.hit_rate_1d !== null ? `${realized.hit_rate_1d}%` : "—"}
                  sub={`${realized.evaluated_1d} picks evaluated`}
                  positive={realized.hit_rate_1d >= 50}
                />
                <StatTile
                  label="Best 5-Day Pick"
                  value={realized.best_ret_5d_pct !== null ? `+${realized.best_ret_5d_pct}%` : "—"}
                  sub="single best realized return"
                  positive
                />
              </>
            ) : wf ? (
              <>
                <StatTile
                  label="Model Edge (5d)"
                  value={wf["5d"]?.top10_daily_edge_pct != null ? `+${wf["5d"].top10_daily_edge_pct}%` : "—"}
                  sub="top picks vs market avg, walk-forward tested"
                  positive
                />
                <StatTile
                  label="Model Win Rate (5d)"
                  value={wf["5d"]?.top10_abs_win_rate != null ? `${(wf["5d"].top10_abs_win_rate * 100).toFixed(1)}%` : "—"}
                  sub="backtested top-10 picks closing higher"
                  positive={wf["5d"]?.top10_abs_win_rate >= 0.5}
                />
                <StatTile
                  label="Model Edge (1d)"
                  value={wf["1d"]?.top10_daily_edge_pct != null ? `+${wf["1d"].top10_daily_edge_pct}%` : "—"}
                  sub="per day, walk-forward tested"
                  positive
                />
                <StatTile
                  label="Live Track Record"
                  value="Building…"
                  sub="realized accuracy appears after picks mature"
                />
              </>
            ) : null}
          </div>

          {/* Cap tabs */}
          <div style={{ display: "flex", gap: "8px", marginBottom: "20px", flexWrap: "wrap" }}>
            {CAP_TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                style={{
                  padding: "10px 20px",
                  borderRadius: "12px",
                  border: activeTab === t.key ? "1px solid var(--accent)" : "1px solid var(--border-subtle)",
                  background: activeTab === t.key ? "var(--accent-dim)" : "transparent",
                  color: activeTab === t.key ? "var(--accent)" : "var(--text-muted)",
                  fontWeight: 700,
                  fontSize: "0.85rem",
                  cursor: "pointer",
                  fontFamily: "inherit",
                  transition: "all 0.2s",
                }}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Picks */}
          {isUpdating ? (
            <div className="glass" style={{ padding: "40px", textAlign: "center", boxShadow: "var(--shadow-card)" }}>
              <div
                style={{
                  width: "48px",
                  height: "48px",
                  margin: "0 auto 16px",
                  borderRadius: "50%",
                  border: "3px solid var(--surface-hover)",
                  borderTopColor: "var(--accent)",
                  animation: "spin 0.9s linear infinite",
                }}
              />
              <h3 style={{ fontWeight: 700, marginBottom: "8px" }}>Scanning the market…</h3>
              <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                The AI is ranking the full universe. This usually takes under a minute.
              </p>
            </div>
          ) : bucket.length === 0 ? (
            <div className="glass" style={{ padding: "40px", textAlign: "center", boxShadow: "var(--shadow-card)" }}>
              <h3 style={{ fontWeight: 700, marginBottom: "8px" }}>No qualifying picks today</h3>
              <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", maxWidth: "480px", margin: "0 auto" }}>
                No {CAP_TABS.find((t) => t.key === activeTab)?.label} stock cleared the model's minimum
                outperformance probability today. That's the system working — it won't force weak picks.
              </p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }} className="animate-fadeInUp">
              {/* Column headers (desktop) */}
              <div
                className="daily-edge-row"
                style={{
                  display: "grid",
                  gridTemplateColumns: "minmax(110px, 1.4fr) 1fr 1fr 1.2fr 1fr 0.9fr",
                  gap: "12px",
                  padding: "0 20px",
                  fontSize: "0.68rem",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  color: "var(--text-muted)",
                }}
              >
                <span>Stock</span>
                <span>Price</span>
                <span>5D Target</span>
                <span>Edge vs Avg Stock</span>
                <span>Expected 5D</span>
                <span>1D Signal</span>
              </div>

              {bucket.map((p) => (
                <Link key={p.symbol} href={`/stock/${p.symbol}`} style={{ textDecoration: "none", color: "inherit" }}>
                  <div
                    className="glass daily-edge-row"
                    style={{
                      display: "grid",
                      gridTemplateColumns: "minmax(110px, 1.4fr) 1fr 1fr 1.2fr 1fr 0.9fr",
                      gap: "12px",
                      alignItems: "center",
                      padding: "16px 20px",
                      boxShadow: "var(--shadow-card)",
                      cursor: "pointer",
                      transition: "transform 0.15s, border-color 0.15s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.transform = "translateY(-2px)")}
                    onMouseLeave={(e) => (e.currentTarget.style.transform = "translateY(0)")}
                  >
                    <div>
                      <div style={{ fontWeight: 800, fontSize: "0.95rem", fontFamily: "'Space Grotesk', sans-serif" }}>
                        {p.symbol}
                      </div>
                      <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>
                        RSI {p.rsi_14} · 21d {p.momentum_21d_pct > 0 ? "+" : ""}
                        {p.momentum_21d_pct}%
                      </div>
                    </div>
                    <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>₹{p.current_price?.toLocaleString("en-IN")}</div>
                    <div style={{ fontWeight: 700, fontSize: "0.9rem", color: p.upside > 0 ? "var(--green)" : "var(--red)" }}>
                      ₹{p.target_price?.toLocaleString("en-IN")}
                    </div>
                    <EdgeBar lift={p.lift_5d} />
                    <div
                      style={{
                        fontWeight: 800,
                        fontSize: "0.9rem",
                        color: p.expected_5d_pct > 0 ? "var(--green)" : "var(--red)",
                      }}
                    >
                      {p.expected_5d_pct > 0 ? "+" : ""}
                      {p.expected_5d_pct}%
                    </div>
                    <SignalBadge signal={p.signal_1d} />
                  </div>
                </Link>
              ))}
            </div>
          )}

          {/* Methodology + disclaimer */}
          <div
            className="glass animate-fadeInUp animate-delay-200"
            style={{ padding: "24px", marginTop: "28px", boxShadow: "var(--shadow-card)" }}
          >
            <h3 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "10px", fontFamily: "'Space Grotesk', sans-serif" }}>
              How Daily Edge works
            </h3>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", lineHeight: 1.6 }}>
              One machine-learning model ranks every stock in the universe against its peers each day using
              momentum, volatility, volume and market-regime features. "Edge vs Avg Stock" is how many times
              more likely the model rates this stock to be a top 5-day performer than the average stock
              (1.00× = average) — a probabilistic edge, not a guarantee. Expected moves are volatility-scaled
              estimates. Every pick's real outcome is recorded, and the hit rates above reflect actual,
              measured performance — never simulated numbers.
            </p>
            <p style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "12px", opacity: 0.8 }}>
              Invexo is not SEBI registered. Daily Edge is an educational tool, not investment advice. Markets
              involve risk — do your own research before acting on any signal.
            </p>
          </div>
        </div>
      </div>

      <style jsx>{`
        @media (max-width: 720px) {
          :global(.daily-edge-row) {
            grid-template-columns: minmax(90px, 1.2fr) 1fr 1fr !important;
          }
          :global(.daily-edge-row) > *:nth-child(4),
          :global(.daily-edge-row) > *:nth-child(5) {
            display: none;
          }
        }
      `}</style>
    </>
  );
}
