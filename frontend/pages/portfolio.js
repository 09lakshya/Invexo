import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Navbar from "../components/Navbar";
import API from "../services/api";
import Head from "next/head";
import { useAuth } from "../context/AuthContext";
import { STOCK_METADATA, logoPath } from "../services/stocks";
import Icon from "../components/Icon";

// ── Mini donut for allocation ─────────────────────────────────────────────
function AllocationDonut({ holdings, size = 100 }) {
  if (!holdings || holdings.length === 0) return null;
  const total = holdings.reduce((s, h) => s + h.invested, 0);
  if (total === 0) return null;

  const colors = ["var(--accent)", "var(--green)", "var(--purple)", "var(--gold)", "var(--orange)", "var(--blue)", "var(--red)", "var(--green-dim)"];
  let cumulative = 0;
  const r = 38, cx = 50, cy = 50, circumference = 2 * Math.PI * r;

  return (
    <svg width={size} height={size} viewBox="0 0 100 100">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--border-subtle)" strokeWidth="12" />
      {holdings.map((h, i) => {
        const frac = h.invested / total;
        const arc = frac * circumference;
        const offset = -cumulative * circumference;
        cumulative += frac;
        return (
          <circle
            key={h.id || i}
            cx={cx} cy={cy} r={r}
            fill="none"
            stroke={colors[i % colors.length]}
            strokeWidth="12"
            strokeDasharray={`${arc} ${circumference}`}
            strokeDashoffset={offset}
            transform={`rotate(-90 ${cx} ${cy})`}
          />
        );
      })}
      <text x={cx} y={cy + 5} textAnchor="middle" fill="var(--text-primary)" fontSize="10" fontWeight="800" fontFamily="Space Grotesk, sans-serif">
        {holdings.length}
      </text>
    </svg>
  );
}

// ── Summary metric card ───────────────────────────────────────────────────
function MetricCard({ label, value, color = "var(--text-primary)", icon, delta }) {
  return (
    <div
      style={{
        background: "var(--bg-card)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "clamp(14px, 2vmin, 18px)",
        padding: "clamp(14px, 2.5vmin, 20px) clamp(16px, 2.5vmin, 22px)",
        backdropFilter: "blur(12px)",
        transition: "all 0.25s",
        position: "relative",
        overflow: "hidden",
      }}
      onMouseEnter={e => { e.currentTarget.style.border = "1px solid var(--accent-glow)"; e.currentTarget.style.transform = "translateY(-2px)"; }}
      onMouseLeave={e => { e.currentTarget.style.border = "1px solid var(--border-subtle)"; e.currentTarget.style.transform = "translateY(0)"; }}
    >
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: "2px", background: `linear-gradient(90deg, ${color}, transparent)`, opacity: 0.6 }} />
      {icon && <p style={{ marginBottom: "8px", color, display: "flex" }}><Icon name={icon} size={18} /></p>}
      <p style={{ fontSize: "0.65rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "8px" }}>{label}</p>
      <p style={{ fontSize: "clamp(1.1rem, 2.5vmin, 1.6rem)", fontWeight: 900, color, fontFamily: "'Space Grotesk', sans-serif", letterSpacing: "-0.02em" }}>{value}</p>
      {delta && <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>{delta}</p>}
    </div>
  );
}

