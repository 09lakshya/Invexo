import Link from "next/link";
import { useRouter } from "next/router";
import { useState, useEffect, useRef } from "react";
import API from "../services/api";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";

// Gear icon SVG for Settings
const GearIcon = ({ size = 18, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

// Dashboard Icon SVG
const DashboardIcon = ({ size = 18, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="9" />
    <rect x="14" y="3" width="7" height="5" />
    <rect x="14" y="12" width="7" height="9" />
    <rect x="3" y="16" width="7" height="5" />
  </svg>
);

// Sparkles Icon SVG for AI Advisor
const SparklesIcon = ({ size = 18, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
    <path d="m5 3 1 2.5L8.5 6 6 7 5 9.5 4 7 1.5 6 4 5.5Z" />
    <path d="m19 17 1 2.5 2.5.5-2.5 1-1 2.5-1-2.5-2.5-1 2.5-1Z" />
  </svg>
);

// Calculator Icon SVG
const CalculatorIcon = ({ size = 18, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="4" y="2" width="16" height="20" rx="2" ry="2" />
    <line x1="8" y1="6" x2="16" y2="6" />
    <line x1="16" y1="14" x2="16" y2="18" />
    <line x1="8" y1="14" x2="12" y2="14" />
    <line x1="8" y1="18" x2="12" y2="18" />
    <line x1="8" y1="10" x2="10" y2="10" />
    <line x1="14" y1="10" x2="16" y2="10" />
  </svg>
);

// Briefcase/Portfolio Icon SVG
const PortfolioIcon = ({ size = 18, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
    <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
  </svg>
);

// Logout Icon SVG
const LogOutIcon = ({ size = 18, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <polyline points="16 17 21 12 16 7" />
    <line x1="21" y1="12" x2="9" y2="12" />
  </svg>
);

const NAV_LINKS = [
  { href: "/", label: "Dashboard", icon: DashboardIcon },
  { href: "/advisor", label: "AI Advisor", icon: SparklesIcon },
  { href: "/calculator", label: "Calculator", icon: CalculatorIcon },
  { href: "/portfolio", label: "Portfolio", icon: PortfolioIcon },
  { href: "/settings", label: "Settings", icon: GearIcon, isGear: true },
];

export default function Navbar() {
  const router = useRouter();
  const { user, logout, avatar } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Close dropdowns on outside click
  useEffect(() => {
    const handler = (e) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <>
      <nav
        style={{
          position: "sticky",
          top: 0,
          zIndex: 100,
          background: scrolled ? "var(--nav-bg-scrolled)" : "var(--nav-bg)",
          backdropFilter: "blur(24px) saturate(200%)",
          WebkitBackdropFilter: "blur(24px) saturate(200%)",
          borderBottom: "1px solid var(--border-subtle)",
          transition: "background 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease",
          boxShadow: scrolled ? "0 4px 32px rgba(0,0,0,0.15), 0 1px 0 var(--border-subtle)" : "none",
        }}
      >
        <div
          style={{
            maxWidth: "1400px",
            margin: "0 auto",
            padding: "0 clamp(12px, 3vmin, 24px)",
            height: "clamp(52px, 8vmin, 64px)",
            display: "flex",
            alignItems: "center",
            gap: "clamp(12px, 3vmin, 32px)",
          }}
        >
          {/* Logo */}
          <Link href="/" style={{ textDecoration: "none", flex: "0 0 auto" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <img
                src="/logo-512.png"
                alt="Invexo"
                width={36}
                height={36}
                style={{
                  width: "36px",
                  height: "36px",
                  flexShrink: 0,
                  filter: "drop-shadow(0 2px 8px rgba(0,229,255,0.3))",
                  objectFit: "contain",
                  borderRadius: "6px",
                  aspectRatio: "1 / 1",
                }}
              />
              <span
                style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontWeight: 800,
                  fontSize: "clamp(0.95rem, 1.5vmin, 1.2rem)",
                  background: "linear-gradient(90deg, var(--accent) 0%, var(--purple) 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                  letterSpacing: "-0.02em",
                }}
              >
                Invexo
              </span>
            </div>
          </Link>

          {/* Desktop Nav Links */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              flex: "0 0 auto",
            }}
            className="hidden-mobile"
          >
            {NAV_LINKS.filter(l => !l.isGear).map(({ href, label }) => {
              const active = router.pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  style={{
                    textDecoration: "none",
                    padding: "8px 16px",
                    borderRadius: "10px",
                    fontSize: "0.875rem",
                    fontWeight: 600,
                    color: active ? "var(--accent)" : "var(--text-muted)",
                    background: active ? "var(--accent-dim)" : "transparent",
                    border: active ? "1px solid var(--accent-glow)" : "1px solid transparent",
                    transition: "all 0.2s ease",
                    letterSpacing: "0.01em",
                  }}
                  onMouseEnter={e => {
                    if (!active) {
                      e.currentTarget.style.color = "var(--text-primary)";
                      e.currentTarget.style.background = "var(--hover-overlay)";
                    }
                  }}
                  onMouseLeave={e => {
                    if (!active) {
                      e.currentTarget.style.color = "var(--text-muted)";
                      e.currentTarget.style.background = "transparent";
                    }
                  }}
                >
                  {label}
                </Link>
              );
            })}
          </div>

          {/* Spacer */}
          <div style={{ flex: 1 }} />





          {/* User Menu / Login */}
          {user ? (
            <div ref={userMenuRef} style={{ position: "relative", flexShrink: 0 }}>
              <button
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  background: "var(--search-bg)",
                  border: "1px solid var(--border-medium)",
                  borderRadius: "12px",
                  padding: "6px 14px 6px 6px",
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--accent-glow)"; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border-medium)"; }}
              >
                {/* Avatar */}
                <div
                  style={{
                    width: "32px",
                    height: "32px",
                    borderRadius: "10px",
                    background: avatar ? `url("${avatar}") center / cover no-repeat` : "linear-gradient(135deg, var(--accent) 0%, var(--purple) 100%)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "0.8rem",
                    fontWeight: 800,
                    color: "var(--bg-primary)",
                    fontFamily: "'Space Grotesk', sans-serif",
                    flexShrink: 0,
                  }}
                >
                  {!avatar ? (user.name ? user.name.charAt(0).toUpperCase() : "U") : ""}
                </div>
                <span
                  style={{
                    fontSize: "0.85rem",
                    fontWeight: 600,
                    color: "var(--text-secondary)",
                    maxWidth: "100px",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                  className="hidden sm:inline"
                >
                  {user.name || "User"}
                </span>
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2.5" style={{ flexShrink: 0 }}>
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>

              {/* Dropdown */}
              {userMenuOpen && (
                <div
                  style={{
                    position: "absolute",
                    top: "calc(100% + 8px)",
                    right: 0,
                    width: "240px",
                    background: "var(--dropdown-bg)",
                    border: "1px solid var(--border-medium)",
                    borderRadius: "16px",
                    overflow: "hidden",
                    boxShadow: "var(--shadow-dropdown)",
                    zIndex: 200,
                    animation: "fadeInUp 0.2s ease forwards",
                  }}
                >
                  {/* User info */}
                  <div style={{ padding: "16px 18px", borderBottom: "1px solid var(--border-subtle)" }}>
                    <p style={{ fontWeight: 700, color: "var(--text-primary)", fontSize: "0.95rem", marginBottom: "3px" }}>
                      {user.name}
                    </p>
                    <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {user.email}
                    </p>
                  </div>
                                    {/* Settings */}
                  <button
                    onClick={() => { setUserMenuOpen(false); router.push('/settings'); }}
                    style={{
                      width: "100%",
                      padding: "14px 18px",
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                      textAlign: "left",
                      fontSize: "0.875rem",
                      fontWeight: 600,
                      color: "var(--text-secondary)",
                      fontFamily: "inherit",
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                      transition: "background 0.15s",
                      borderBottom: "1px solid var(--border-subtle)",
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = "var(--hover-overlay)"}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                  >
                    <GearIcon size={16} />
                    Settings
                  </button>

                  {/* Credits */}
                  <button
                    onClick={() => { setUserMenuOpen(false); router.push('/credits'); }}
                    style={{
                      width: "100%",
                      padding: "14px 18px",
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                      textAlign: "left",
                      fontSize: "0.875rem",
                      fontWeight: 600,
                      color: "var(--text-secondary)",
                      fontFamily: "inherit",
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                      transition: "background 0.15s",
                      borderBottom: "1px solid var(--border-subtle)",
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = "var(--hover-overlay)"}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                  >
                    <span style={{ fontSize: "16px", width: "16px", textAlign: "center" }}>ℹ️</span>
                    Credits & About
                  </button>

                  {/* Logout */}
                  <button
                    onClick={() => { setUserMenuOpen(false); logout(); router.replace("/login"); }}
                    style={{
                      width: "100%",
                      padding: "14px 18px",
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                      textAlign: "left",
                      fontSize: "0.875rem",
                      fontWeight: 600,
                      color: "var(--red)",
                      fontFamily: "inherit",
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                      transition: "background 0.15s",
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = "var(--red-dim)"}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                  >
                    <LogOutIcon size={16} color="var(--red)" />
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <>

              <Link
                href="/login"
                style={{
                  padding: "8px 20px",
                  borderRadius: "10px",
                  background: "linear-gradient(135deg, var(--accent) 0%, var(--purple) 100%)",
                  color: "var(--bg-primary)",
                  fontWeight: 700,
                  fontSize: "0.85rem",
                  textDecoration: "none",
                  boxShadow: "0 4px 16px var(--accent-glow)",
                  transition: "all 0.2s",
                  flexShrink: 0,
                }}
              >
                Sign In
              </Link>
            </>
          )}

          {/* Mobile menu button */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            style={{
              background: "var(--search-bg)",
              border: "1px solid var(--border-medium)",
              borderRadius: "10px",
              padding: "8px 12px",
              cursor: "pointer",
              color: "var(--text-secondary)",
              fontSize: "18px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
            className="hidden-desktop"
          >
            {mobileOpen ? "✕" : "☰"}
          </button>
        </div>
      </nav>

      {/* Mobile Menu */}
      {mobileOpen && (
        <div
          style={{
            position: "fixed",
            top: "64px",
            left: 0,
            right: 0,
            bottom: 0,
            background: "var(--mobile-menu-bg)",
            backdropFilter: "blur(24px) saturate(180%)",
            WebkitBackdropFilter: "blur(24px) saturate(180%)",
            zIndex: 99,
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
            animation: "fadeIn 0.2s ease forwards",
          }}
          className="md:hidden"
        >
          {NAV_LINKS.map(({ href, label, icon: IconComponent }) => {
            const active = router.pathname === href;
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setMobileOpen(false)}
                style={{
                  textDecoration: "none",
                  padding: "16px 20px",
                  borderRadius: "14px",
                  fontSize: "1rem",
                  fontWeight: 600,
                  color: active ? "var(--accent)" : "var(--text-secondary)",
                  background: active ? "var(--accent-dim)" : "var(--hover-overlay)",
                  border: `1px solid ${active ? "var(--accent-glow)" : "var(--border-subtle)"}`,
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                }}
              >
                <IconComponent size={20} color={active ? "var(--accent)" : "var(--text-secondary)"} />
                {label}
                {active && <span style={{ marginLeft: "auto", fontSize: "0.75rem", color: "var(--accent)", opacity: 0.7 }}>●</span>}
              </Link>
            );
          })}
          {user && (
            <button
              onClick={() => {
                setMobileOpen(false);
                logout();
                router.replace("/login");
              }}
              style={{
                marginTop: "auto",
                padding: "16px 20px",
                borderRadius: "14px",
                fontSize: "1rem",
                fontWeight: 600,
                color: "var(--red)",
                background: "var(--red-dim)",
                border: "1px solid var(--red-dim)",
                display: "flex",
                alignItems: "center",
                gap: "12px",
                cursor: "pointer",
                textAlign: "left",
                fontFamily: "inherit",
              }}
            >
              <LogOutIcon size={20} color="var(--red)" />
              Sign Out
            </button>
          )}
        </div>
      )}
    </>
  );
}



