import { useState, useEffect, useRef, useMemo } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import Head from "next/head";
import Navbar from "../../components/Navbar";
import RealChart from "../../components/RealChart";
import API from "../../services/api";
import { STOCK_METADATA } from "../../services/stocks";
import Icon from "../../components/Icon";
import CompanyLogo from "../../components/CompanyLogo";

// ── CLIENT-SIDE MATHEMATICAL CALCULATORS ────────────────────────────────────

const cleanHistoryData = (history) => {
  if (!Array.isArray(history)) return [];
  return history.map((d) => {
    if (!d) return null;
    const open = d.Open !== undefined && d.Open !== null ? Number(d.Open) : (d.open !== undefined && d.open !== null ? Number(d.open) : null);
    const high = d.High !== undefined && d.High !== null ? Number(d.High) : (d.high !== undefined && d.high !== null ? Number(d.high) : null);
    const low = d.Low !== undefined && d.Low !== null ? Number(d.Low) : (d.low !== undefined && d.low !== null ? Number(d.low) : null);
    const close = d.Close !== undefined && d.Close !== null ? Number(d.Close) : (d.close !== undefined && d.close !== null ? Number(d.close) : null);
    const date = d.Date || d.date;

    const finalClose = close !== null && !isNaN(close) ? close : null;
    const finalOpen = open !== null && !isNaN(open) ? open : finalClose;
    const finalHigh = high !== null && !isNaN(high) ? high : Math.max(finalOpen || 0, finalClose || 0);
    const finalLow = low !== null && !isNaN(low) ? low : Math.min(finalOpen || 999999, finalClose || 999999);

    return {
      Date: date,
      Open: finalOpen,
      High: finalHigh,
      Low: finalLow,
      Close: finalClose,
    };
  }).filter(
    (d) => d && d.Date && d.Close !== null && d.Open !== null && d.High !== null && d.Low !== null
  );
};

// Calculate Bollinger Bands: 20-period SMA, 2-stdDev limits
function calculateBollingerBands(history) {
  if (!history || history.length < 20) return null;
  const closes = history.map(d => d.Close);
  const n = closes.length;
  const period = 20;
  const slice = closes.slice(n - period);
  
  const sum = slice.reduce((a, b) => a + b, 0);
  const sma = sum / period;
  
  const variance = slice.reduce((a, b) => a + Math.pow(b - sma, 2), 0) / period;
  const stdDev = Math.sqrt(variance);
  
  const upper = sma + 2 * stdDev;
  const lower = sma - 2 * stdDev;
  const current = closes[n - 1];
  const percent = ((current - lower) / (upper - lower)) * 100;
  
  return {
    lower,
    middle: sma,
    upper,
    percent
  };
}

// Calculate ADX (Average Directional Index) - 14-period Wilder's Smoothing
function calculateADX(history) {
  if (!history || history.length < 28) return null;
  const tr = [];
  const plusDM = [];
  const minusDM = [];
  
  for (let i = 1; i < history.length; i++) {
    const curr = history[i];
    const prev = history[i - 1];
    
    const hL = curr.High - curr.Low;
    const hCp = Math.abs(curr.High - prev.Close);
    const lCp = Math.abs(curr.Low - prev.Close);
    const trueRange = Math.max(hL, hCp, lCp);
    tr.push(trueRange);
    
    const upMove = curr.High - prev.High;
    const downMove = prev.Low - curr.Low;
    
    if (upMove > downMove && upMove > 0) {
      plusDM.push(upMove);
    } else {
      plusDM.push(0);
    }
    
    if (downMove > upMove && downMove > 0) {
      minusDM.push(downMove);
    } else {
      minusDM.push(0);
    }
  }
  
  const period = 14;
  let smoothedTR = tr.slice(0, period).reduce((a, b) => a + b, 0);
  let smoothedPlusDM = plusDM.slice(0, period).reduce((a, b) => a + b, 0);
  let smoothedMinusDM = minusDM.slice(0, period).reduce((a, b) => a + b, 0);
  
  const dxValues = [];
  let plusDI = 100 * (smoothedPlusDM / (smoothedTR || 1));
  let minusDI = 100 * (smoothedMinusDM / (smoothedTR || 1));
  let dx = 100 * Math.abs(plusDI - minusDI) / ((plusDI + minusDI) || 1);
  dxValues.push(dx);
  
  for (let i = period; i < tr.length; i++) {
    smoothedTR = smoothedTR - (smoothedTR / period) + tr[i];
    smoothedPlusDM = smoothedPlusDM - (smoothedPlusDM / period) + plusDM[i];
    smoothedMinusDM = smoothedMinusDM - (smoothedMinusDM / period) + minusDM[i];
    
    plusDI = 100 * (smoothedPlusDM / (smoothedTR || 1));
    minusDI = 100 * (smoothedMinusDM / (smoothedTR || 1));
    dx = 100 * Math.abs(plusDI - minusDI) / ((plusDI + minusDI) || 1);
    dxValues.push(dx);
  }
  
  if (dxValues.length < period) return null;
  
  let adx = dxValues.slice(0, period).reduce((a, b) => a + b, 0) / period;
  for (let i = period; i < dxValues.length; i++) {
    adx = (adx * (period - 1) + dxValues[i]) / period;
  }
  
  return {
    adx,
    plusDI,
    minusDI
  };
}

