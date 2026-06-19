import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import StockCard from "../components/StockCard";
import RealChart from "../components/RealChart";
import Navbar from "../components/Navbar";
import API from "../services/api";
import Head from "next/head";
import { STOCK_METADATA } from "../services/stocks";
import { useWebSocket } from "../context/WebSocketContext";

// ── Market hours helper (NSE: Mon–Fri 9:15–15:30 IST) ────────────────────
function isMarketOpen() {
  const now = new Date();
  // Convert to IST (UTC+5:30)
  const utc = now.getTime() + now.getTimezoneOffset() * 60000;
  const ist = new Date(utc + 5.5 * 3600000);
  const day = ist.getDay(); // 0=Sun, 6=Sat
  if (day === 0 || day === 6) return false;
  const mins = ist.getHours() * 60 + ist.getMinutes();
  return mins >= 555 && mins < 930; // 9:15=555, 15:30=930
}

// ── Market status indicator ───────────────────────────────────────────────
function MarketStatusBadge({ connected }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(isMarketOpen());
    const id = setInterval(() => setOpen(isMarketOpen()), 30000); // check every 30s
    return () => clearInterval(id);
  }, []);

  const live = connected && open;
  const label = !connected ? "Connecting…" : open ? "Live" : "Market Closed";
  const color = !connected ? "var(--gold)" : open ? "var(--green)" : "var(--text-muted)";
  const bg = !connected
    ? "var(--bg-card)"
    : open
    ? "var(--green-dim)"
    : "var(--bg-card)";
  const borderColor = !connected
    ? "var(--border-medium)"
    : open
    ? "var(--green-dim)"
    : "var(--border-subtle)";

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "5px 12px",
        borderRadius: "20px",
        background: bg,
        border: `1px solid ${borderColor}`,
        fontSize: "0.72rem",
        fontWeight: 700,
        color: color,
        letterSpacing: "0.05em",
        textTransform: "uppercase",
      }}
    >
      <span
        style={{
          width: "6px",
          height: "6px",
          borderRadius: "50%",
          background: color,
          animation: live ? "pulseGlowGreen 2s ease-in-out infinite" : "none",
          boxShadow: live ? "0 0 8px var(--green)" : "none",
        }}
      />
      {label}
    </div>
  );
}

