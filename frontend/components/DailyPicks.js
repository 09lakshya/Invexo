import React, { useState, useEffect } from 'react';
import API from '../services/api';

export default function DailyPicks() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let interval;
    
    const fetchPicks = async () => {
      try {
        const res = await API.get('/predict/daily-picks');
        setData(res.data);
        if (res.data.status === "ready") {
          setLoading(false);
          clearInterval(interval);
        }
      } catch (err) {
        console.error("Failed to fetch daily picks:", err);
      }
    };

    fetchPicks();
    
    // Poll every 5 seconds if still generating
    interval = setInterval(() => {
      if (data?.status !== "ready") {
        fetchPicks();
      }
    }, 5000);
    
    return () => clearInterval(interval);
  }, [data?.status]);

  if (loading || data?.status === "updating") {
    return (
      <div style={{
        background: "var(--surface)",
        borderRadius: "20px",
        padding: "24px",
        boxShadow: "var(--shadow-card)",
        marginBottom: "32px",
        border: "1px solid var(--border)",
        position: "relative",
        overflow: "hidden"
      }}>
        <div style={{
          position: "absolute",
          top: 0, left: 0, right: 0, height: "3px",
          background: "linear-gradient(90deg, var(--accent), var(--purple), var(--accent))",
          backgroundSize: "200% 100%",
          animation: "shimmer 2s infinite linear"
        }} />
        <h2 style={{ fontSize: "1.2rem", fontWeight: 800, marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
          <span>✨</span> Daily AI Stock Picks
        </h2>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", marginBottom: "24px" }}>
          Our AI is currently crunching millions of data points to find today's best opportunities...
        </p>
        
        <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
          {[1, 2, 3].map((i) => (
            <div key={i} style={{
              flex: "1 1 300px",
              height: "120px",
              background: "var(--surface-hover)",
              borderRadius: "16px",
              animation: "pulse 1.5s infinite ease-in-out"
            }}></div>
          ))}
        </div>
      </div>
    );
  }

  if (!data?.picks || data.picks.length === 0) return null;

  return (
    <div style={{
      background: "var(--surface)",
      borderRadius: "20px",
      padding: "24px",
      boxShadow: "var(--shadow-card)",
      marginBottom: "32px",
      border: "1px solid var(--border)"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
        <h2 style={{ fontSize: "1.4rem", fontWeight: 800, display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: "var(--accent)" }}>✨</span> Daily AI Stock Picks
        </h2>
        <span style={{ fontSize: "0.75rem", background: "var(--purple-dim)", color: "var(--purple)", padding: "4px 8px", borderRadius: "8px", fontWeight: 700 }}>
          UPDATED TODAY
        </span>
      </div>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "24px" }}>
        Highly curated recommendations based on predictive XGBoost models, fundamental strength, and live market sentiment.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "16px" }}>
        {data.picks.map((pick, i) => (
          <div key={i} style={{
            background: "linear-gradient(145deg, var(--surface-hover), var(--surface))",
            border: "1px solid var(--border)",
            borderRadius: "16px",
            padding: "20px",
            transition: "transform 0.2s, box-shadow 0.2s",
            cursor: "pointer",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
            position: "relative",
            overflow: "hidden"
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = "translateY(-4px)";
            e.currentTarget.style.boxShadow = "0 12px 24px rgba(0,0,0,0.15)";
            e.currentTarget.style.borderColor = "var(--accent)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "none";
            e.currentTarget.style.boxShadow = "none";
            e.currentTarget.style.borderColor = "var(--border)";
          }}>
            {i === 0 && (
               <div style={{
                 position: "absolute", top: 0, right: 0,
                 background: "var(--accent)", color: "#fff",
                 fontSize: "0.65rem", fontWeight: 800, padding: "4px 12px",
                 borderBottomLeftRadius: "12px", letterSpacing: "0.05em"
               }}>
                 TOP PICK
               </div>
            )}
            
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <h3 style={{ fontSize: "1.2rem", fontWeight: 800, margin: 0 }}>{pick.symbol}</h3>
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 600 }}>{pick.full_symbol}</span>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "1.1rem", fontWeight: 700 }}>₹{pick.current_price?.toFixed(2)}</div>
                <div style={{ color: "var(--green)", fontSize: "0.85rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "4px", justifyContent: "flex-end" }}>
                  <span>↗</span> {pick.upside}% Upside
                </div>
              </div>
            </div>

            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "4px" }}>
              <span style={{ fontSize: "0.7rem", background: "var(--accent-dim)", color: "var(--accent)", padding: "4px 8px", borderRadius: "6px", fontWeight: 700 }}>
                Target: ₹{pick.target_price?.toFixed(2)}
              </span>
              <span style={{ fontSize: "0.7rem", background: "var(--surface-hover)", color: "var(--text-secondary)", padding: "4px 8px", borderRadius: "6px", fontWeight: 600 }}>
                {pick.sentiment} News
              </span>
              <span style={{ fontSize: "0.7rem", background: "var(--surface-hover)", color: "var(--text-secondary)", padding: "4px 8px", borderRadius: "6px", fontWeight: 600 }}>
                {pick.confidence} Confidence
              </span>
            </div>

            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5, margin: 0, marginTop: "4px", paddingLeft: "10px", borderLeft: "2px solid var(--border)" }}>
              {pick.reasoning}
            </p>
          </div>
        ))}
      </div>
      
      <style>{`
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
        @keyframes pulse {
          0% { opacity: 0.6; }
          50% { opacity: 0.3; }
          100% { opacity: 0.6; }
        }
      `}</style>
    </div>
  );
}