// ── Holding row ───────────────────────────────────────────────────────────
function HoldingRow({ h, onRemove }) {
  const profit = h.pnl >= 0;
  const hasPrice = h.current_price > 0;
  const fmt = n => n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
  const pnlColor = profit ? "var(--green)" : "var(--red)";
  const [removing, setRemoving] = useState(false);

  const cleanSymbol = h.symbol ? h.symbol.replace(/\.NS$/i, "").replace(/\.BO$/i, "") : "";
  const metadata = STOCK_METADATA[cleanSymbol] || {};
  const companyName = metadata.name || h.symbol;
  const [logoError, setLogoError] = useState(false);
  const logoUrl = logoError ? null : logoPath(cleanSymbol);

  const handleRemove = async () => {
    setRemoving(true);
    await onRemove(h.id);
    setRemoving(false);
  };

  const pnlPct = hasPrice ? h.pnl_percent : null;

  return (
    <tr
      style={{
        borderBottom: "1px solid var(--border-subtle)",
        transition: "background 0.2s",
      }}
      onMouseEnter={e => { e.currentTarget.style.background = "var(--hover-overlay)"; }}
      onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
    >
      {/* Stock */}
      <td style={{ padding: "16px 18px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
          {logoUrl ? (
            <img
              src={logoUrl}
              alt={`${companyName} logo`}
              onError={() => setLogoError(true)}
              style={{
                width: "28px",
                height: "28px",
                borderRadius: "6px",
                border: "1px solid var(--border-medium)",
                background: "#fff",
                objectFit: "contain",
                padding: "2px",
                flexShrink: 0,
              }}
            />
          ) : (
            <div
              style={{
                width: "28px",
                height: "28px",
                borderRadius: "6px",
                background: "var(--accent-dim)",
                border: "1px solid var(--accent-glow)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.75rem",
                fontWeight: 800,
                color: "var(--accent)",
                fontFamily: "'Space Grotesk', sans-serif",
                flexShrink: 0,
              }}
            >
              {cleanSymbol ? cleanSymbol.substring(0, 2).toUpperCase() : "??"}
            </div>
          )}
          <div style={{ minWidth: 0 }}>
            <p style={{ fontWeight: 800, color: "var(--text-primary)", fontSize: "0.9rem", fontFamily: "'Space Grotesk', sans-serif", marginBottom: "2px", margin: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} title={companyName}>
              {companyName}
            </p>
            <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", margin: 0 }}>
              NSE: {cleanSymbol} · {h.added_on}
            </p>
          </div>
        </div>
      </td>
      {/* Qty */}
      <td style={{ padding: "16px 18px", textAlign: "right", fontWeight: 600, color: "var(--text-secondary)", fontSize: "0.875rem" }}>{h.quantity}</td>
      {/* Buy ₹ */}
      <td style={{ padding: "16px 18px", textAlign: "right", fontWeight: 600, color: "var(--text-secondary)", fontSize: "0.875rem" }}>₹{h.buy_price}</td>
      {/* Current ₹ */}
      <td style={{ padding: "16px 18px", textAlign: "right", fontWeight: 700, color: "var(--text-primary)", fontSize: "0.875rem" }}>
        {hasPrice ? `₹${h.current_price}` : <span style={{ color: "var(--text-muted)" }}>N/A</span>}
      </td>
      {/* Invested */}
      <td style={{ padding: "16px 18px", textAlign: "right", fontWeight: 600, color: "var(--text-muted)", fontSize: "0.875rem" }}>₹{fmt(h.invested)}</td>
      {/* Value */}
      <td style={{ padding: "16px 18px", textAlign: "right", fontWeight: 700, color: "var(--text-primary)", fontSize: "0.875rem" }}>
        {hasPrice ? `₹${fmt(h.current_value)}` : <span style={{ color: "var(--text-muted)" }}>—</span>}
      </td>
      {/* P&L */}
      <td style={{ padding: "16px 18px", textAlign: "right", fontWeight: 800, color: hasPrice ? pnlColor : "var(--text-muted)", fontSize: "0.875rem" }}>
        {hasPrice ? `${profit ? "+" : "−"}₹${fmt(Math.abs(h.pnl))}` : "—"}
      </td>
      {/* P&L % */}
      <td style={{ padding: "16px 18px", textAlign: "right", fontSize: "0.875rem" }}>
        {hasPrice ? (
          <span style={{
            padding: "3px 8px",
            borderRadius: "20px",
            background: profit ? "var(--green-dim)" : "var(--red-dim)",
            color: pnlColor,
            fontWeight: 800,
            fontSize: "0.78rem",
          }}>
            {profit ? "+" : ""}{pnlPct.toFixed(2)}%
          </span>
        ) : <span style={{ color: "var(--text-muted)" }}>—</span>}
      </td>
      {/* Remove */}
      <td style={{ padding: "16px 18px", textAlign: "center" }}>
        <button
          onClick={handleRemove}
          disabled={removing}
          aria-label={`Remove ${cleanSymbol} from portfolio`}
          style={{
            background: "var(--red-dim)",
            border: "1px solid var(--red-dim)",
            borderRadius: "8px",
            padding: "5px 10px",
            cursor: "pointer",
            color: "var(--red)",
            fontSize: "0.8rem",
            transition: "all 0.2s",
            opacity: removing ? 0.5 : 1,
          }}
          onMouseEnter={e => { e.currentTarget.style.background = "var(--red-dim)"; }}
          onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
        >
          {removing ? "…" : <Icon name="x" size={14} />}
        </button>
      </td>
    </tr>
  );
}

// ── Main Portfolio Page ───────────────────────────────────────────────────
export default function Portfolio() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [showForm, setShowForm]   = useState(false);

  const [searchQ, setSearchQ]         = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [selSymbol, setSelSymbol]     = useState("");
  const [quantity, setQuantity]       = useState("");
  const [buyPrice, setBuyPrice]       = useState("");
  const [formErr, setFormErr]         = useState("");

  const { data: holdings = [], isLoading: loading } = useQuery({
    queryKey: ["portfolio", user?.id],
    queryFn: async () => {
      const res = await API.get("/portfolio");
      return Array.isArray(res.data) ? res.data : [];
    },
    enabled: !!user,
  });

  const { data: analytics } = useQuery({
    queryKey: ["portfolio-analytics", user?.id],
    queryFn: async () => {
      const res = await API.get("/portfolio/analytics");
      return res.data;
    },
    enabled: !!user && holdings.length > 0,
  });

  const addMutation = useMutation({
    mutationFn: async (newHolding) => {
      return API.post("/portfolio/add", newHolding);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio", user?.id] });
      queryClient.invalidateQueries({ queryKey: ["portfolio-analytics", user?.id] });
      setShowForm(false);
      setSearchQ(""); setSelSymbol(""); setQuantity(""); setBuyPrice("");
    },
    onError: () => {
      setFormErr("Could not add holding. Please try again.");
    }
  });

  const removeMutation = useMutation({
    mutationFn: async (id) => {
      return API.delete(`/portfolio/remove/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio", user?.id] });
      queryClient.invalidateQueries({ queryKey: ["portfolio-analytics", user?.id] });
    },
    onError: () => {
      alert("Failed to remove. Please try again.");
    }
  });

  const handleSearch = async (q) => {
    setSearchQ(q);
    setSelSymbol("");
    if (!q) { setSearchResults([]); return; }
    try {
      const res = await API.get(`/search?q=${q}`);
      setSearchResults((res.data || []).slice(0, 6));
    } catch {
      setSearchResults([]);
    }
  };

  const selectStock = (sym) => {
    setSelSymbol(sym);
    setSearchQ(sym);
    setSearchResults([]);
  };

  const addHolding = async () => {
    if (!selSymbol || !quantity || !buyPrice) { setFormErr("Please fill in all three fields."); return; }
    if (parseFloat(quantity) <= 0 || parseFloat(buyPrice) <= 0) { setFormErr("Quantity and price must be greater than zero."); return; }
    setFormErr("");
    addMutation.mutate({
      symbol: selSymbol,
      company_name: selSymbol,
      quantity: parseFloat(quantity),
      buy_price: parseFloat(buyPrice),
    });
  };

  const removeHolding = async (id) => {
    return removeMutation.mutateAsync(id);
  };

  const adding = addMutation.isPending;

  // Summary
  const totalInvested = holdings.reduce((s, h) => s + h.invested, 0);
  const totalCurrent  = holdings.reduce((s, h) => s + (h.current_price > 0 ? h.current_value : h.invested), 0);
  const totalPnL      = totalCurrent - totalInvested;
  const totalPnLPct   = totalInvested > 0 ? (totalPnL / totalInvested) * 100 : 0;
  const fmt           = n => n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
  const isProfitable  = totalPnL >= 0;

  const inputStyle = {
    width: "100%",
    background: "var(--input-bg)",
    border: "1.5px solid var(--border-subtle)",
    borderRadius: "12px",
    padding: "12px 14px",
    color: "var(--text-primary)",
    fontSize: "0.9rem",
    fontFamily: "inherit",
    outline: "none",
    transition: "all 0.2s",
  };

  return (
    <>
      <Head>
        <title>Portfolio — Invexo</title>
        <meta name="description" content="Track and manage your stock portfolio with real-time P&L calculations." />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </Head>

      <div style={{ minHeight: "100vh" }}>
        <Navbar />

        <div style={{ maxWidth: "1300px", margin: "0 auto", padding: "clamp(20px, 4vmin, 40px) clamp(12px, 3vmin, 24px) clamp(40px, 8vmin, 80px)" }}>

          {/* Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: "clamp(12px, 2vmin, 16px)", marginBottom: "clamp(24px, 4vmin, 36px)", animation: "fadeInUp 0.5s ease forwards" }}>
            <div>
              <p className="section-label">Investments</p>
              <h1
                style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: "clamp(1.8rem, 4vmin, 2.8rem)",
                  fontWeight: 800,
                  letterSpacing: "-0.03em",
                  background: "linear-gradient(90deg, var(--accent) 0%, var(--purple) 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                  marginBottom: "6px",
                }}
              >
                My Portfolio
              </h1>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                {holdings.length} holding{holdings.length !== 1 ? "s" : ""} tracked
              </p>
            </div>



            <button
              onClick={() => { setShowForm(!showForm); setFormErr(""); }}
              style={{
                padding: "12px 24px",
                borderRadius: "12px",
                border: showForm ? "1px solid var(--red-dim)" : "none",
                cursor: "pointer",
                fontFamily: "inherit",
                fontWeight: 700,
                fontSize: "0.9rem",
                background: showForm ? "var(--red-dim)" : "linear-gradient(135deg, var(--accent) 0%, var(--purple) 100%)",
                color: showForm ? "var(--red)" : "var(--bg-primary)",
                boxShadow: showForm ? "none" : "0 6px 24px var(--accent-glow)",
                transition: "all 0.25s",
              }}
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                <Icon name={showForm ? "x" : "plus"} size={15} />
                {showForm ? "Cancel" : "Add Stock"}
              </span>
            </button>
          </div>

          {/* Add Stock Form */}
          {showForm && (
            <div
              style={{
                background: "var(--bg-card)",
                border: "1px solid var(--accent-glow)",
                borderRadius: "20px",
                padding: "28px",
                marginBottom: "28px",
                backdropFilter: "blur(20px)",
                animation: "fadeInUp 0.3s ease forwards",
              }}
            >
              <p style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: "1.1rem", color: "var(--text-primary)", marginBottom: "20px" }}>
                Add a Stock to Your Portfolio
              </p>

              <div style={{ display: "flex", flexWrap: "wrap", gap: "14px", alignItems: "flex-end" }}>
                {/* Symbol */}
                <div style={{ position: "relative", flex: "2 1 180px" }}>
                  <label style={{ display: "block", fontSize: "0.68rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "8px" }}>
                    Stock Symbol
                  </label>
                  <input
                    type="text"
                    value={searchQ}
                    onChange={e => handleSearch(e.target.value)}
                    placeholder="e.g. RELIANCE"
                    style={inputStyle}
                    onFocus={e => { e.target.style.borderColor = "var(--accent)"; }}
                    onBlur={e => { e.target.style.borderColor = "var(--border-subtle)"; }}
                  />
                  {searchResults.length > 0 && (
                    <div style={{ position: "absolute", top: "100%", left: 0, right: 0, background: "var(--bg-primary)", border: "1px solid var(--border-subtle)", borderRadius: "12px", zIndex: 50, marginTop: "6px", overflow: "hidden", boxShadow: "0 16px 48px var(--shadow-card)" }}>
                      {searchResults.map(stock => {
                        const sym = stock.symbol;
                        const companyName = stock.name;
                        return (
                          <div
                            key={sym}
                            onClick={() => selectStock(sym)}
                            style={{ padding: "11px 14px", cursor: "pointer", borderBottom: "1px solid var(--border-subtle)", fontSize: "0.875rem", transition: "background 0.15s", color: "var(--text-primary)", fontWeight: 600 }}
                            onMouseEnter={e => e.currentTarget.style.background = "var(--accent-dim)"}
                            onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                          >
                            <span style={{ color: "var(--accent)" }}>{sym}</span>
                            {companyName ? ` — ${companyName}` : ""}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Qty */}
                <div style={{ flex: "1 1 100px" }}>
                  <label style={{ display: "block", fontSize: "0.68rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "8px" }}>
                    Quantity
                  </label>
                  <input type="number" value={quantity} onChange={e => setQuantity(e.target.value)} placeholder="e.g. 10" style={inputStyle}
                    onFocus={e => { e.target.style.borderColor = "var(--accent)"; }}
                    onBlur={e => { e.target.style.borderColor = "var(--border-subtle)"; }}
                  />
                </div>

                {/* Buy price */}
                <div style={{ flex: "1 1 120px" }}>
                  <label style={{ display: "block", fontSize: "0.68rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "8px" }}>
                    Buy Price (₹)
                  </label>
                  <input type="number" value={buyPrice} onChange={e => setBuyPrice(e.target.value)} placeholder="e.g. 2500" style={inputStyle}
                    onFocus={e => { e.target.style.borderColor = "var(--accent)"; }}
                    onBlur={e => { e.target.style.borderColor = "var(--border-subtle)"; }}
                  />
                </div>

                <button
                  onClick={addHolding}
                  disabled={adding}
                  style={{
                    padding: "12px 24px",
                    borderRadius: "12px",
                    border: "none",
                    cursor: adding ? "not-allowed" : "pointer",
                    background: "linear-gradient(135deg, var(--accent), var(--purple))",
                    color: "var(--bg-primary)",
                    fontWeight: 800,
                    fontFamily: "inherit",
                    fontSize: "0.9rem",
                    opacity: adding ? 0.7 : 1,
                    boxShadow: "0 4px 16px var(--accent-glow)",
                    flex: "0 0 auto",
                    alignSelf: "flex-end",
                    minWidth: "110px",
                    transition: "all 0.2s",
                  }}
                >
                  {adding ? "Adding…" : "Add Stock"}
                </button>
              </div>

              {formErr && (
                <p style={{ color: "var(--red)", fontSize: "0.8rem", fontWeight: 600, marginTop: "12px", display: "flex", alignItems: "center", gap: "6px" }}><Icon name="alert" size={14} /> {formErr}</p>
              )}
            </div>
          )}

          {/* Summary cards */}
          {holdings.length > 0 && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(160px, 100%), 1fr))", gap: "clamp(10px, 1.5vmin, 14px)", marginBottom: "clamp(20px, 3vmin, 28px)", animation: "fadeInUp 0.5s 0.1s ease both" }}>
              <MetricCard label="Total Invested"  value={`₹${fmt(totalInvested)}`}  icon="briefcase" />
              <MetricCard label="Current Value"   value={`₹${fmt(totalCurrent)}`}   icon="bar-chart" color="var(--accent)" />
              <MetricCard
                label="Total P&L"
                value={`${totalPnL >= 0 ? "+" : "−"}₹${fmt(Math.abs(totalPnL))}`}
                color={isProfitable ? "var(--green)" : "var(--red)"}
                icon={isProfitable ? "trending-up" : "trending-down"}
              />
              <MetricCard
                label="Overall Return"
                value={`${totalPnLPct >= 0 ? "+" : ""}${totalPnLPct.toFixed(2)}%`}
                color={isProfitable ? "var(--green)" : "var(--red)"}
                icon="target"
              />
            </div>
          )}

          {/* Allocation insight */}
          {holdings.length > 1 && (
            <div style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: "18px", padding: "20px 24px", marginBottom: "24px", display: "flex", gap: "20px", alignItems: "center", flexWrap: "wrap", animation: "fadeInUp 0.5s 0.15s ease both" }}>
              <AllocationDonut holdings={holdings} size={80} />
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "10px" }}>Allocation</p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                  {holdings.slice(0, 6).map((h, i) => {
                    const colors = ["var(--accent)", "var(--green)", "var(--purple)", "var(--gold)", "var(--orange)", "var(--blue)"];
                    const pct = ((h.invested / totalInvested) * 100).toFixed(1);
                    return (
                      <span key={h.id} style={{ display: "inline-flex", alignItems: "center", gap: "6px", padding: "4px 10px", borderRadius: "20px", background: "var(--bg-primary)", border: "1px solid var(--border-subtle)", fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                        <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: colors[i % colors.length], flexShrink: 0 }} />
                        {h.symbol} · {pct}%
                      </span>
                    );
                  })}
                  {holdings.length > 6 && <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", padding: "4px 10px" }}>+{holdings.length - 6} more</span>}
                </div>
              </div>
            </div>
          )}

          {/* Holdings table / empty state */}
          {loading ? (
            <div style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: "20px", padding: "64px 24px", textAlign: "center" }}>
              <div className="spinner" style={{ margin: "0 auto 16px" }} />
              <p style={{ color: "var(--text-secondary)" }}>Loading your portfolio…</p>
            </div>
          ) : holdings.length === 0 ? (
            <div style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: "20px", padding: "80px 24px", textAlign: "center", animation: "fadeInUp 0.5s ease forwards" }}>
              <p style={{ marginBottom: "16px", color: "var(--text-muted)", display: "flex", justifyContent: "center" }}><Icon name="folder" size={48} strokeWidth={1.5} /></p>
              <p style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: "8px" }}>Portfolio is empty</p>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "24px" }}>
                Click <strong style={{ color: "var(--accent)" }}>+ Add Stock</strong> to start tracking your investments.
              </p>
              <button
                onClick={() => setShowForm(true)}
                style={{ padding: "12px 28px", borderRadius: "12px", border: "none", cursor: "pointer", fontFamily: "inherit", fontWeight: 700, fontSize: "0.9rem", background: "linear-gradient(135deg, var(--accent), var(--purple))", color: "var(--bg-primary)", boxShadow: "0 6px 24px var(--accent-glow)" }}
              >
                + Add Your First Stock
              </button>
            </div>
          ) : (
            <div style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: "20px", overflow: "hidden", backdropFilter: "blur(12px)", animation: "fadeInUp 0.5s 0.2s ease both" }}>
              <div style={{ overflowX: "auto" }}>
                <table className="table-premium" style={{ minWidth: "600px" }}>
                  <thead style={{ background: "var(--input-bg)" }}>
                    <tr>
                      {["Stock", "Qty", "Buy ₹", "Current ₹", "Invested", "Value", "P&L", "P&L %", ""].map(h => (
                        <th key={h} style={{ padding: "14px 18px", textAlign: h === "Stock" || h === "" ? "left" : "right", fontSize: "0.65rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {holdings.map(h => (
                      <HoldingRow key={h.id} h={h} onRemove={removeHolding} />
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Table footer */}
              <div style={{ padding: "clamp(10px, 2vmin, 14px) clamp(12px, 2vmin, 18px)", borderTop: "1px solid var(--border-subtle)", display: "flex", justifyContent: "flex-end", gap: "clamp(12px, 2vmin, 24px)", background: "var(--input-bg)", flexWrap: "wrap" }}>
                <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                  Total Invested: <strong style={{ color: "var(--text-primary)" }}>₹{fmt(totalInvested)}</strong>
                </span>
                <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                  Current Value: <strong style={{ color: "var(--accent)" }}>₹{fmt(totalCurrent)}</strong>
                </span>
                <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                  Net P&L: <strong style={{ color: isProfitable ? "var(--green)" : "var(--red)" }}>{isProfitable ? "+" : "−"}₹{fmt(Math.abs(totalPnL))}</strong>
                </span>
              </div>
            </div>
          )}

          {/* ── Portfolio Analytics & Risk Dashboard ───────────────────────────────── */}
          {analytics && holdings.length > 0 && (
            <div style={{ marginTop: "40px", animation: "fadeInUp 0.6s ease both" }}>
              <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "1.5rem", fontWeight: 800, color: "var(--text-primary)", marginBottom: "18px", letterSpacing: "-0.02em" }}>
                Portfolio Risk & Diversification Analytics
              </h2>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "20px" }}>
                {/* Diversification Score & Advice */}
                <div style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: "18px", padding: "24px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div>
                    <p style={{ fontSize: "0.68rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "12px" }}>Diversification Score</p>
                    <div style={{ display: "flex", alignItems: "baseline", gap: "8px", marginBottom: "14px" }}>
                      <span style={{ fontSize: "2.4rem", fontWeight: 900, fontFamily: "'Space Grotesk', sans-serif", color: "var(--accent)" }}>{analytics.metrics.diversification_score}</span>
                      <span style={{ fontSize: "1rem", color: "var(--text-muted)", fontWeight: 700 }}>/ 100</span>
                    </div>
                    {/* Progress Bar */}
                    <div style={{ width: "100%", height: "6px", background: "var(--border-subtle)", borderRadius: "3px", overflow: "hidden", marginBottom: "18px" }}>
                      <div style={{ width: `${analytics.metrics.diversification_score}%`, height: "100%", background: "linear-gradient(90deg, var(--accent) 0%, var(--purple) 100%)", borderRadius: "3px", transition: "width 1s ease-in-out" }} />
                    </div>
                  </div>
                  <div style={{ background: "var(--hover-overlay)", border: "1px solid var(--border-subtle)", borderRadius: "12px", padding: "14px 16px" }}>
                    <p style={{ fontSize: "0.72rem", fontWeight: 800, color: "var(--accent)", textTransform: "uppercase", letterSpacing: "0.05em", margin: "0 0 6px 0", display: "flex", alignItems: "center", gap: "6px" }}><Icon name="bot" size={14} /> Vexo Suggestion</p>
                    <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: "1.45", margin: 0 }}>{analytics.advice}</p>
                  </div>
                </div>

                {/* Risk Parameters Grid */}
                <div style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: "18px", padding: "24px" }}>
                  <p style={{ fontSize: "0.68rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "18px" }}>Risk & Volatility Parameters</p>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                    <div>
                      <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "4px", margin: 0 }}>Portfolio Beta</p>
                      <p style={{ fontSize: "1.2rem", fontWeight: 800, color: "var(--text-primary)", fontFamily: "'Space Grotesk', sans-serif", margin: 0 }}>{analytics.metrics.portfolio_beta}</p>
                      <span style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>Market avg is 1.0</span>
                    </div>
                    <div>
                      <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "4px", margin: 0 }}>Sharpe Ratio</p>
                      <p style={{ fontSize: "1.2rem", fontWeight: 800, color: "var(--green)", fontFamily: "'Space Grotesk', sans-serif", margin: 0 }}>{analytics.metrics.sharpe_ratio}</p>
                      <span style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>Risk-adjusted return</span>
                    </div>
                    <div>
                      <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "4px", margin: 0 }}>Annual Volatility</p>
                      <p style={{ fontSize: "1.2rem", fontWeight: 800, color: "var(--text-primary)", fontFamily: "'Space Grotesk', sans-serif", margin: 0 }}>{analytics.metrics.portfolio_volatility_annual}%</p>
                      <span style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>Standard deviation</span>
                    </div>
                    <div>
                      <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "4px", margin: 0 }}>Value at Risk (1D)</p>
                      <p style={{ fontSize: "1.2rem", fontWeight: 800, color: "var(--red)", fontFamily: "'Space Grotesk', sans-serif", margin: 0 }}>₹{analytics.metrics.value_at_risk_95.toLocaleString("en-IN")}</p>
                      <span style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>95% Confidence VaR</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── Removed Local Vexo Copilot UI ───────────────────────────── */}
        </div>
      </div>
    </>
  );
}
