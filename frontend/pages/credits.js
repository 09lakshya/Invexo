import Navbar from "../components/Navbar";
import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";

export default function Credits() {
  const router = useRouter();

  const creditItems = [
    {
      category: "Developer",
      credits: [
        { name: "Lakshya Hindocha", role: "Full Stack Developer & Student Creator" }
      ]
    },
    {
      category: "Data Services & APIs",
      credits: [
        { name: "Yahoo Finance (yfinance)", role: "Historical & real-time stock pricing feed" },
        { name: "Clearbit Logo API", role: "Real-time automated company branding metadata" }
      ]
    },
    {
      category: "Backend Stack",
      credits: [
        { name: "FastAPI", role: "High-performance Python web gateway & WebSockets engine" },
        { name: "curl_cffi", role: "TLS fingerprint client impersonation (bypassing rate limits)" },
        { name: "TextBlob", role: "NLP polarity parsing adjusted with custom financial lexicons" }
      ]
    },
    {
      category: "Frontend Stack",
      credits: [
        { name: "Next.js & React", role: "Declarative framework for the single page app application structure" },
        { name: "Tailwind CSS", role: "Responsive glassmorphism layout utility styles" },
        { name: "Chart.js", role: "Market historical chart rendering" }
      ]
    }
  ];

  return (
    <>
      <Head>
        <title>Credits & About — Invexo</title>
        <meta name="description" content="Invexo developers, creators, third-party APIs, libraries, and libraries used." />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </Head>

      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />

        <div style={{ maxWidth: "720px", margin: "0 auto", padding: "clamp(20px, 4vmin, 40px) clamp(12px, 3vmin, 24px) clamp(40px, 8vmin, 80px)" }}>
          
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "24px" }}>
            <button
              onClick={() => router.back()}
              style={{
                background: "var(--bg-card)",
                border: "1px solid var(--border-medium)",
                borderRadius: "10px",
                padding: "6px 12px",
                cursor: "pointer",
                color: "var(--text-muted)",
                fontSize: "0.8rem",
                fontFamily: "inherit",
                transition: "all 0.2s",
              }}
              onMouseEnter={e => { e.currentTarget.style.color = "var(--text-primary)"; e.currentTarget.style.borderColor = "var(--accent-glow)"; }}
              onMouseLeave={e => { e.currentTarget.style.color = "var(--text-muted)"; e.currentTarget.style.borderColor = "var(--border-medium)"; }}
            >
              ← Back
            </button>
            <p style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.08em", textTransform: "uppercase", margin: 0 }}>Project Details</p>
          </div>

          <div style={{ marginBottom: "36px", animation: "fadeInUp 0.5s ease forwards" }}>
            <h1
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: "clamp(2rem, 4vmin, 2.8rem)",
                fontWeight: 800,
                letterSpacing: "-0.03em",
                background: "linear-gradient(90deg, var(--accent) 0%, var(--purple) 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
                marginBottom: "10px",
              }}
            >
              Credits & About
            </h1>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem", lineHeight: 1.6 }}>
              Invexo is an Indian stock market tracker and predictive analysis tool designed to guide investors using artificial intelligence algorithms. Below are the creators and services that power this app.
            </p>
          </div>

          {/* Credits List */}
          <div style={{ display: "flex", flexDirection: "column", gap: "20px", animation: "fadeInUp 0.5s 0.1s ease both" }}>
            {creditItems.map((sec, idx) => (
              <div
                key={sec.category}
                style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "16px",
                  padding: "20px 24px",
                  backdropFilter: "blur(16px)",
                  transition: "all 0.2s ease",
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--accent-glow)"; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border-subtle)"; }}
              >
                <h2 style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--accent)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "14px" }}>
                  {sec.category}
                </h2>
                
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {sec.credits.map((item) => (
                    <div key={item.name} style={{ borderLeft: "2px solid var(--border-medium)", paddingLeft: "12px" }}>
                      <p style={{ fontWeight: 700, color: "var(--text-primary)", fontSize: "0.9rem", margin: "0 0 2px 0" }}>
                        {item.name}
                      </p>
                      <p style={{ color: "var(--text-muted)", fontSize: "0.78rem", margin: 0, lineHeight: 1.4 }}>
                        {item.role}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Footer note */}
          <div style={{ marginTop: "40px", textAlign: "center" }}>
            <p style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
              Invexo is for educational purposes only. Developed by Lakshya Hindocha.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