export default function StockDetail() {
  const router = useRouter();
  const { symbol } = router.query;

  const [predictionData, setPredictionData] = useState(null);
  const [chartHistory, setChartHistory] = useState([]);
  const [chartPeriod, setChartPeriod] = useState("3m"); // default 3mo period
  
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(true);
  const [error, setError] = useState(null);
  const [watchlist, setWatchlist] = useState([]);

  const cleanSymbol = useMemo(() => {
    return symbol ? symbol.toUpperCase().replace(/\.NS$/i, "").replace(/\.BO$/i, "") : "";
  }, [symbol]);

  const companyName = useMemo(() => {
    return STOCK_METADATA[cleanSymbol]?.name || cleanSymbol;
  }, [cleanSymbol]);

  const querySymbol = useMemo(() => {
    return cleanSymbol ? `${cleanSymbol}.NS` : "";
  }, [cleanSymbol]);

  // Client-side computed indicators from 3-month history
  const [indicators, setIndicators] = useState({
    bollinger: null,
    adx: null
  });

  const getPeriodFormat = (p) => {
    const PERIODS = [
      { key: "1d", yf: "1d" },
      { key: "1w", yf: "5d" },
      { key: "1m", yf: "1mo" },
      { key: "3m", yf: "3mo" },
      { key: "6m", yf: "6mo" },
      { key: "1y", yf: "1y" },
    ];
    return PERIODS.find(x => x.key === p)?.yf || p;
  };

  // Fetch watchlist
  const fetchWatchlist = async () => {
    try {
      const res = await API.get("/watchlist/");
      setWatchlist(res.data.map(item => item.symbol.toUpperCase()));
    } catch (err) {
      console.error("Failed to fetch watchlist:", err);
    }
  };

  const toggleWatchlist = async () => {
    if (!cleanSymbol) return;
    const isWatched = watchlist.includes(cleanSymbol);
    try {
      if (isWatched) {
        await API.delete(`/watchlist/${cleanSymbol}`);
        setWatchlist(prev => prev.filter(s => s !== cleanSymbol));
      } else {
        await API.post("/watchlist/", { symbol: cleanSymbol });
        setWatchlist(prev => [...prev, cleanSymbol]);
      }
    } catch (err) {
      console.error("Failed to toggle watchlist:", err);
    }
  };

  // Load prediction data and stable indicators (using 3-month history) on mount
  useEffect(() => {
    if (!symbol) return;

    const loadCoreData = async () => {
      setLoading(true);
      setError(null);
      try {
        await fetchWatchlist();
        
        // Fetch AI prediction
        const predRes = await API.get(`/predict/${querySymbol}`);
        if (predRes.data && predRes.data.error) {
          throw new Error(predRes.data.error);
        }
        setPredictionData(predRes.data);

        // Fetch stable 3-month history to compute Bollinger Bands & ADX
        const histRes = await API.get(`/market/${cleanSymbol}/history?period=3mo`);
        const histData = cleanHistoryData(histRes.data);
        
        const bb = calculateBollingerBands(histData);
        const adx = calculateADX(histData);
        setIndicators({ bollinger: bb, adx: adx });
        
        // Initially set the chart history to this loaded 3-month history
        setChartHistory(histData);
        setChartLoading(false);
      } catch (err) {
        console.error("Failed to load stock data:", err);
        console.error("Core data fetch error details:", err.response?.data || err.message);
        const detailedMsg = err.response?.data?.detail || err.response?.data?.error || err.message;
        setError(detailedMsg || "Technical analysis data currently unavailable. The market may be closed.");
      } finally {
        setLoading(false);
      }
    };

    loadCoreData();
  }, [symbol, querySymbol, cleanSymbol]);

  // Reload history only for chart when timeframe is changed
  useEffect(() => {
    if (!symbol || loading) return;

    // Skip reload if timeframe is 3M (which matches core data)
    if (chartPeriod === "3m") return;

    const loadTimeframeHistory = async () => {
      setChartLoading(true);
      try {
        const histRes = await API.get(`/market/${cleanSymbol}/history?period=${getPeriodFormat(chartPeriod)}`);
        setChartHistory(cleanHistoryData(histRes.data));
      } catch (err) {
        console.error("Failed to load timeframe history:", err);
      } finally {
        setChartLoading(false);
      }
    };

    loadTimeframeHistory();
  }, [chartPeriod, symbol, cleanSymbol, loading]);

  // Re-sync chart with 3-month history if timeframe returns to 3M
  useEffect(() => {
    if (chartPeriod === "3m" && !loading) {
      const reloadDefaultHistory = async () => {
        setChartLoading(true);
        try {
          const histRes = await API.get(`/market/${cleanSymbol}/history?period=3mo`);
          setChartHistory(cleanHistoryData(histRes.data));
        } catch (err) {
          console.error(err);
        } finally {
          setChartLoading(false);
        }
      };
      reloadDefaultHistory();
    }
  }, [chartPeriod]);

  const isWatched = watchlist.includes(cleanSymbol);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "70vh", gap: "16px" }}>
          <div className="spinner" />
          <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem", fontWeight: 500 }}>Analysing market datasets for {cleanSymbol}...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />
        <div style={{ maxWidth: "800px", margin: "80px auto", padding: "0 20px" }}>
          <div className="glass" style={{ padding: "40px", textAlign: "center", display: "flex", flexDirection: "column", gap: "20px", border: "1px solid var(--red-dim)" }}>
            <p style={{ margin: 0, color: "var(--red)", display: "flex", justifyContent: "center" }}><Icon name="alert" size={44} strokeWidth={1.75} /></p>
            <h2 style={{ fontFamily: "Space Grotesk, sans-serif", fontWeight: 800 }}>Analysis Failed</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem", lineHeight: 1.6 }}>{error}</p>
            <div style={{ display: "flex", gap: "12px", justifyContent: "center", marginTop: "10px" }}>
              <Link href="/" className="btn-primary" style={{ padding: "12px 24px", color: "var(--bg-primary)" }}>
                Return to Dashboard
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const currentPrice = predictionData?.current_price || 0;
  const change = predictionData?.change || 0;
  const percentChange = predictionData?.percent_change || 0;
  const isPositive = change >= 0;

  // Trend Badge styles
  const trend = predictionData?.trend || "NEUTRAL";
  const trendColor = trend === "BULLISH" ? "var(--green)" : trend === "BEARISH" ? "var(--red)" : "var(--accent)";
  const trendBg = trend === "BULLISH" ? "var(--green-dim)" : trend === "BEARISH" ? "var(--red-dim)" : "var(--accent-dim)";

  // RSI Styling
  const rsi = predictionData?.rsi || 50;
  const rsiLabel = rsi >= 70 ? "Overbought" : rsi <= 30 ? "Oversold" : "Neutral";
  const rsiColor = rsi >= 70 ? "var(--red)" : rsi <= 30 ? "var(--green)" : "var(--accent)";

  // MACD styling
  const macd = predictionData?.macd || 0;
  const macdLabel = macd > 0 ? "Bullish Crossover" : macd < 0 ? "Bearish Divergence" : "Neutral";
  const macdColor = macd > 0 ? "var(--green)" : macd < 0 ? "var(--red)" : "var(--text-muted)";

  // ADX strength rating
  const adxVal = indicators.adx?.adx || 0;
  const adxLabel = adxVal >= 50 ? "Very Strong Trend" : adxVal >= 25 ? "Strong Trend" : adxVal >= 20 ? "Developing Trend" : "Weak/No Trend";
  const adxColor = adxVal >= 25 ? "var(--green)" : adxVal >= 20 ? "var(--gold)" : "var(--text-muted)";

  // News sentiment
  const newsSentiment = predictionData?.news_sentiment || 50;
  const newsImpact = predictionData?.news_impact || "neutral";
  const newsCount = predictionData?.news_count || 0;
  const sentimentColor = newsSentiment > 55 ? "var(--green)" : newsSentiment < 45 ? "var(--red)" : "var(--accent)";

  return (
    <>
      <Head>
        <title>{cleanSymbol} Analysis — Invexo</title>
        <meta name="description" content={`Real-time AI prediction, chart, technical indicators and fundamentals for ${companyName} (${cleanSymbol}).`} />
      </Head>

      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />

        <div className="page-wrapper" style={{ display: "flex", flexDirection: "column", gap: "var(--section-gap)" }}>
          
          {/* Navigation and Title Row */}
          <div style={{ display: "flex", flexDirection: "column", gap: "16px", animation: "fadeInUp 0.5s ease" }}>
            <div>
              <Link href="/" className="btn-ghost" style={{ padding: "8px 16px", borderRadius: "10px", fontSize: "0.82rem", display: "inline-flex", alignItems: "center", gap: "6px" }}>
                <span>&larr;</span> Back to Dashboard
              </Link>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                <CompanyLogo symbol={cleanSymbol} size={48} radius={10} fontSize="1.3rem" />
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <h1 style={{ fontFamily: "Space Grotesk, sans-serif", fontSize: "clamp(1.5rem, 3.5vw, 2.2rem)", fontWeight: 800, margin: 0, color: "var(--text-primary)", letterSpacing: "-0.02em" }}>
                      {companyName}
                    </h1>
                    <button
                      onClick={toggleWatchlist}
                      style={{
                        background: "transparent",
                        border: "none",
                        cursor: "pointer",
                        fontSize: "1.4rem",
                        color: isWatched ? "var(--gold)" : "var(--text-muted)",
                        transition: "color 0.2s",
                        padding: "4px"
                      }}
                      title={isWatched ? "Remove from watchlist" : "Add to watchlist"}
                    >
                      <Icon name="star" filled={isWatched} size={18} />
                    </button>
                  </div>
                  <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", fontWeight: 500, margin: "2px 0 0 0" }}>
                    NSE: {cleanSymbol} · Real-time Analytics
                  </p>
                </div>
              </div>

              {/* Price Details */}
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "clamp(1.6rem, 4vw, 2.4rem)", fontWeight: 900, fontFamily: "Space Grotesk, sans-serif", color: "var(--text-primary)", letterSpacing: "-0.02em" }}>
                  ₹{currentPrice.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </div>
                <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end", alignItems: "center", marginTop: "4px" }}>
                  <span style={{
                    padding: "3px 8px",
                    borderRadius: "20px",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    background: isPositive ? "var(--green-dim)" : "var(--red-dim)",
                    color: isPositive ? "var(--green)" : "var(--red)",
                  }}>
                    {isPositive ? "\u25B2" : "\u25BC"} {isPositive ? "+" : ""}{change.toFixed(2)} ({isPositive ? "+" : ""}{percentChange.toFixed(2)}%)
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Candlestick Chart Area */}
          <div className="glass" style={{ padding: "var(--card-padding)", animation: "fadeInUp 0.5s 0.05s ease both" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
              <h2 style={{ fontFamily: "Space Grotesk, sans-serif", fontSize: "1.1rem", fontWeight: 700, margin: 0 }}>
                Price History & Charting
              </h2>
              
              {/* Chart Period Selector */}
              <div style={{
                display: "flex",
                gap: "4px",
                background: "var(--filter-tab-bg)",
                border: "1px solid var(--filter-tab-border)",
                borderRadius: "10px",
                padding: "3px",
              }}>
                {[
                  { key: "1d", label: "1D" },
                  { key: "1w", label: "1W" },
                  { key: "1m", label: "1M" },
                  { key: "3m", label: "3M" },
                  { key: "6m", label: "6M" },
                  { key: "1y", label: "1Y" },
                ].map(({ key, label }) => (
                  <button
                    key={key}
                    onClick={() => setChartPeriod(key)}
                    style={{
                      padding: "5px 12px",
                      borderRadius: "7px",
                      border: "none",
                      cursor: "pointer",
                      fontFamily: "inherit",
                      fontWeight: 700,
                      fontSize: "0.75rem",
                      background: chartPeriod === key ? "var(--accent-dim)" : "transparent",
                      color: chartPeriod === key ? "var(--accent)" : "var(--filter-tab-inactive)",
                      transition: "all 0.2s",
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ height: "420px", position: "relative", overflow: "hidden" }}>
              {chartLoading ? (
                <div style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "12px",
                  background: "rgba(0,0,0,0.15)",
                  borderRadius: "12px"
                }}>
                  <div className="spinner" />
                  <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Loading financial candlesticks...</p>
                </div>
              ) : chartHistory && chartHistory.length > 0 ? (
                <RealChart data={chartHistory} />
              ) : (
                <div style={{
                  height: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  border: "1px dashed var(--border-subtle)",
                  borderRadius: "12px",
                }}>
                  <p style={{ color: "var(--text-muted)" }}>Chart unavailable for this period.</p>
                </div>
              )}
            </div>
          </div>

          {/* Grid Layout for Panels */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(450px, 100%), 1fr))",
            gap: "var(--section-gap)",
            animation: "fadeInUp 0.5s 0.1s ease both"
          }}>
            
            {/* PANEL 1: AI Prediction Panel */}
            <div className="glass" style={{ padding: "var(--card-padding)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px" }}>
                <p className="section-label" style={{ margin: 0, display: "flex", alignItems: "center", gap: "7px" }}><Icon name="bot" size={15} /> AI Prediction Model</p>
                <span className="badge" style={{ background: trendBg, color: trendColor }}>
                  {trend}
                </span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "20px" }}>
                <div style={{ background: "var(--input-bg)", border: "1px solid var(--border-subtle)", padding: "12px 16px", borderRadius: "12px" }}>
                  <p style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em", marginBottom: "4px" }}>
                    Current Price
                  </p>
                  <p style={{ fontSize: "1.3rem", fontWeight: 800, fontFamily: "Space Grotesk, sans-serif" }}>
                    ₹{currentPrice.toFixed(2)}
                  </p>
                </div>

                <div style={{ background: "var(--input-bg)", border: "1px solid var(--border-subtle)", padding: "12px 16px", borderRadius: "12px" }}>
                  <p style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em", marginBottom: "4px" }}>
                    Predicted Price (5-7D Target)
                  </p>
                  <p style={{ fontSize: "1.3rem", fontWeight: 800, fontFamily: "Space Grotesk, sans-serif", color: predictionData?.predicted_price >= currentPrice ? "var(--green)" : "var(--red)" }}>
                    ₹{predictionData?.predicted_price ? predictionData.predicted_price.toFixed(2) : "—"}
                  </p>
                </div>

                <div style={{ background: "var(--input-bg)", border: "1px solid var(--border-subtle)", padding: "12px 16px", borderRadius: "12px" }}>
                  <p style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em", marginBottom: "4px" }}>
                    XGBoost Prediction
                  </p>
                  <p style={{ fontSize: "1.3rem", fontWeight: 800, fontFamily: "Space Grotesk, sans-serif", color: predictionData?.xgb_predicted_price >= currentPrice ? "var(--green)" : "var(--red)" }}>
                    {predictionData?.xgb_predicted_price ? `₹${predictionData.xgb_predicted_price.toFixed(2)}` : "Unavailable"}
                  </p>
                </div>

                <div style={{ background: "var(--input-bg)", border: "1px solid var(--border-subtle)", padding: "12px 16px", borderRadius: "12px" }}>
                  <p style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em", marginBottom: "4px" }}>
                    Model Confidence
                  </p>
                  <p style={{ fontSize: "1.3rem", fontWeight: 800, fontFamily: "Space Grotesk, sans-serif", color: predictionData?.confidence >= 70 ? "var(--green)" : predictionData?.confidence >= 55 ? "var(--gold)" : "var(--red)" }}>
                    {predictionData?.confidence || 0}%
                  </p>
                </div>
              </div>

              {/* Explanatory summary text */}
              {predictionData?.explanation?.summary && (
                <div style={{ background: "var(--hover-overlay)", border: "1px solid var(--border-subtle)", borderRadius: "12px", padding: "14px" }}>
                  <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.5, margin: 0 }}>
                    {predictionData.explanation.summary}
                  </p>
                  
                  {/* SHAP values display */}
                  {predictionData?.explanation?.shap_values && (
                    <div style={{ marginTop: "12px", borderTop: "1px solid var(--border-subtle)", paddingTop: "10px" }}>
                      <p style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "8px" }}>SHAP Driver Impacts</p>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                        {Object.entries(predictionData.explanation.shap_values).map(([feature, weight]) => {
                          const isPos = weight >= 0;
                          return (
                            <span key={feature} style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "4px",
                              background: "var(--bg-primary)",
                              border: "1px solid var(--border-subtle)",
                              borderRadius: "6px",
                              padding: "4px 8px",
                              fontSize: "0.72rem",
                              fontWeight: 600,
                              color: "var(--text-secondary)"
                            }}>
                              {feature}: <strong style={{ color: isPos ? "var(--green)" : "var(--red)" }}>{isPos ? "+" : ""}{weight.toFixed(2)}</strong>
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* PANEL 2: Technical Indicators Panel */}
            <div className="glass" style={{ padding: "var(--card-padding)" }}>
              <p className="section-label" style={{ marginBottom: "18px", display: "flex", alignItems: "center", gap: "7px" }}><Icon name="bar-chart" size={15} /> Technical Indicators</p>

              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                {/* RSI Gauge */}
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <span style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-secondary)" }}>Relative Strength Index (RSI-14)</span>
                    <span style={{ fontSize: "0.78rem", fontWeight: 800, color: rsiColor }}>{rsi.toFixed(1)} ({rsiLabel})</span>
                  </div>
                  <div style={{ height: "8px", background: "var(--border-subtle)", borderRadius: "4px", position: "relative" }}>
                    {/* Zones markings */}
                    <div style={{ position: "absolute", left: "30%", top: 0, bottom: 0, width: "1px", background: "var(--border-medium)" }} title="Oversold limit (30)" />
                    <div style={{ position: "absolute", left: "70%", top: 0, bottom: 0, width: "1px", background: "var(--border-medium)" }} title="Overbought limit (70)" />
                    {/* Fill */}
                    <div style={{
                      position: "absolute",
                      left: 0,
                      width: `${rsi}%`,
                      height: "100%",
                      background: `linear-gradient(90deg, var(--green) 0%, var(--accent) 50%, var(--red) 100%)`,
                      borderRadius: "4px",
                      opacity: 0.8
                    }} />
                    {/* Handle indicator */}
                    <div style={{
                      position: "absolute",
                      left: `calc(${rsi}% - 5px)`,
                      top: "-3px",
                      width: "10px",
                      height: "14px",
                      background: "#fff",
                      borderRadius: "2px",
                      boxShadow: "0 2px 6px rgba(0,0,0,0.5)"
                    }} />
                  </div>
                </div>

                {/* MACD Histogram */}
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <span style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-secondary)" }}>MACD Histogram / Diff</span>
                    <span style={{ fontSize: "0.78rem", fontWeight: 800, color: macdColor }}>{macd.toFixed(4)} ({macdLabel})</span>
                  </div>
                  <div style={{ display: "flex", gap: "2px", height: "14px", alignItems: "center" }}>
                    {/* Simulated visual bar */}
                    <div style={{ flex: 1, height: "4px", background: macd < 0 ? "var(--red)" : "var(--border-subtle)", borderRadius: "2px", opacity: 0.7 }} />
                    <div style={{ width: "2px", height: "100%", background: "var(--text-muted)" }} />
                    <div style={{ flex: 1, height: "4px", background: macd > 0 ? "var(--green)" : "var(--border-subtle)", borderRadius: "2px", opacity: 0.7 }} />
                  </div>
                </div>

                {/* Bollinger Bands Position Indicator */}
                {indicators.bollinger ? (
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                      <span style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-secondary)" }}>Bollinger Bands Position</span>
                      <span style={{ fontSize: "0.78rem", fontWeight: 800, color: "var(--accent)" }}>{indicators.bollinger.percent.toFixed(1)}% of Band width</span>
                    </div>
                    {/* Bands Slider */}
                    <div style={{ height: "6px", background: "var(--border-subtle)", borderRadius: "3px", position: "relative", margin: "10px 0" }}>
                      <div style={{ position: "absolute", left: `calc(${Math.max(0, Math.min(100, indicators.bollinger.percent))}% - 4px)`, top: "-4px", width: "8px", height: "14px", borderRadius: "3px", background: "var(--accent)" }} />
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.68rem", color: "var(--text-muted)" }}>
                      <span>Lower: ₹{indicators.bollinger.lower.toFixed(1)}</span>
                      <span>Middle: ₹{indicators.bollinger.middle.toFixed(1)}</span>
                      <span>Upper: ₹{indicators.bollinger.upper.toFixed(1)}</span>
                    </div>
                  </div>
                ) : (
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Computing Bollinger Bands from price series...</div>
                )}

                {/* ADX Strength Bar */}
                {indicators.adx ? (
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                      <span style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-secondary)" }}>Trend Strength (ADX-14)</span>
                      <span style={{ fontSize: "0.78rem", fontWeight: 800, color: adxColor }}>{adxVal.toFixed(1)} ({adxLabel})</span>
                    </div>
                    <div style={{ height: "8px", background: "var(--border-subtle)", borderRadius: "4px", overflow: "hidden" }}>
                      <div style={{
                        width: `${Math.min(100, (adxVal / 60) * 100)}%`, // Map 0-60 to 0-100% progress
                        height: "100%",
                        background: `linear-gradient(90deg, var(--accent) 0%, ${adxColor} 100%)`,
                        borderRadius: "4px"
                      }} />
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "4px" }}>
                      <span>DI+: {indicators.adx.plusDI.toFixed(1)}</span>
                      <span>DI-: {indicators.adx.minusDI.toFixed(1)}</span>
                    </div>
                  </div>
                ) : (
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Computing ADX index series...</div>
                )}
              </div>
            </div>

            {/* PANEL 3: News Sentiment Panel */}
            <div className="glass" style={{ padding: "var(--card-padding)" }}>
              <p className="section-label" style={{ marginBottom: "18px", display: "flex", alignItems: "center", gap: "7px" }}><Icon name="news" size={15} /> News &amp; Public Sentiment</p>

              <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <p style={{ fontSize: "1.8rem", fontWeight: 900, fontFamily: "Space Grotesk, sans-serif", color: sentimentColor, margin: 0 }}>
                      {newsSentiment.toFixed(1)}
                    </p>
                    <p style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", margin: "2px 0 0 0" }}>
                      Public Sentiment Index
                    </p>
                  </div>

                  <div style={{ textAlign: "right" }}>
                    <span className="badge" style={{
                      background: newsImpact === "bullish" || newsImpact === "positive" ? "var(--green-dim)" : newsImpact === "bearish" || newsImpact === "negative" ? "var(--red-dim)" : "var(--accent-dim)",
                      color: newsImpact === "bullish" || newsImpact === "positive" ? "var(--green)" : newsImpact === "bearish" || newsImpact === "negative" ? "var(--red)" : "var(--accent)"
                    }}>
                      {newsImpact} impact
                    </span>
                    <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px", margin: 0 }}>
                      From {newsCount} media articles
                    </p>
                  </div>
                </div>

                {/* Sentiment Progress Gauge */}
                <div>
                  <div style={{ height: "8px", background: "var(--border-subtle)", borderRadius: "4px", overflow: "hidden" }}>
                    <div style={{
                      width: `${newsSentiment}%`,
                      height: "100%",
                      background: `linear-gradient(90deg, var(--red) 0%, var(--accent) 50%, var(--green) 100%)`,
                      borderRadius: "4px"
                    }} />
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "4px" }}>
                    <span>Negative Sentiment</span>
                    <span>Neutral</span>
                    <span>Positive Sentiment</span>
                  </div>
                </div>

                <div style={{ background: "var(--hover-overlay)", border: "1px solid var(--border-subtle)", borderRadius: "12px", padding: "12px 14px", fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.45 }}>
                  <Icon name="target" size={15} style={{ verticalAlign: "-2px", marginRight: "4px" }} /><strong>Impact Assessment:</strong> Media analysis shows a <strong>{newsImpact}</strong> tone across articles. Current sentiment exerts a <strong>{newsSentiment > 55 ? "positive pull" : newsSentiment < 45 ? "negative resistance" : "neutral effect"}</strong> on short-term price momentum.
                </div>
              </div>
            </div>

            {/* PANEL 4: Fundamentals Panel */}
            <div className="glass" style={{ padding: "var(--card-padding)" }}>
              <p className="section-label" style={{ marginBottom: "18px", display: "flex", alignItems: "center", gap: "7px" }}><Icon name="bar-chart" size={15} /> Financial Fundamentals</p>

              <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <p style={{ fontSize: "1.8rem", fontWeight: 900, fontFamily: "Space Grotesk, sans-serif", color: "var(--accent)", margin: 0 }}>
                      {predictionData?.fundamental_score ? predictionData.fundamental_score.toFixed(1) : "—"}
                    </p>
                    <p style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", margin: "2px 0 0 0" }}>
                      Fundamental Quality Score
                    </p>
                  </div>
                  
                  <span className="badge" style={{
                    background: predictionData?.fundamental_score >= 60 ? "var(--green-dim)" : predictionData?.fundamental_score >= 45 ? "var(--accent-dim)" : "var(--red-dim)",
                    color: predictionData?.fundamental_score >= 60 ? "var(--green)" : predictionData?.fundamental_score >= 45 ? "var(--accent)" : "var(--red)"
                  }}>
                    {predictionData?.fundamental_score >= 60 ? "Strong Value" : predictionData?.fundamental_score >= 45 ? "Neutral Value" : "Weak Value"}
                  </span>
                </div>

                {/* Score Progress Bar */}
                <div style={{ height: "6px", background: "var(--border-subtle)", borderRadius: "3px", overflow: "hidden" }}>
                  <div style={{
                    width: `${predictionData?.fundamental_score || 50}%`,
                    height: "100%",
                    background: "linear-gradient(90deg, var(--accent) 0%, var(--purple) 100%)",
                    borderRadius: "3px"
                  }} />
                </div>

                {/* Fundamental Metrics list */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div style={{ background: "var(--input-bg)", padding: "10px 14px", borderRadius: "10px", border: "1px solid var(--border-subtle)" }}>
                    <p style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.04em", marginBottom: "4px" }}>P/E Ratio</p>
                    <p style={{ fontSize: "1.05rem", fontWeight: 800, margin: 0 }}>
                      {predictionData?.pe_ratio !== null && predictionData?.pe_ratio !== undefined ? predictionData.pe_ratio.toFixed(2) : "N/A"}
                    </p>
                  </div>

                  <div style={{ background: "var(--input-bg)", padding: "10px 14px", borderRadius: "10px", border: "1px solid var(--border-subtle)" }}>
                    <p style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.04em", marginBottom: "4px" }}>Fundamental Source</p>
                    <p style={{ fontSize: "1.05rem", fontWeight: 800, margin: 0, textTransform: "capitalize", color: "var(--text-secondary)" }}>
                      {predictionData?.fundamental_source ? predictionData.fundamental_source.replace("_", " ") : "N/A"}
                    </p>
                  </div>

                  <div style={{ background: "var(--input-bg)", padding: "10px 14px", borderRadius: "10px", border: "1px solid var(--border-subtle)" }}>
                    <p style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.04em", marginBottom: "4px" }}>Earnings Growth</p>
                    <p style={{ fontSize: "1.05rem", fontWeight: 800, margin: 0, color: predictionData?.earnings_growth >= 0 ? "var(--green)" : "var(--red)" }}>
                      {predictionData?.earnings_growth !== null && predictionData?.earnings_growth !== undefined ? `${(predictionData.earnings_growth * 100).toFixed(1)}%` : "N/A"}
                    </p>
                  </div>

                  <div style={{ background: "var(--input-bg)", padding: "10px 14px", borderRadius: "10px", border: "1px solid var(--border-subtle)" }}>
                    <p style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.04em", marginBottom: "4px" }}>Revenue Growth</p>
                    <p style={{ fontSize: "1.05rem", fontWeight: 800, margin: 0, color: predictionData?.revenue_growth >= 0 ? "var(--green)" : "var(--red)" }}>
                      {predictionData?.revenue_growth !== null && predictionData?.revenue_growth !== undefined ? `${(predictionData.revenue_growth * 100).toFixed(1)}%` : "N/A"}
                    </p>
                  </div>
                </div>
              </div>
            </div>

          </div>

          {/* Bottom disclaimer */}
          <div style={{ textAlign: "center", marginTop: "16px", marginBottom: "48px" }}>
            <p style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 500 }}>
              All algorithmic models, indicators and forecast projections are for informational purposes only. Past performance does not guarantee future market returns. Invest responsibly.
            </p>
          </div>

        </div>
      </div>
    </>
  );
}
