import React from 'react';
import Head from 'next/head';
import Navbar from '../components/Navbar';
import DailyPicks from '../components/DailyPicks';

export default function DailyEdgePage() {
  return (
    <>
      <Head>
        <title>Daily Edge | Invexo</title>
        <meta name="description" content="Get your daily edge with AI-powered stock picks across large, mid, and small cap sectors." />
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
          padding: "clamp(20px, 4vmin, 40px) clamp(12px, 3vmin, 24px)",
          animation: "fadeInUp 0.5s ease both"
        }}>
          <div style={{ marginBottom: "32px" }}>
            <h1 style={{ 
              fontSize: "clamp(2rem, 4vw, 2.8rem)", 
              fontWeight: 800, 
              marginBottom: "8px",
              background: "linear-gradient(90deg, var(--text-primary), var(--text-secondary))",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent"
            }}>
              The Daily Edge
            </h1>
            <p style={{ color: "var(--text-secondary)", fontSize: "1.1rem", maxWidth: "600px" }}>
              Actionable AI-driven stock recommendations updated every midnight to give you an edge in the market.
            </p>
          </div>
          
          <DailyPicks />
        </main>
      </div>
    </>
  );
}