// ── Ticker tape ───────────────────────────────────────────────────────────
function TickerTape({ stocks }) {
  const items = Object.entries(stocks).slice(0, 20);
  if (items.length === 0) return null;
  const doubled = [...items, ...items];

  return (
    <div
      className="ticker-wrap"
      style={{
        borderBottom: "1px solid var(--border-subtle)",
        borderTop: "1px solid var(--border-subtle)",
        background: "var(--breadth-bg)",
        backdropFilter: "blur(12px)",
        height: "36px",
        display: "flex",
        alignItems: "center",
      }}
    >
      <div
        style={{
          display: "inline-flex",
          gap: "40px",
          animation: "ticker 35s linear infinite",
        }}
      >
        {doubled.map(([sym, d], i) => {
          const pos = d?.percent >= 0;
          return (
            <span
              key={`${sym}-${i}`}
              style={{
                fontSize: "0.72rem",
                fontWeight: 600,
                color: "var(--text-secondary)",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                flexShrink: 0,
              }}
            >
              <span style={{ color: "var(--accent)", fontWeight: 700 }}>{sym}</span>
              <span>₹{(d?.price || 0).toFixed(2)}</span>
              <span style={{ color: pos ? "var(--green)" : "var(--red)", fontWeight: 700 }}>
                {pos ? "\u25B2" : "\u25BC"} {Math.abs(d?.percent || 0).toFixed(2)}%
              </span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

// ── Index summary card ────────────────────────────────────────────────────
function IndexCard({ symbol, data, prevData }) {
  if (!data) return null;
  const prc = data.price || 0;
  
  if (prc === 0) {
    return (
      <div
        style={{
          background: "var(--bg-card)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "clamp(14px, 2vmin, 20px)",
          padding: "clamp(16px, 3vmin, 24px) clamp(18px, 3vmin, 28px)",
          flex: "1 1 200px",
          minWidth: "min(220px, 100%)",
          boxShadow: "var(--shadow-card)",
        }}
      >
        <div style={{ marginBottom: "12px" }}>
          <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase" }}>
            {symbol === "NIFTY50" ? "NIFTY 50" : symbol === "SENSEX" ? "BSE SENSEX" : symbol}
          </span>
        </div>
        <div className="skeleton" style={{ width: "50%", height: "38px", marginBottom: "12px", borderRadius: "6px" }} />
        <div style={{ display: "flex", gap: "10px" }}>
          <div className="skeleton" style={{ width: "60px", height: "20px", borderRadius: "4px" }} />
          <div className="skeleton" style={{ width: "45px", height: "20px", borderRadius: "10px" }} />
        </div>
      </div>
    );
  }

  const prevPrc = prevData?.price || prc;
  const isUp = data.percent >= 0;
  const flash = prc > prevPrc ? "up" : prc < prevPrc ? "down" : null;

  return (
    <div
      style={{
        background: "var(--bg-card)",
        backdropFilter: "blur(24px) saturate(200%)",
        WebkitBackdropFilter: "blur(24px) saturate(200%)",
        border: `1px solid ${flash === "up" ? "var(--green-dim)" : flash === "down" ? "var(--red-dim)" : "var(--border-subtle)"}`,
        borderRadius: "clamp(14px, 2vmin, 20px)",
        padding: "clamp(16px, 3vmin, 24px) clamp(18px, 3vmin, 28px)",
        flex: "1 1 200px",
        minWidth: "min(220px, 100%)",
        position: "relative",
        overflow: "hidden",
        boxShadow: flash === "up"
          ? "0 0 24px var(--green-dim), var(--shadow-card)"
          : flash === "down"
          ? "0 0 24px var(--red-dim), var(--shadow-card)"
          : "var(--shadow-card)",
        animation: flash === "up"
          ? "flashPriceUp 0.8s ease forwards"
          : flash === "down"
          ? "flashPriceDown 0.8s ease forwards"
          : "none",
        transition: "border-color 0.3s ease, box-shadow 0.3s ease",
      }}
    >
      {/* Glass shimmer */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "linear-gradient(135deg, var(--skeleton-from) 0%, transparent 60%)",
          pointerEvents: "none",
        }}
      />
      {/* Decorative accent line */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: "2px",
          background: isUp
            ? "linear-gradient(90deg, var(--green), transparent)"
            : "linear-gradient(90deg, var(--red), transparent)",
          borderRadius: "20px 20px 0 0",
        }}
      />

      <div style={{ marginBottom: "8px" }}>
        <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase" }}>
          {symbol === "NIFTY50" ? "NIFTY 50" : symbol === "SENSEX" ? "BSE SENSEX" : symbol}
        </span>
      </div>

      <p
        style={{
          fontSize: "clamp(1.4rem, 3vmin, 2rem)",
          fontWeight: 800,
          color: flash === "up" ? "var(--green)" : flash === "down" ? "var(--red)" : "var(--text-primary)",
          transition: "color 0.4s",
          fontFamily: "'Space Grotesk', sans-serif",
          letterSpacing: "-0.03em",
          marginBottom: "8px",
        }}
      >
        {prc.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </p>

      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <span
          style={{
            fontSize: "0.85rem",
            fontWeight: 700,
            color: isUp ? "var(--green)" : "var(--red)",
          }}
        >
          {isUp ? "\u25B2 +" : "\u25BC "}{(data.change || 0).toFixed(2)}
        </span>
        <span
          style={{
            padding: "2px 8px",
            borderRadius: "20px",
            background: isUp ? "var(--green-dim)" : "var(--red-dim)",
            color: isUp ? "var(--green)" : "var(--red)",
            fontSize: "0.75rem",
            fontWeight: 700,
          }}
        >
          {isUp ? "+" : ""}{(data.percent || 0).toFixed(2)}%
        </span>
      </div>
    </div>
  );
}

// ── Skeleton loader ───────────────────────────────────────────────────────
function SkeletonCard() {
  return (
    <div
      style={{
        background: "var(--bg-card)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "16px",
        padding: "20px",
        height: "130px",
      }}
    >
      <div style={{ display: "flex", gap: "12px", marginBottom: "16px" }}>
        <div className="skeleton" style={{ width: "60%", height: "14px" }} />
        <div className="skeleton" style={{ width: "20%", height: "14px", marginLeft: "auto" }} />
      </div>
      <div className="skeleton" style={{ width: "50%", height: "24px", marginBottom: "12px" }} />
      <div style={{ display: "flex", gap: "8px" }}>
        <div className="skeleton" style={{ width: "40px", height: "12px" }} />
        <div className="skeleton" style={{ width: "40px", height: "12px" }} />
      </div>
    </div>
  );
}

// ── Main Dashboard ────────────────────────────────────────────────────────
export default function Home() {
  const router = useRouter();
  const { stocks, prevStocks, connected } = useWebSocket();
  const [filterCategory, setFilterCategory] = useState("All");
  const [viewAll, setViewAll] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [recentSearches, setRecentSearches] = useState([]);
  const [showRecents, setShowRecents] = useState(false);
  const [focused, setFocused] = useState(false);
  const searchRef = useRef(null);

  // Watchlist & Alerts states
  const [watchlist, setWatchlist] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [watchlistLoading, setWatchlistLoading] = useState(false);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [alertTargetPrice, setAlertTargetPrice] = useState("");
  const [alertCondition, setAlertCondition] = useState("above");

  const fetchWatchlist = async () => {
    setWatchlistLoading(true);
    try {
      const res = await API.get("/watchlist/");
      setWatchlist(res.data.map(item => item.symbol.toUpperCase()));
    } catch (err) {
      console.error("Failed to fetch watchlist:", err);
    } finally {
      setWatchlistLoading(false);
    }
  };

  const fetchAlerts = async () => {
    setAlertsLoading(true);
    try {
      const res = await API.get("/alerts/");
      setAlerts(res.data);
    } catch (err) {
      console.error("Failed to fetch alerts:", err);
    } finally {
      setAlertsLoading(false);
    }
  };

  useEffect(() => {
    fetchWatchlist();
    fetchAlerts();
  }, []);

  const toggleWatchlist = async (symbol) => {
    const cleanSym = symbol.toUpperCase().replace(/\.NS$/i, "").replace(/\.BO$/i, "");
    const isWatched = watchlist.includes(cleanSym);
    try {
      if (isWatched) {
        await API.delete(`/watchlist/${cleanSym}`);
        setWatchlist(prev => prev.filter(s => s !== cleanSym));
      } else {
        await API.post("/watchlist/", { symbol: cleanSym });
        setWatchlist(prev => [...prev, cleanSym]);
      }
    } catch (err) {
      console.error("Failed to toggle watchlist:", err);
    }
  };

  const handleCreateAlert = async () => {
    if (!activeStockSymbol || !alertTargetPrice) return;
    const cleanSym = activeStockSymbol.toUpperCase().replace(/\.NS$/i, "").replace(/\.BO$/i, "");
    try {
      await API.post("/alerts/", {
        symbol: cleanSym,
        target_price: parseFloat(alertTargetPrice),
        condition: alertCondition
      });
      fetchAlerts();
      alert(`Alert set for ${cleanSym} when price goes ${alertCondition} ₹${alertTargetPrice}`);
    } catch (err) {
      console.error("Failed to create alert:", err);
      alert("Failed to create alert");
    }
  };

  const handleDeleteAlert = async (id) => {
    try {
      await API.delete(`/alerts/${id}`);
      fetchAlerts();
    } catch (err) {
      console.error("Failed to delete alert:", err);
      alert("Failed to delete alert");
    }
  };

  // States for Quick View Chart Modal
  const [activeStockSymbol, setActiveStockSymbol] = useState(null);
  const [showChartModal, setShowChartModal] = useState(false);
  const [modalHistory, setModalHistory] = useState([]);
  const [modalPrediction, setModalPrediction] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalPeriod, setModalPeriod] = useState("1m");
  const [modalLogoError, setModalLogoError] = useState(false);
  const [modalError, setModalError] = useState(null);
  const modalHistoryCacheRef = useRef({});

  const getPeriodFormat = (p) => {
    const PERIODS = [
      { key: "1d", yf: "1d" },
      { key: "1w", yf: "5d" },
      { key: "1m", yf: "1mo" },
      { key: "3m", yf: "3mo" },
      { key: "6m", yf: "6mo" },
      { key: "1y", yf: "1y" },
      { key: "5y", yf: "5y" },
    ];
    return PERIODS.find(x => x.key === p)?.yf || p;
  };

  // Lock body scroll and hide legal disclaimer when modal is open
  useEffect(() => {
    if (showChartModal) {
      document.body.style.overflow = "hidden";
      document.body.setAttribute("data-fullscreen", "true");
    } else {
      document.body.style.overflow = "";
      document.body.removeAttribute("data-fullscreen");
    }
    return () => {
      document.body.style.overflow = "";
      document.body.removeAttribute("data-fullscreen");
    };
  }, [showChartModal]);

  const openQuickView = async (symbol) => {
    setActiveStockSymbol(symbol);
    setShowChartModal(true);
    setModalPeriod("1m");
    setModalLoading(true);
    setModalHistory([]);
    setModalPrediction(null);
    setModalError(null);
    setModalLogoError(false);
    const curPrc = stocks[symbol]?.price || 0;
    setAlertTargetPrice(curPrc ? String(curPrc) : "");
    setAlertCondition("above");
    const normalizedSymbol = symbol.replace(/\.NS$/i, "");
    try {
      const predRes = await API.get(`/predict/${normalizedSymbol}.NS`);
      if (predRes.data && predRes.data.error) {
        throw new Error(predRes.data.error);
      }
      setModalPrediction(predRes.data);
    } catch (err) {
      console.error("ERROR Loading stock details:", err);
      setModalError("Data unavailable — market may be closed");
    }
  };

  useEffect(() => {
    if (!showChartModal || !activeStockSymbol) return;
    
    const normalizedSymbol = activeStockSymbol.replace(/\.NS$/i, "");
    const cacheKey = `${normalizedSymbol}_${modalPeriod}`;
    if (modalHistoryCacheRef.current[cacheKey]) {
      setModalHistory(modalHistoryCacheRef.current[cacheKey]);
      setModalLoading(false);
      return;
    }

    const loadHistory = async () => {
      setModalLoading(true);
      try {
        const histRes = await API.get(`/market/${normalizedSymbol}/history?period=${getPeriodFormat(modalPeriod)}`);
        const data = Array.isArray(histRes.data) ? histRes.data : [];
        setModalHistory(data);
        modalHistoryCacheRef.current[cacheKey] = data;
      } catch (err) {
        console.error("ERROR loading history:", err);
        setModalError("Data unavailable — market may be closed");
      } finally {
        setModalLoading(false);
      }
    };
    loadHistory();
  }, [modalPeriod, activeStockSymbol, showChartModal]);

  // Load recent searches from localStorage
  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("invexo_recent_searches") || "[]");
      setRecentSearches(stored.slice(0, 5));
    } catch { setRecentSearches([]); }
  }, []);

  // Close dropdowns on outside click
  useEffect(() => {
    const handler = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setResults([]);
        setShowRecents(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleSearch = async (val) => {
    setQuery(val);
    if (!val.trim()) { setResults([]); setShowRecents(true); return; }
    setShowRecents(false);
    try {
      const res = await API.get(`/search?q=${val}`);
      setResults((res.data || []).slice(0, 8));
    } catch {
      setResults([]);
    }
  };

  const goToStock = (sym) => {
    setQuery(""); setResults([]); setShowRecents(false);
    // Save to recent searches
    try {
      const stored = JSON.parse(localStorage.getItem("invexo_recent_searches") || "[]");
      const updated = [sym, ...stored.filter(s => s !== sym)].slice(0, 5);
      localStorage.setItem("invexo_recent_searches", JSON.stringify(updated));
      setRecentSearches(updated);
    } catch {}
    router.push(`/stock/${sym}`);
  };

  const indexSymbols = ["NIFTY50", "SENSEX"];

  const entries = Object.entries(stocks || {});
  const indexEntries = entries.filter(([s]) => indexSymbols.includes(s));
  const stockEntries = entries
    .filter(([s]) => !indexSymbols.includes(s))
    .sort((a, b) => b[1].percent - a[1].percent);

  const gainers = stockEntries.filter(([, d]) => d.percent >= 0);
  const losers = stockEntries.filter(([, d]) => d.percent < 0).reverse();

  let displayed = [];
  if (filterCategory === "Gainers") {
    displayed = viewAll ? gainers : gainers.slice(0, 10);
  } else if (filterCategory === "Losers") {
    displayed = viewAll ? losers : losers.slice(0, 10);
  } else if (filterCategory === "Watchlist") {
    const watchedStockEntries = stockEntries.filter(([sym]) => watchlist.includes(sym.toUpperCase().replace(/\.NS$/i, "").replace(/\.BO$/i, "")));
    const missingSymbols = watchlist.filter(sym => !stockEntries.some(([s]) => s.toUpperCase().replace(/\.NS$/i, "").replace(/\.BO$/i, "") === sym));
    const missingEntries = missingSymbols.map(sym => [sym + ".NS", stocks[sym + ".NS"] || stocks[sym] || { price: 0, change: 0, percent: 0 }]);
    displayed = [...watchedStockEntries, ...missingEntries];
  } else {
    const topGainers = gainers.slice(0, 10);
    const topLosers = losers.slice(0, 10);
    displayed = viewAll ? [...gainers, ...losers] : [...topGainers, ...topLosers];
  }

  const totalStocks = stockEntries.length;
  const gainersCount = gainers.length;
  const losersCount = losers.length;

  const isLoaded = stockEntries.length > 0;

  const normalizedActiveSymbol = activeStockSymbol ? activeStockSymbol.replace(/\.NS$/i, "") : null;
  const activeMetadata = STOCK_METADATA[normalizedActiveSymbol] || {};
  const activeCompanyName = activeMetadata.name || activeStockSymbol;
  const activeCompanyDomain = activeMetadata.domain;
  const activeLogoUrl = null; // Removed external logo API — using styled initials badge

  return (
    <>
      <Head>
        <title>Invexo — Live Market Dashboard</title>
        <meta name="description" content="Real-time Indian stock market data, live prices, AI advisor, and portfolio tracker." />
      </Head>

      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />

        {/* Ticker tape */}
        {isLoaded && <TickerTape stocks={stocks} />}

        <div style={{ maxWidth: "1400px", margin: "0 auto", padding: "clamp(20px, 4vmin, 32px) clamp(12px, 3vmin, 24px) clamp(40px, 8vmin, 64px)" }}>

          {/* ── Header ──────────────────────────────────────────────── */}
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              justifyContent: "space-between",
              alignItems: "flex-end",
              gap: "16px",
              marginBottom: "32px",
              animation: "fadeInUp 0.5s ease forwards",
            }}
          >
            <div>
              <p style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: "8px" }}>
                Indian Stock Market
              </p>
              <h1
                style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: "clamp(2rem, 4vmin, 3rem)",
                  fontWeight: 800,
                  letterSpacing: "-0.03em",
                  lineHeight: 1.1,
                  background: "linear-gradient(90deg, var(--accent) 0%, var(--purple) 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                  marginBottom: "8px",
                }}
              >
                Live Market
              </h1>
              <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", fontWeight: 400 }}>
                Real-time prices · Updated every ~15 seconds
              </p>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
              {isLoaded && (
                <div style={{ display: "flex", gap: "12px" }}>
                  <div style={{ textAlign: "center" }}>
                    <p style={{ fontSize: "1.2rem", fontWeight: 800, color: "var(--green)", fontFamily: "'Space Grotesk', sans-serif" }}>{gainersCount}</p>
                    <p style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Gainers</p>
                  </div>
                  <div style={{ width: "1px", background: "var(--border-subtle)" }} />
                  <div style={{ textAlign: "center" }}>
                    <p style={{ fontSize: "1.2rem", fontWeight: 800, color: "var(--red)", fontFamily: "'Space Grotesk', sans-serif" }}>{losersCount}</p>
                    <p style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Losers</p>
                  </div>
                  <div style={{ width: "1px", background: "var(--border-subtle)" }} />
                  <div style={{ textAlign: "center" }}>
                    <p style={{ fontSize: "1.2rem", fontWeight: 800, color: "var(--accent)", fontFamily: "'Space Grotesk', sans-serif" }}>{totalStocks}</p>
                    <p style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Stocks</p>
                  </div>
                </div>
              )}
              <MarketStatusBadge connected={connected} />
            </div>
          </div>

          {/* ── Search Bar ──────────────────────────────────────────── */}
          <div
            ref={searchRef}
            style={{
              position: "relative",
              maxWidth: "480px",
              marginBottom: "32px",
              zIndex: 30,
              animation: "fadeInUp 0.5s 0.05s ease both",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                background: focused ? "var(--accent-dim)" : "var(--search-bg)",
                border: `1.5px solid ${focused ? "var(--accent)" : "var(--search-border)"}`,
                borderRadius: "16px",
                padding: "12px 18px",
                transition: "all 0.25s ease",
                boxShadow: focused ? "0 0 24px var(--accent-glow), var(--shadow-card)" : "var(--shadow-card)",
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={focused ? "var(--accent)" : "var(--text-muted)"} strokeWidth="2.5" style={{ flexShrink: 0 }}>
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
              <input
                type="text"
                value={query}
                onChange={e => handleSearch(e.target.value)}
                placeholder="Search stocks by name or symbol…"
                style={{
                  background: "transparent",
                  border: "none",
                  outline: "none",
                  color: "var(--text-primary)",
                  fontSize: "0.95rem",
                  fontFamily: "inherit",
                  width: "100%",
                }}
                onFocus={() => {
                  setFocused(true);
                  if (!query.trim()) setShowRecents(true);
                }}
                onBlur={() => setFocused(false)}
              />
              {query && (
                <button
                  onClick={() => { setQuery(""); setResults([]); }}
                  style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)", fontSize: "16px", padding: 0 }}
                >✕</button>
              )}
            </div>

            {/* Search Results Dropdown */}
            {results.length > 0 && (
              <div
                style={{
                  position: "absolute",
                  top: "calc(100% + 8px)",
                  left: 0,
                  right: 0,
                  background: "var(--dropdown-bg)",
                  border: "1px solid var(--border-medium)",
                  borderRadius: "16px",
                  overflow: "hidden",
                  boxShadow: "var(--shadow-dropdown)",
                  zIndex: 200,
                }}
              >
                {results.map((sym) => {
                  const metadata = STOCK_METADATA[sym] || {};
                  const companyName = metadata.name || sym;
                  return (
                    <div
                      key={sym}
                      onClick={() => goToStock(sym)}
                      style={{
                        padding: "14px 18px",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        borderBottom: "1px solid var(--border-subtle)",
                        transition: "background 0.15s",
                        fontSize: "0.95rem",
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = "var(--hover-overlay)"}
                      onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                    >
                      <div
                        style={{
                          width: "32px",
                          height: "32px",
                          borderRadius: "10px",
                          background: "var(--accent-dim)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: "11px",
                          fontWeight: 700,
                          color: "var(--accent)",
                          flexShrink: 0,
                        }}
                      >
                        {sym.slice(0, 2)}
                      </div>
                      <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                        {companyName}
                        {metadata.name ? ` — ${sym}` : ""}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Recent Searches Dropdown */}
            {showRecents && results.length === 0 && !query.trim() && recentSearches.length > 0 && (
              <div
                style={{
                  position: "absolute",
                  top: "calc(100% + 8px)",
                  left: 0,
                  right: 0,
                  background: "var(--dropdown-bg)",
                  border: "1px solid var(--border-medium)",
                  borderRadius: "16px",
                  overflow: "hidden",
                  boxShadow: "var(--shadow-dropdown)",
                  zIndex: 200,
                  animation: "fadeIn 0.15s ease",
                }}
              >
                <div style={{ padding: "12px 18px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-subtle)" }}>
                  <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Recent Searches</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      localStorage.removeItem("invexo_recent_searches");
                      setRecentSearches([]);
                      setShowRecents(false);
                    }}
                    style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)", fontSize: "0.72rem", fontWeight: 600, padding: 0, fontFamily: "inherit" }}
                    onMouseEnter={e => e.currentTarget.style.color = "var(--red)"}
                    onMouseLeave={e => e.currentTarget.style.color = "var(--text-muted)"}
                  >Clear</button>
                </div>
                {recentSearches.map((sym) => (
                  <div
                    key={sym}
                    onClick={() => goToStock(sym)}
                    style={{
                      padding: "14px 18px",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      borderBottom: "1px solid var(--border-subtle)",
                      transition: "background 0.15s",
                      fontSize: "0.95rem",
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = "var(--hover-overlay)"}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                      <polyline points="1 4 1 10 7 10" />
                      <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
                    </svg>
                    <span style={{ fontWeight: 600, color: "var(--accent)" }}>{sym}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Index Cards ──────────────────────────────────────────── */}
          {indexEntries.length > 0 && (
            <div style={{ marginBottom: "32px", animation: "fadeInUp 0.5s 0.1s ease both" }}>
              <p className="section-label">Market Indices</p>
              <div style={{ display: "flex", gap: "clamp(10px, 2vmin, 16px)", flexWrap: "wrap" }}>
                {indexEntries.map(([sym, data]) => (
                  <IndexCard key={sym} symbol={sym} data={data} prevData={prevStocks[sym]} />
                ))}
              </div>
            </div>
          )}

          {/* ── Market breadth bar ─────────────────────────────────── */}
          {isLoaded && (
            <div
              style={{
                background: "var(--bg-card)",
                backdropFilter: "blur(16px)",
                WebkitBackdropFilter: "blur(16px)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "16px",
                padding: "16px 20px",
                marginBottom: "32px",
                boxShadow: gainersCount > losersCount
                  ? "0 0 32px var(--green-dim), var(--shadow-card)"
                  : "var(--shadow-card)",
                animation: "fadeInUp 0.5s 0.15s ease both",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)", letterSpacing: "0.05em", textTransform: "uppercase" }}>
                  Market Breadth
                </span>
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  {gainersCount} gainers · {losersCount} losers
                </span>
              </div>
              <div style={{ display: "flex", height: "8px", borderRadius: "8px", overflow: "hidden", gap: "2px" }}>
                <div
                  style={{
                    flex: gainersCount,
                    background: "linear-gradient(90deg, var(--green), var(--green-dim))",
                    borderRadius: "8px 0 0 8px",
                    transition: "flex 0.5s ease",
                    boxShadow: gainersCount > losersCount ? "0 0 12px var(--green-dim)" : "none",
                  }}
                />
                <div
                  style={{
                    flex: losersCount,
                    background: "linear-gradient(90deg, var(--red-dim), var(--red))",
                    borderRadius: "0 8px 8px 0",
                    transition: "flex 0.5s ease",
                    boxShadow: losersCount > gainersCount ? "0 0 12px var(--red-dim)" : "none",
                  }}
                />
              </div>
            </div>
          )}

          {/* ── Filter tabs ──────────────────────────────────────── */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "12px",
              marginBottom: "20px",
              animation: "fadeInUp 0.5s 0.2s ease both",
            }}
          >
            <p className="section-label" style={{ margin: 0 }}>
              Trending Stocks
            </p>
            <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
              <button
                onClick={() => setViewAll(!viewAll)}
                style={{
                  padding: "6px 14px",
                  borderRadius: "9px",
                  border: "1px solid var(--border-medium)",
                  background: viewAll ? "var(--accent-dim)" : "transparent",
                  color: viewAll ? "var(--accent)" : "var(--text-muted)",
                  cursor: "pointer",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  transition: "all 0.2s"
                }}
              >
                {viewAll ? "Show Top 10" : "View All"}
              </button>
              <div style={{ display: "flex", gap: "4px", background: "var(--filter-tab-bg)", border: "1px solid var(--filter-tab-border)", borderRadius: "12px", padding: "4px" }}>
                {["All", "Gainers", "Losers", "Watchlist"].map((cat) => (
                <button
                  key={cat}
                  onClick={() => setFilterCategory(cat)}
                  style={{
                    padding: "6px 16px",
                    borderRadius: "9px",
                    border: "none",
                    cursor: "pointer",
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    fontFamily: "inherit",
                    transition: "all 0.2s",
                    background: filterCategory === cat
                      ? cat === "Gainers"
                        ? "var(--green-dim)"
                        : cat === "Losers"
                        ? "var(--red-dim)"
                        : cat === "Watchlist"
                        ? "var(--gold-dim, rgba(255, 193, 7, 0.15))"
                        : "var(--accent-dim)"
                      : "transparent",
                    color: filterCategory === cat
                      ? cat === "Gainers" ? "var(--green)" : cat === "Losers" ? "var(--red)" : cat === "Watchlist" ? "var(--gold)" : "var(--accent)"
                      : "var(--filter-tab-inactive)",
                    boxShadow: filterCategory === cat ? "0 2px 8px var(--shadow-card)" : "none",
                  }}
                >
                  {cat === "Watchlist" ? "★ Watchlist" : cat}
                </button>
              ))}
              </div>
            </div>
          </div>

          {/* ── Stock Grid ───────────────────────────────────────────── */}
          {!isLoaded ? (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(min(220px, 100%), 1fr))",
                gap: "clamp(10px, 2vmin, 16px)",
              }}
            >
              {Array.from({ length: 9 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : displayed.length === 0 ? (
            <div
              style={{
                background: "var(--bg-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "20px",
                padding: "64px 24px",
                textAlign: "center",
              }}
            >
              <p style={{ fontSize: "3rem", marginBottom: "16px" }}>📉</p>
              <p style={{ color: "var(--text-muted)", fontSize: "1rem" }}>
                No {filterCategory.toLowerCase()} stocks right now.
              </p>
            </div>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(min(200px, 100%), 1fr))",
                gap: "clamp(10px, 1.5vmin, 14px)",
                animation: "fadeIn 0.4s ease forwards",
              }}
            >
              {displayed.map(([sym, current], idx) => {
                const prev = prevStocks[sym];
                const curPrc = current?.price || 0;
                const prevPrc = prev?.price || 0;
                let colorClass = "text-white";
                if (prev) {
                  colorClass = curPrc > prevPrc ? "text-green-premium" : curPrc < prevPrc ? "text-red-premium" : colorClass;
                }
                return (
                  <div
                    key={sym}
                    style={{ animation: `dealIn 0.5s ${idx * 0.04}s cubic-bezier(0.22, 1, 0.36, 1) both` }}
                  >
                    <StockCard
                      symbol={sym}
                      price={curPrc}
                      change={current?.change}
                      percent={current?.percent}
                      color={colorClass}
                      onClick={() => openQuickView(sym)}
                      isWatched={watchlist.includes(sym.toUpperCase().replace(/\.NS$/i, "").replace(/\.BO$/i, ""))}
                      onToggleWatchlist={() => toggleWatchlist(sym)}
                    />
                  </div>
                );
              })}
            </div>
          )}

          {/* ── Footer note ─────────────────────────────────── */}
          <div style={{ marginTop: "48px", textAlign: "center" }}>
            <p style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 500 }}>
              Data is for informational purposes only. Not financial advice. Prices may be delayed.
            </p>
          </div>
        </div>
      </div>

      {/* Quick View Chart Modal */}
      {showChartModal && activeStockSymbol && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(8, 12, 26, 0.6)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(8px)",
            padding: "20px",
            animation: "fadeIn 0.25s ease-out forwards",
          }}
          onClick={() => setShowChartModal(false)}
        >
          <div
            className="glass"
            style={{
              width: "100%",
              maxWidth: "800px",
              borderRadius: "20px",
              padding: "clamp(16px, 3vmin, 28px)",
              boxShadow: "0 24px 64px rgba(0,0,0,0.8), 0 0 0 1px var(--border-medium)",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
              animation: "scaleIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards",
              background: "var(--bg-card)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                {activeLogoUrl ? (
                  <img
                    src={activeLogoUrl}
                    alt={`${activeCompanyName} logo`}
                    onError={() => setModalLogoError(true)}
                    style={{
                      width: "40px",
                      height: "40px",
                      borderRadius: "10px",
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
                      width: "40px",
                      height: "40px",
                      borderRadius: "10px",
                      background: "var(--accent-dim)",
                      border: "1px solid var(--accent-glow)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "1.1rem",
                      fontWeight: 800,
                      color: "var(--accent)",
                      fontFamily: "'Space Grotesk', sans-serif",
                      flexShrink: 0,
                    }}
                  >
                    {normalizedActiveSymbol ? normalizedActiveSymbol.substring(0, 2).toUpperCase() : "??"}
                  </div>
                )}
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "1.25rem", fontWeight: 800, color: "var(--text-primary)", margin: 0, lineHeight: 1.2 }}>
                      {activeCompanyName}
                    </h2>
                    <span style={{ fontSize: "0.68rem", color: "var(--accent)", fontWeight: 700, padding: "2px 6px", background: "var(--accent-dim)", borderRadius: "4px" }}>
                      {normalizedActiveSymbol}
                    </span>
                  </div>
                  <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", margin: "2px 0 0 0" }}>
                    Quick View · AI Prediction Details
                  </p>
                </div>
              </div>

              <button
                onClick={() => setShowChartModal(false)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--text-muted)",
                  fontSize: "1.5rem",
                  cursor: "pointer",
                  padding: "4px",
                  lineHeight: 1,
                  transition: "color 0.2s",
                }}
                onMouseEnter={(e) => e.currentTarget.style.color = "var(--text-primary)"}
                onMouseLeave={(e) => e.currentTarget.style.color = "var(--text-muted)"}
              >
                &times;
              </button>
            </div>

            {/* Timeframe Selector */}
            <div style={{
              display: "flex",
              gap: "4px",
              background: "var(--filter-tab-bg)",
              border: "1px solid var(--filter-tab-border)",
              borderRadius: "10px",
              padding: "3px",
              width: "fit-content",
            }}>
              {[
                { key: "1d", label: "1D" },
                { key: "1w", label: "1W" },
                { key: "1m", label: "1M" },
                { key: "3m", label: "3M" },
                { key: "1y", label: "1Y" },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setModalPeriod(key)}
                  style={{
                    padding: "5px 10px",
                    borderRadius: "7px",
                    border: "none",
                    cursor: "pointer",
                    fontFamily: "inherit",
                    fontWeight: 700,
                    fontSize: "0.75rem",
                    background: modalPeriod === key ? "var(--accent-dim)" : "transparent",
                    color: modalPeriod === key ? "var(--accent)" : "var(--filter-tab-inactive)",
                    transition: "all 0.2s",
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Error Message */}
            {modalError && (
              <div style={{
                background: "var(--red-dim)",
                border: "1px solid rgba(255, 23, 68, 0.2)",
                borderRadius: "12px",
                padding: "12px 16px",
                color: "var(--red)",
                fontSize: "0.85rem",
                fontWeight: 600,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
              }}>
                <span>⚠️</span>
                <span>{modalError}</span>
              </div>
            )}

            {/* Chart Block */}
            <div style={{ height: "300px", position: "relative", minHeight: "250px" }}>
              {modalLoading ? (
                <div style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "12px",
                  background: "rgba(0,0,0,0.1)",
                  borderRadius: "12px",
                }}>
                  <div className="spinner" style={{ width: "32px", height: "32px" }} />
                  <p style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>Loading stock chart...</p>
                </div>
              ) : modalHistory && modalHistory.length > 0 ? (
                <RealChart data={modalHistory} />
              ) : (
                <div style={{
                  height: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  border: "1px dashed var(--border-subtle)",
                  borderRadius: "12px",
                }}>
                  <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>No history data available for this period</p>
                </div>
              )}
            </div>

            {/* AI prediction details quick bar */}
            {modalPrediction && (
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                gap: "10px",
                background: "var(--input-bg)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "12px",
                padding: "12px",
              }}>
                <div>
                  <p style={{ fontSize: "0.62rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em", marginBottom: "4px" }}>
                    Current Price
                  </p>
                  <p style={{ fontSize: "1.1rem", fontWeight: 800, color: "var(--text-primary)", fontFamily: "'Space Grotesk', sans-serif" }}>
                    ₹{modalPrediction.current_price}
                  </p>
                </div>
                <div>
                  <p style={{ fontSize: "0.62rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em", marginBottom: "4px" }}>
                    Predicted Price (5-7 Day Target)
                  </p>
                  <p style={{
                    fontSize: "1.1rem",
                    fontWeight: 800,
                    color: modalPrediction.predicted_price >= modalPrediction.current_price ? "var(--green)" : "var(--red)",
                    fontFamily: "'Space Grotesk', sans-serif"
                  }}>
                    ₹{modalPrediction.predicted_price}
                  </p>
                </div>
                <div>
                  <p style={{ fontSize: "0.62rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em", marginBottom: "4px" }}>
                    Trend
                  </p>
                  <p style={{
                    fontSize: "1.1rem",
                    fontWeight: 800,
                    color: modalPrediction.trend === "BULLISH" ? "var(--green)" : modalPrediction.trend === "BEARISH" ? "var(--red)" : "var(--accent)",
                    fontFamily: "'Space Grotesk', sans-serif"
                  }}>
                    {modalPrediction.trend}
                  </p>
                </div>
                <div>
                  <p style={{ fontSize: "0.62rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em", marginBottom: "4px" }}>
                    Confidence
                  </p>
                  <p style={{
                    fontSize: "1.1rem",
                    fontWeight: 800,
                    color: modalPrediction.confidence >= 70 ? "var(--green)" : modalPrediction.confidence >= 55 ? "var(--gold)" : "var(--red)",
                    fontFamily: "'Space Grotesk', sans-serif"
                  }}>
                    {modalPrediction.confidence}%
                  </p>
                </div>
              </div>
            )}

            {/* Price Alerts Panel */}
            <div style={{
              background: "var(--input-bg)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "12px",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
              marginTop: "8px"
            }}>
              <p style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--accent)", textTransform: "uppercase", letterSpacing: "0.05em", margin: 0 }}>
                🔔 Set Price Alert
              </p>
              
              <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>Alert me when price goes</span>
                <select
                  value={alertCondition}
                  onChange={(e) => setAlertCondition(e.target.value)}
                  style={{
                    background: "var(--bg-secondary)",
                    color: "var(--text-primary)",
                    border: "1px solid var(--border-medium)",
                    borderRadius: "8px",
                    padding: "6px 10px",
                    fontSize: "0.8rem",
                    fontWeight: 600,
                  }}
                >
                  <option value="above">Above</option>
                  <option value="below">Below</option>
                </select>
                <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                  <span style={{ position: "absolute", left: "10px", fontSize: "0.82rem", color: "var(--text-muted)" }}>₹</span>
                  <input
                    type="number"
                    step="any"
                    value={alertTargetPrice}
                    onChange={(e) => setAlertTargetPrice(e.target.value)}
                    style={{
                      background: "var(--bg-secondary)",
                      color: "var(--text-primary)",
                      border: "1px solid var(--border-medium)",
                      borderRadius: "8px",
                      padding: "6px 10px 6px 22px",
                      fontSize: "0.8rem",
                      fontWeight: 600,
                      width: "120px",
                    }}
                  />
                </div>
                <button
                  onClick={handleCreateAlert}
                  className="btn-primary"
                  style={{ padding: "6px 12px", fontSize: "0.8rem", color: "var(--bg-primary)" }}
                >
                  Create Alert
                </button>
              </div>

              {/* Active Alerts for this Ticker */}
              {alerts.filter(a => a.symbol === normalizedActiveSymbol && a.is_active).length > 0 && (
                <div style={{ marginTop: "4px", borderTop: "1px solid var(--border-subtle)", paddingTop: "8px" }}>
                  <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600, margin: "0 0 6px 0" }}>Active Alerts:</p>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    {alerts.filter(a => a.symbol === normalizedActiveSymbol && a.is_active).map(a => (
                      <span key={a.id} style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        background: "var(--bg-secondary)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "6px",
                        padding: "3px 8px",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        color: "var(--text-primary)"
                      }}>
                        {a.condition.toUpperCase()} ₹{a.target_price}
                        <button
                          onClick={() => handleDeleteAlert(a.id)}
                          style={{
                            background: "transparent",
                            border: "none",
                            color: "var(--red)",
                            cursor: "pointer",
                            fontSize: "0.75rem",
                            padding: 0,
                            marginLeft: "4px",
                          }}
                        >
                          ✕
                        </button>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Actions */}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "4px" }}>
              <button
                onClick={() => setShowChartModal(false)}
                className="btn-ghost"
                style={{ padding: "8px 16px", fontSize: "0.8rem" }}
              >
                Close
              </button>
              <button
                onClick={() => {
                  setShowChartModal(false);
                  router.push(`/stock/${activeStockSymbol}`);
                }}
                className="btn-primary"
                style={{ padding: "8px 16px", fontSize: "0.8rem", color: "var(--bg-primary)" }}
              >
                View Full Analysis &rarr;
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
