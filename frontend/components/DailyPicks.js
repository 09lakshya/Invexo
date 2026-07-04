import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import API from '../services/api';

export default function DailyPicks() {
  const [activeTab, setActiveTab] = useState('large_cap');

  const { data, isLoading } = useQuery({
    queryKey: ['daily-picks'],
    queryFn: async () => {
      const res = await API.get('/predict/daily-picks');
      return res.data;
    },
    refetchInterval: (query) => {
      return query.state.data?.status !== "ready" ? 5000 : false;
    }
  });

  const loading = isLoading || data?.status === "updating";
  if (loading) {
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
          top: 0, left: 0, right: 0, height: "2px",
          background: "var(--accent)",
          opacity: 0.6,
          animation: "skeletonPulse 1.6s ease-in-out infinite"
        }} />
        <h2 style={{ fontSize: "1.2rem", fontWeight: 800, marginBottom: "8px" }}>
          Daily Edge
        </h2>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", marginBottom: "24px" }}>
          Ranking 253 liquid NSE stocks — 100 large, 94 mid &amp; 59 small cap — on today&apos;s prices…
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

  if (!data?.picks) return null;

  // Determine picks array based on format
  const isOldFormat = Array.isArray(data.picks);
  const currentPicks = isOldFormat ? data.picks : (data.picks[activeTab] || []);

  if (currentPicks.length === 0) return null;

  const tabs = [
    { id: 'large_cap', label: 'Large Cap' },
    { id: 'mid_cap', label: 'Mid Cap' },
    { id: 'small_cap', label: 'Small Cap' }
  ];

  const topPicks = !isOldFormat && data.picks.large_cap && data.picks.mid_cap && data.picks.small_cap ? [
    { category: "Large Cap", ...data.picks.large_cap[0] },
    { category: "Mid Cap", ...data.picks.mid_cap[0] },
    { category: "Small Cap", ...data.picks.small_cap[0] }
  ].filter(p => p.symbol) : [];

  return (
    <div style={{
      background: "var(--surface)",
      borderRadius: "20px",
      padding: "24px",
      boxShadow: "var(--shadow-card)",
      marginBottom: "32px",
      border: "1px solid var(--border)"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <h2 style={{ fontSize: "1.4rem", fontWeight: 800, marginBottom: "4px" }}>
            Daily Edge
          </h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", margin: 0 }}>
            A cross-sectional XGBoost model ranks 253 NSE stocks each day by their odds of out-performing over the next 5 sessions.
          </p>
        </div>
        <span style={{ fontSize: "0.75rem", background: "var(--purple-dim)", color: "var(--purple)", padding: "4px 8px", borderRadius: "8px", fontWeight: 700 }}>
          UPDATED TODAY
        </span>
      </div>


      {!isOldFormat && (
        <div style={{ 
          display: "flex", 
          gap: "8px", 
          marginBottom: "24px", 
          background: "var(--surface-hover)", 
          padding: "4px", 
          borderRadius: "12px", 
          width: "fit-content" 
        }}>
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: "8px 16px",
                borderRadius: "8px",
                border: "none",
                background: activeTab === tab.id ? "var(--accent)" : "transparent",
                color: activeTab === tab.id ? "#fff" : "var(--text-secondary)",
                fontWeight: 700,
                fontSize: "0.85rem",
                cursor: "pointer",
                transition: "all 0.2s"
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "16px" }}>
        {currentPicks.map((pick, i) => (
          <div key={i} style={{
            background: "linear-gradient(145deg, var(--surface-hover), var(--surface))",
            border: "1px solid rgba(255,255,255,0.08)",
            boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
            borderRadius: "16px",
            padding: "20px",
            transition: "transform 0.2s, box-shadow 0.2s, border-color 0.2s",
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
            e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.1)";
            e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)";
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
                {pick.expected_5d_pct !== undefined ? "5-Day" : "1-Day"} Target: ₹{pick.target_price?.toFixed(2)}
              </span>
              {pick.signal_1d ? (
                <span style={{ fontSize: "0.7rem", background: "var(--surface-hover)", color: pick.signal_1d === "Bullish" ? "var(--green)" : pick.signal_1d === "Bearish" ? "var(--red)" : "var(--text-secondary)", padding: "4px 8px", borderRadius: "6px", fontWeight: 600 }}>
                  {pick.signal_1d} 1-Day Signal
                </span>
              ) : pick.sentiment ? (
                <span style={{ fontSize: "0.7rem", background: "var(--surface-hover)", color: "var(--text-secondary)", padding: "4px 8px", borderRadius: "6px", fontWeight: 600 }}>
                  {pick.sentiment} News
                </span>
              ) : null}
              {pick.lift_5d ? (
                <span style={{ fontSize: "0.7rem", background: "var(--purple-dim)", color: "var(--purple)", padding: "4px 8px", borderRadius: "6px", fontWeight: 700 }}>
                  {pick.lift_5d}× Edge vs Avg
                </span>
              ) : pick.confidence ? (
                <span style={{ fontSize: "0.7rem", background: "var(--purple-dim)", color: "var(--purple)", padding: "4px 8px", borderRadius: "6px", fontWeight: 700 }}>
                  {pick.confidence}% Confidence
                </span>
              ) : null}
            </div>

            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5, margin: 0, marginTop: "4px", paddingLeft: "10px", borderLeft: "2px solid rgba(255,255,255,0.1)" }}>
              {pick.reasoning}
            </p>
          </div>
        ))}
      </div>

      {topPicks.length > 0 && (
        <div style={{ marginTop: "40px", paddingTop: "24px", borderTop: "1px solid rgba(255,255,255,0.05)" }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: "16px", color: "var(--text-primary)" }}>
            Picks for Tomorrow
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px" }}>
            {topPicks.map((pick, i) => (
              <div key={i} style={{
                background: "linear-gradient(135deg, var(--surface-hover), var(--surface))",
                border: "1px solid var(--border)",
                boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                borderRadius: "12px",
                padding: "12px",
                position: "relative",
                display: "flex",
                flexDirection: "column",
                gap: "6px"
              }}>
                <div style={{ fontSize: "0.65rem", fontWeight: 800, color: "var(--accent)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  {pick.category} Top Pick
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <div style={{ fontSize: "1rem", fontWeight: 800 }}>{pick.symbol}</div>
                    <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>{pick.full_symbol}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: "0.9rem", fontWeight: 700 }}>₹{pick.current_price?.toFixed(2)}</div>
                    <div style={{ color: "var(--green)", fontSize: "0.75rem", fontWeight: 700 }}>
                      ↗ {pick.upside}%
                    </div>
                    {pick.confidence && (
                      <div style={{ color: "var(--purple)", fontSize: "0.7rem", fontWeight: 700, marginTop: "2px" }}>
                        {pick.confidence}% Conf
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      
      <style>{`
        @keyframes pulse {
          0% { opacity: 0.6; }
          50% { opacity: 0.3; }
          100% { opacity: 0.6; }
        }
      `}</style>
    </div>
  );
}
