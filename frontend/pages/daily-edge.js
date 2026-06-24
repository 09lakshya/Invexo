import React from 'react';
import Head from 'next/head';
import Link from 'next/link';
import Navbar from '../components/Navbar';

export default function DailyEdgePage() {
  return (
    <>
      <Head>
        <title>Daily Edge | Invexo</title>
        <meta name="description" content="Daily Edge is currently under construction and optimization." />
      </Head>
      <div style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "var(--bg-primary)"
      }}>
        <Navbar />
        
        <main style={{
          flex: 1,
          maxWidth: "1400px",
          width: "100%",
          margin: "0 auto",
          padding: "clamp(20px, 4vmin, 60px) clamp(12px, 3vmin, 24px)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          animation: "fadeInUp 0.5s ease both"
        }}>
          
          <div className="glass" style={{
            maxWidth: "600px",
            width: "100%",
            borderRadius: "24px",
            padding: "clamp(24px, 4vmin, 48px)",
            textAlign: "center",
            border: "1px solid var(--border-medium)",
            background: "var(--bg-card)",
            boxShadow: "0 24px 64px rgba(0,0,0,0.6), var(--shadow-card)",
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(20px)",
            position: "relative",
            overflow: "hidden"
          }}>
            {/* Shimmer line */}
            <div style={{
              position: "absolute",
              top: 0, left: 0, right: 0, height: "3px",
              background: "linear-gradient(90deg, var(--accent) 0%, var(--purple) 50%, var(--accent) 100%)",
              backgroundSize: "200% 100%",
              animation: "shimmer 3s infinite linear"
            }} />

            {/* Glowing orb background */}
            <div style={{
              position: "absolute",
              top: "-50px",
              left: "50%",
              transform: "translateX(-50%)",
              width: "150px",
              height: "150px",
              background: "var(--accent-glow)",
              borderRadius: "50%",
              filter: "blur(50px)",
              opacity: 0.5,
              pointerEvents: "none"
            }} />

            {/* SVG Gear/Wrench icon */}
            <div style={{
              width: "80px",
              height: "80px",
              borderRadius: "50%",
              background: "var(--accent-dim)",
              border: "1px solid var(--accent-glow)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 24px",
              position: "relative"
            }}>
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ animation: "spin 12s infinite linear" }}>
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
            </div>

            <h1 style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: "clamp(1.5rem, 3.5vw, 2.2rem)",
              fontWeight: 800,
              letterSpacing: "-0.03em",
              marginBottom: "12px",
              background: "linear-gradient(90deg, var(--accent) 0%, var(--purple) 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}>
              Daily Edge Calibrating
            </h1>

            <p style={{
              color: "var(--text-secondary)",
              fontSize: "0.95rem",
              lineHeight: 1.6,
              marginBottom: "28px",
              fontWeight: 500
            }}>
              We are currently optimizing our XGBoost neural networks and updating technical consensus indicators to provide higher accuracy stock recommendations. This feature is temporarily under construction and will be back online shortly.
            </p>

            {/* Progress Bar */}
            <div style={{ marginBottom: "28px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "8px" }}>
                <span>Model Calibration Progress</span>
                <span style={{ color: "var(--accent)" }}>75%</span>
              </div>
              <div style={{
                height: "8px",
                background: "var(--border-subtle)",
                borderRadius: "10px",
                overflow: "hidden"
              }}>
                <div style={{
                  width: "75%",
                  height: "100%",
                  background: "linear-gradient(90deg, var(--accent) 0%, var(--purple) 100%)",
                  borderRadius: "10px",
                }} />
              </div>
            </div>

            {/* Pipeline list */}
            <div style={{
              background: "var(--input-bg)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "16px",
              padding: "16px 20px",
              textAlign: "left",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
              marginBottom: "28px"
            }}>
              {[
                { status: "done", label: "Pre-trained Model Deployment" },
                { status: "done", label: "Sentiment Lexicon Verification" },
                { status: "pending", label: "Market Regime Calibration" },
                { status: "waiting", label: "Production Validation" }
              ].map((item, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "0.82rem", fontWeight: 600 }}>
                  <span style={{
                    color: item.status === "done" ? "var(--green)" : item.status === "pending" ? "var(--gold)" : "var(--text-muted)",
                    fontSize: "0.9rem"
                  }}>
                    {item.status === "done" ? "✓" : item.status === "pending" ? "⚡" : "○"}
                  </span>
                  <span style={{ color: item.status === "done" ? "var(--text-primary)" : "var(--text-secondary)" }}>
                    {item.label}
                  </span>
                </div>
              ))}
            </div>

            {/* Back Button */}
            <Link href="/" className="btn-primary" style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "12px 24px",
              fontSize: "0.88rem",
              color: "var(--bg-primary)",
              textDecoration: "none",
              borderRadius: "12px",
              fontWeight: 800,
              boxShadow: "0 6px 20px var(--accent-glow)"
            }}>
              &larr; Return to Dashboard
            </Link>

          </div>
        </main>
      </div>

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </>
  );
}
