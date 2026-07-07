import { useEffect, useMemo, useState, useRef } from "react";
import { useRouter } from "next/router";
import Head from "next/head";
import Navbar from "../components/Navbar";
import API from "../services/api";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { SETTINGS_KEY, TIMEFRAME_KEYS } from "../services/preferences";

const defaultSettings = {
  trading: { chartType: "line", timeframe: "3m" },
  appearance: { density: "comfortable" },
};

// Bring older/loosely-typed stored values in line with what the rest of the
// app now expects (candlestick → candle, "1D" → "1d", etc).
function normalizeSettings(parsed) {
  const t = parsed?.trading || {};
  const rawType = String(t.chartType || "").toLowerCase();
  const rawFrame = String(t.timeframe || "").toLowerCase();
  return {
    trading: {
      chartType: rawType === "candle" || rawType === "candlestick" ? "candle" : "line",
      timeframe: TIMEFRAME_KEYS.includes(rawFrame) ? rawFrame : "3m",
    },
    appearance: {
      density: parsed?.appearance?.density === "compact" ? "compact" : "comfortable",
    },
  };
}

/* ── Inline icon set (matches the app's 1.8px stroke language) ──────────── */
const ICON_PATHS = {
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20.5c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5" />
    </>
  ),
  sliders: (
    <>
      <line x1="4" y1="8" x2="20" y2="8" />
      <line x1="4" y1="16" x2="20" y2="16" />
      <circle cx="9" cy="8" r="2.4" />
      <circle cx="15" cy="16" r="2.4" />
    </>
  ),
  chart: (
    <>
      <line x1="7" y1="4" x2="7" y2="20" />
      <rect x="5" y="8" width="4" height="8" rx="1" />
      <line x1="16" y1="4" x2="16" y2="20" />
      <rect x="14" y="6" width="4" height="6" rx="1" />
    </>
  ),
  bell: (
    <>
      <path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6Z" />
      <path d="M10.5 20a1.8 1.8 0 0 0 3 0" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3 5 6v5c0 4 3 7.5 7 9 4-1.5 7-5 7-9V6l-7-3Z" />
      <path d="M12 11v3" />
      <circle cx="12" cy="10" r="0.6" />
    </>
  ),
  camera: (
    <>
      <path d="M4 8h3l1.5-2h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z" />
      <circle cx="12" cy="13" r="3.2" />
    </>
  ),
  eye: (
    <>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  eyeOff: (
    <>
      <path d="M4 4l16 16" />
      <path d="M9.9 5.2A9.9 9.9 0 0 1 12 5c6.5 0 10 7 10 7a15.3 15.3 0 0 1-3.1 3.9" />
      <path d="M6.1 7.1A15.3 15.3 0 0 0 2 12s3.5 7 10 7a9.9 9.9 0 0 0 3.3-.6" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    </>
  ),
  candle: (
    <>
      <line x1="8" y1="3" x2="8" y2="21" />
      <rect x="6" y="7" width="4" height="9" rx="1" />
      <line x1="16" y1="5" x2="16" y2="19" />
      <rect x="14" y="9" width="4" height="6" rx="1" />
    </>
  ),
  line: (
    <>
      <polyline points="3 15 8 9 12 12 21 4" />
      <polyline points="17 4 21 4 21 8" />
    </>
  ),
  moon: <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z" />,
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4 12H2M22 12h-2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19" />
    </>
  ),
  check: <polyline points="20 6 9 17 4 12" />,
  trash: (
    <>
      <polyline points="3 6 21 6" />
      <path d="M19 6v13a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </>
  ),
};

function SvgIcon({ name, size = 18 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ display: "inline-flex", flexShrink: 0 }}
    >
      {ICON_PATHS[name]}
    </svg>
  );
}

/* ── Building blocks ─────────────────────────────────────────────────────── */
function SectionCard({ id, icon, title, description, children }) {
  return (
    <section
      id={id}
      style={{
        scrollMarginTop: "96px",
        background: "var(--bg-card)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "18px",
        boxShadow: "var(--shadow-card)",
        overflow: "hidden",
      }}
    >
      <header
        style={{
          display: "flex",
          gap: "13px",
          alignItems: "flex-start",
          padding: "20px 22px",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <span
          style={{
            width: 38,
            height: 38,
            borderRadius: 11,
            display: "grid",
            placeItems: "center",
            background: "var(--accent-dim)",
            color: "var(--accent)",
            flexShrink: 0,
          }}
        >
          <SvgIcon name={icon} size={19} />
        </span>
        <div style={{ paddingTop: "1px" }}>
          <h2 style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.01em" }}>
            {title}
          </h2>
          {description && (
            <p style={{ color: "var(--text-muted)", fontSize: "0.83rem", marginTop: "3px", lineHeight: 1.5 }}>
              {description}
            </p>
          )}
        </div>
      </header>
      <div style={{ padding: "8px 22px 20px" }}>{children}</div>
    </section>
  );
}

function SettingRow({ label, description, children, last }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: "16px",
        flexWrap: "wrap",
        padding: "16px 0",
        borderBottom: last ? "none" : "1px solid var(--border-subtle)",
      }}
    >
      <div style={{ minWidth: 190, flex: "1 1 220px" }}>
        <p style={{ color: "var(--text-primary)", fontWeight: 600, fontSize: "0.92rem" }}>{label}</p>
        {description && (
          <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: "4px", lineHeight: 1.45 }}>
            {description}
          </p>
        )}
      </div>
      <div style={{ flexShrink: 0 }}>{children}</div>
    </div>
  );
}

function Segmented({ options, value, onChange, ariaLabel }) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      style={{
        display: "inline-flex",
        background: "var(--input-bg)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "11px",
        padding: "3px",
        gap: "2px",
      }}
    >
      {options.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            aria-pressed={active}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "7px",
              padding: "8px 15px",
              borderRadius: "8px",
              border: "none",
              cursor: "pointer",
              fontFamily: "inherit",
              fontWeight: 600,
              fontSize: "0.84rem",
              background: active ? "var(--accent-dim)" : "transparent",
              color: active ? "var(--accent)" : "var(--text-muted)",
              transition: "background 0.18s ease, color 0.18s ease",
            }}
          >
            {opt.icon && <SvgIcon name={opt.icon} size={15} />}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

const fieldLabelStyle = {
  fontSize: "0.72rem",
  color: "var(--text-muted)",
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  display: "block",
};

const inputStyle = {
  marginTop: "8px",
  width: "100%",
  background: "var(--input-bg)",
  border: "1px solid var(--input-border)",
  borderRadius: "11px",
  padding: "11px 14px",
  color: "var(--text-primary)",
  fontFamily: "inherit",
  fontSize: "0.92rem",
  outline: "none",
};

const SECTIONS = [
  { id: "profile", label: "Profile", icon: "user" },
  { id: "appearance", label: "Appearance", icon: "sliders" },
  { id: "charts", label: "Charts", icon: "chart" },
  { id: "alerts", label: "Alerts", icon: "bell" },
  { id: "security", label: "Security", icon: "shield" },
];

export default function SettingsPage() {
  const router = useRouter();
  const { user, setUser, refreshUser, logout, avatar, updateAvatar } = useAuth();
  const { theme, setThemeMode } = useTheme();
  const fileInputRef = useRef(null);
  const savedTimer = useRef(null);

  const [settings, setSettings] = useState(defaultSettings);
  const [saved, setSaved] = useState(false);

  const [profileName, setProfileName] = useState(user?.name || "");
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileMessage, setProfileMessage] = useState("");

  const [passwordForm, setPasswordForm] = useState({ current_password: "", new_password: "", confirm: "" });
  const [showPasswords, setShowPasswords] = useState(false);
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState({ text: "", ok: false });

  const [signalSubs, setSignalSubs] = useState([]);
  const [signalSubsLoading, setSignalSubsLoading] = useState(true);

  const [activeSection, setActiveSection] = useState("profile");

  /* ── Load persisted preferences ── */
  useEffect(() => {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) {
      try {
        setSettings(normalizeSettings(JSON.parse(raw)));
      } catch {
        setSettings(defaultSettings);
      }
    }
  }, []);

  useEffect(() => {
    setProfileName(user?.name || "");
  }, [user?.name]);

  useEffect(() => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    document.documentElement.setAttribute("data-density", settings.appearance.density);
  }, [settings]);

  /* ── Signal-alert subscriptions ── */
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const res = await API.get("/signal-alerts/subscriptions");
        if (active) setSignalSubs(res.data || []);
      } catch {
        /* unauthenticated or transient — leave empty */
      } finally {
        if (active) setSignalSubsLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  /* ── Scroll-spy for the section rail ── */
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) setActiveSection(visible[0].target.id);
      },
      { rootMargin: "-100px 0px -55% 0px", threshold: [0.15, 0.4, 0.7] }
    );
    SECTIONS.forEach((s) => {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);

  useEffect(() => () => clearTimeout(savedTimer.current), []);

  const memberSince = useMemo(() => {
    if (!user?.created_at) return "Recently";
    const d = new Date(user.created_at);
    if (Number.isNaN(d.getTime())) return user.created_at;
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
  }, [user?.created_at]);

  const flashSaved = () => {
    setSaved(true);
    clearTimeout(savedTimer.current);
    savedTimer.current = setTimeout(() => setSaved(false), 1600);
  };

  const updateNested = (section, key, value) => {
    setSettings((prev) => ({ ...prev, [section]: { ...prev[section], [key]: value } }));
    flashSaved();
  };

  const goTo = (id) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveSection(id);
  };

  const removeSignalSub = async (id) => {
    try {
      await API.delete(`/signal-alerts/subscriptions/${id}`);
      setSignalSubs((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      console.error("Failed to remove signal subscription:", err);
    }
  };

  const handleAvatarUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => updateAvatar(String(reader.result || ""));
    reader.readAsDataURL(file);
  };

  const handleSaveProfile = async () => {
    setProfileMessage("");
    if (!profileName.trim()) {
      setProfileMessage("Please enter your name.");
      return;
    }
    if (profileName.trim() === (user?.name || "")) {
      setProfileMessage("That's already your name.");
      return;
    }
    setSavingProfile(true);
    try {
      const res = await API.patch("/auth/profile", { name: profileName.trim() });
      setUser(res.data);
      setProfileMessage("Saved.");
      await refreshUser();
    } catch (err) {
      setProfileMessage(err?.response?.data?.detail || "Could not update your profile.");
    } finally {
      setSavingProfile(false);
    }
  };

  const handleChangePassword = async () => {
    setPasswordMessage({ text: "", ok: false });
    if (!passwordForm.current_password || !passwordForm.new_password) {
      setPasswordMessage({ text: "Fill in your current and new password.", ok: false });
      return;
    }
    if (passwordForm.new_password.length < 6) {
      setPasswordMessage({ text: "Use at least 6 characters for the new password.", ok: false });
      return;
    }
    if (passwordForm.new_password !== passwordForm.confirm) {
      setPasswordMessage({ text: "The new passwords don't match.", ok: false });
      return;
    }
    setPasswordSaving(true);
    try {
      await API.post("/auth/change-password", {
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      });
      setPasswordForm({ current_password: "", new_password: "", confirm: "" });
      setPasswordMessage({ text: "Password updated.", ok: true });
    } catch (err) {
      setPasswordMessage({ text: err?.response?.data?.detail || "Couldn't update your password.", ok: false });
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  const initial = user?.name?.charAt(0)?.toUpperCase() || "U";

  return (
    <>
      <Head>
        <title>Settings · Invexo</title>
        <meta name="description" content="Manage your Invexo account, appearance, chart defaults, alerts and security." />
      </Head>

      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />

        <div style={{ maxWidth: "1020px", margin: "0 auto", padding: "var(--page-padding-top) var(--page-gutter) 96px", width: "100%" }}>
          {/* Header */}
          <div style={{ marginBottom: "24px" }}>
            <p style={{ ...fieldLabelStyle, color: "var(--text-muted)", marginBottom: "8px" }}>Account</p>
            <h1
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: "clamp(1.7rem, 4vmin, 2.4rem)",
                fontWeight: 800,
                color: "var(--text-primary)",
                letterSpacing: "-0.02em",
                lineHeight: 1.1,
              }}
            >
              Settings
            </h1>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem", marginTop: "8px", maxWidth: "56ch" }}>
              Signed in as <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>{user?.email || "your account"}</span>. Appearance and chart choices save automatically on this device.
            </p>
          </div>

          {/* Mobile section chips */}
          <div className="settings-rail-mobile">
            {SECTIONS.map((s) => (
              <button
                key={s.id}
                type="button"
                className="settings-nav-link"
                data-active={activeSection === s.id}
                onClick={() => goTo(s.id)}
              >
                <span className="settings-nav-icon">
                  <SvgIcon name={s.icon} size={16} />
                </span>
                {s.label}
              </button>
            ))}
          </div>

          <div className="settings-shell">
            {/* Desktop rail */}
            <nav className="settings-rail" aria-label="Settings sections">
              {SECTIONS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className="settings-nav-link"
                  data-active={activeSection === s.id}
                  onClick={() => goTo(s.id)}
                >
                  <span className="settings-nav-icon">
                    <SvgIcon name={s.icon} size={17} />
                  </span>
                  {s.label}
                </button>
              ))}
            </nav>

            {/* Content */}
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--section-gap)", minWidth: 0 }}>
              {/* ── Profile ── */}
              <SectionCard
                id="profile"
                icon="user"
                title="Profile"
                description="The name and photo shown on your account across Invexo."
              >
                <div style={{ display: "flex", gap: "18px", alignItems: "center", padding: "16px 0", flexWrap: "wrap", borderBottom: "1px solid var(--border-subtle)" }}>
                  <div style={{ position: "relative" }}>
                    <div
                      style={{
                        width: "66px",
                        height: "66px",
                        borderRadius: "18px",
                        background: avatar ? `url("${avatar}") center / cover no-repeat` : "var(--accent-dim)",
                        border: "1px solid var(--border-medium)",
                        display: "grid",
                        placeItems: "center",
                        color: "var(--accent)",
                        fontWeight: 800,
                        fontSize: "1.5rem",
                        fontFamily: "'Space Grotesk', sans-serif",
                      }}
                    >
                      {!avatar && initial}
                    </div>
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      aria-label="Change profile photo"
                      style={{
                        position: "absolute",
                        right: "-6px",
                        bottom: "-6px",
                        width: "28px",
                        height: "28px",
                        borderRadius: "50%",
                        border: "1px solid var(--border-medium)",
                        background: "var(--bg-card-solid)",
                        color: "var(--text-secondary)",
                        display: "grid",
                        placeItems: "center",
                        cursor: "pointer",
                        boxShadow: "var(--shadow-card)",
                      }}
                    >
                      <SvgIcon name="camera" size={14} />
                    </button>
                  </div>

                  <div style={{ flex: "1 1 200px" }}>
                    <p style={{ color: "var(--text-primary)", fontWeight: 600, fontSize: "0.92rem" }}>Profile photo</p>
                    <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: "3px", marginBottom: "10px" }}>
                      Square images look best. PNG or JPG.
                    </p>
                    <input ref={fileInputRef} type="file" accept="image/*" onChange={handleAvatarUpload} style={{ display: "none" }} />
                    <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        style={{
                          padding: "8px 16px",
                          borderRadius: "10px",
                          border: "1px solid var(--border-medium)",
                          background: "var(--input-bg)",
                          color: "var(--text-primary)",
                          fontSize: "0.84rem",
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        Upload
                      </button>
                      {avatar && (
                        <button
                          type="button"
                          onClick={() => {
                            updateAvatar("");
                            if (fileInputRef.current) fileInputRef.current.value = "";
                          }}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "6px",
                            padding: "8px 14px",
                            borderRadius: "10px",
                            border: "1px solid var(--border-subtle)",
                            background: "transparent",
                            color: "var(--text-muted)",
                            fontSize: "0.84rem",
                            fontWeight: 600,
                            cursor: "pointer",
                          }}
                        >
                          <SvgIcon name="trash" size={14} /> Remove
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                <div style={{ padding: "18px 0", borderBottom: "1px solid var(--border-subtle)" }}>
                  <label style={fieldLabelStyle} htmlFor="settings-name">Full name</label>
                  <div style={{ display: "flex", gap: "10px", alignItems: "flex-start", flexWrap: "wrap" }}>
                    <input
                      id="settings-name"
                      value={profileName}
                      onChange={(e) => setProfileName(e.target.value)}
                      placeholder="Your name"
                      style={{ ...inputStyle, flex: "1 1 220px" }}
                    />
                    <button
                      onClick={handleSaveProfile}
                      disabled={savingProfile}
                      style={{
                        marginTop: "8px",
                        padding: "11px 22px",
                        borderRadius: "11px",
                        border: "none",
                        background: "var(--accent)",
                        color: "var(--bg-primary)",
                        fontWeight: 700,
                        fontSize: "0.9rem",
                        cursor: savingProfile ? "not-allowed" : "pointer",
                        opacity: savingProfile ? 0.65 : 1,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {savingProfile ? "Saving…" : "Save name"}
                    </button>
                  </div>
                  {!!profileMessage && (
                    <p style={{ color: profileMessage === "Saved." ? "var(--green)" : "var(--text-muted)", fontSize: "0.82rem", marginTop: "8px", fontWeight: 500 }}>
                      {profileMessage}
                    </p>
                  )}
                </div>

                <div style={{ padding: "18px 0 6px" }}>
                  <label style={fieldLabelStyle}>Email address</label>
                  <div style={{ marginTop: "8px", display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                    <input value={user?.email || ""} disabled style={{ ...inputStyle, marginTop: 0, flex: "1 1 220px", color: "var(--text-muted)" }} />
                    <span style={{ display: "inline-flex", alignItems: "center", gap: "5px", padding: "6px 12px", borderRadius: "20px", background: "var(--green-dim)", color: "var(--green)", fontSize: "0.74rem", fontWeight: 700 }}>
                      <SvgIcon name="check" size={13} /> Verified
                    </span>
                  </div>
                  <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: "10px" }}>
                    Member since <span style={{ color: "var(--text-secondary)", fontWeight: 600 }}>{memberSince}</span>. Your email is your login and can't be changed here.
                  </p>
                </div>
              </SectionCard>

              {/* ── Appearance ── */}
              <SectionCard
                id="appearance"
                icon="sliders"
                title="Appearance"
                description="How Invexo looks on this device. Changes apply instantly."
              >
                <SettingRow label="Theme" description="Use a dark or light interface.">
                  <Segmented
                    ariaLabel="Theme"
                    value={theme}
                    onChange={setThemeMode}
                    options={[
                      { value: "dark", label: "Dark", icon: "moon" },
                      { value: "light", label: "Light", icon: "sun" },
                    ]}
                  />
                </SettingRow>
                <SettingRow
                  label="Display density"
                  description="Compact tightens spacing to fit more on screen."
                  last
                >
                  <Segmented
                    ariaLabel="Display density"
                    value={settings.appearance.density}
                    onChange={(v) => updateNested("appearance", "density", v)}
                    options={[
                      { value: "comfortable", label: "Comfortable" },
                      { value: "compact", label: "Compact" },
                    ]}
                  />
                </SettingRow>
              </SectionCard>

              {/* ── Charts ── */}
              <SectionCard
                id="charts"
                icon="chart"
                title="Charts"
                description="Your defaults, applied every time you open a stock. You can still switch on the chart itself."
              >
                <SettingRow label="Default chart style" description="Candlesticks show open/high/low/close; line is a simpler close-price view.">
                  <Segmented
                    ariaLabel="Default chart style"
                    value={settings.trading.chartType}
                    onChange={(v) => updateNested("trading", "chartType", v)}
                    options={[
                      { value: "candle", label: "Candles", icon: "candle" },
                      { value: "line", label: "Line", icon: "line" },
                    ]}
                  />
                </SettingRow>
                <SettingRow label="Default time range" description="The range a chart opens on." last>
                  <Segmented
                    ariaLabel="Default time range"
                    value={settings.trading.timeframe}
                    onChange={(v) => updateNested("trading", "timeframe", v)}
                    options={[
                      { value: "1d", label: "1D" },
                      { value: "1w", label: "1W" },
                      { value: "1m", label: "1M" },
                      { value: "3m", label: "3M" },
                      { value: "6m", label: "6M" },
                      { value: "1y", label: "1Y" },
                    ]}
                  />
                </SettingRow>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", flexWrap: "wrap", paddingTop: "14px", marginTop: "4px", borderTop: "1px solid var(--border-subtle)" }}>
                  <p style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>Prices are in Indian Rupees (₹).</p>
                  <span style={{ padding: "5px 11px", borderRadius: "20px", background: "var(--input-bg)", border: "1px solid var(--border-subtle)", color: "var(--text-secondary)", fontSize: "0.74rem", fontWeight: 700 }}>
                    INR ₹
                  </span>
                </div>
              </SectionCard>

              {/* ── Alerts ── */}
              <SectionCard
                id="alerts"
                icon="bell"
                title="Signal alerts"
                description="We notify you — in-app and by email — when Invexo's model flips to BUY or SELL on a stock."
              >
                <div style={{ background: "var(--input-bg)", border: "1px solid var(--border-subtle)", borderRadius: "12px", padding: "14px 16px", marginTop: "8px", marginBottom: "8px" }}>
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", lineHeight: 1.55 }}>
                    Everything on your <strong style={{ color: "var(--text-primary)" }}>watchlist</strong> and in your{" "}
                    <strong style={{ color: "var(--text-primary)" }}>portfolio</strong> is covered automatically. To follow any
                    other stock, open it and tap the <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>bell</span> icon.
                  </p>
                </div>

                <p style={{ ...fieldLabelStyle, marginTop: "14px", marginBottom: "2px" }}>Followed manually</p>

                {signalSubsLoading ? (
                  <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", padding: "12px 0" }}>Loading…</p>
                ) : signalSubs.length === 0 ? (
                  <p style={{ color: "var(--text-muted)", fontSize: "0.84rem", padding: "12px 0", lineHeight: 1.55 }}>
                    Nothing followed manually yet — your watchlist and holdings are already covered.
                  </p>
                ) : (
                  signalSubs.map((s, i) => (
                    <div
                      key={s.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "13px 0",
                        borderBottom: i === signalSubs.length - 1 ? "none" : "1px solid var(--border-subtle)",
                        gap: "16px",
                      }}
                    >
                      <div>
                        <p style={{ color: "var(--text-primary)", fontWeight: 700, fontSize: "0.92rem" }}>{s.symbol}</p>
                        <p style={{ color: "var(--text-muted)", fontSize: "0.79rem", marginTop: "3px" }}>
                          Alerts at ≥ {s.min_confidence}% model confidence
                        </p>
                      </div>
                      <button
                        onClick={() => removeSignalSub(s.id)}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          padding: "7px 13px",
                          borderRadius: "10px",
                          border: "1px solid var(--border-subtle)",
                          background: "transparent",
                          color: "var(--text-muted)",
                          fontSize: "0.8rem",
                          fontWeight: 600,
                          cursor: "pointer",
                          flexShrink: 0,
                        }}
                      >
                        <SvgIcon name="trash" size={14} /> Remove
                      </button>
                    </div>
                  ))
                )}

                <p style={{ color: "var(--text-muted)", fontSize: "0.72rem", marginTop: "16px", lineHeight: 1.5 }}>
                  Signals are automated model outputs, not investment advice. They can be wrong — always do your own research.
                </p>
              </SectionCard>

              {/* ── Security ── */}
              <SectionCard
                id="security"
                icon="shield"
                title="Security"
                description="Update your password or sign out of this device."
              >
                <div style={{ padding: "8px 0 4px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" }}>
                    <p style={{ color: "var(--text-primary)", fontWeight: 600, fontSize: "0.92rem" }}>Change password</p>
                    <button
                      type="button"
                      onClick={() => setShowPasswords((v) => !v)}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        background: "transparent",
                        border: "none",
                        color: "var(--text-muted)",
                        fontSize: "0.8rem",
                        fontWeight: 600,
                        cursor: "pointer",
                        fontFamily: "inherit",
                      }}
                    >
                      <SvgIcon name={showPasswords ? "eyeOff" : "eye"} size={15} />
                      {showPasswords ? "Hide" : "Show"}
                    </button>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(180px, 100%), 1fr))", gap: "14px", marginTop: "14px" }}>
                    <div>
                      <label style={fieldLabelStyle}>Current</label>
                      <input
                        type={showPasswords ? "text" : "password"}
                        autoComplete="current-password"
                        value={passwordForm.current_password}
                        onChange={(e) => setPasswordForm((p) => ({ ...p, current_password: e.target.value }))}
                        style={inputStyle}
                      />
                    </div>
                    <div>
                      <label style={fieldLabelStyle}>New</label>
                      <input
                        type={showPasswords ? "text" : "password"}
                        autoComplete="new-password"
                        value={passwordForm.new_password}
                        onChange={(e) => setPasswordForm((p) => ({ ...p, new_password: e.target.value }))}
                        style={inputStyle}
                      />
                    </div>
                    <div>
                      <label style={fieldLabelStyle}>Confirm new</label>
                      <input
                        type={showPasswords ? "text" : "password"}
                        autoComplete="new-password"
                        value={passwordForm.confirm}
                        onChange={(e) => setPasswordForm((p) => ({ ...p, confirm: e.target.value }))}
                        style={inputStyle}
                      />
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", marginTop: "16px", flexWrap: "wrap" }}>
                    {passwordMessage.text ? (
                      <p style={{ color: passwordMessage.ok ? "var(--green)" : "var(--red)", fontSize: "0.82rem", fontWeight: 500 }}>
                        {passwordMessage.text}
                      </p>
                    ) : (
                      <p style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>At least 6 characters.</p>
                    )}
                    <button
                      onClick={handleChangePassword}
                      disabled={passwordSaving}
                      style={{
                        padding: "10px 20px",
                        borderRadius: "11px",
                        border: "1px solid var(--border-medium)",
                        background: "var(--input-bg)",
                        color: "var(--text-primary)",
                        fontWeight: 700,
                        fontSize: "0.88rem",
                        cursor: passwordSaving ? "not-allowed" : "pointer",
                        opacity: passwordSaving ? 0.65 : 1,
                        marginLeft: "auto",
                      }}
                    >
                      {passwordSaving ? "Updating…" : "Update password"}
                    </button>
                  </div>
                </div>

                <div style={{ marginTop: "18px", paddingTop: "18px", borderTop: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
                  <div>
                    <p style={{ color: "var(--text-primary)", fontWeight: 600, fontSize: "0.92rem" }}>Sign out</p>
                    <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: "3px" }}>End your session on this device.</p>
                  </div>
                  <button
                    onClick={handleLogout}
                    style={{
                      padding: "10px 20px",
                      borderRadius: "11px",
                      border: "1px solid var(--red-dim)",
                      background: "var(--red-dim)",
                      color: "var(--red)",
                      cursor: "pointer",
                      fontWeight: 700,
                      fontSize: "0.88rem",
                    }}
                  >
                    Sign out
                  </button>
                </div>
              </SectionCard>
            </div>
          </div>
        </div>
      </div>

      {/* Auto-save confirmation */}
      <div
        aria-live="polite"
        style={{
          position: "fixed",
          bottom: "24px",
          left: "50%",
          transform: `translateX(-50%) translateY(${saved ? "0" : "16px"})`,
          display: "inline-flex",
          alignItems: "center",
          gap: "8px",
          padding: "10px 18px",
          borderRadius: "999px",
          background: "var(--bg-card-solid)",
          border: "1px solid var(--border-medium)",
          boxShadow: "var(--shadow-dropdown)",
          color: "var(--text-primary)",
          fontSize: "0.84rem",
          fontWeight: 600,
          opacity: saved ? 1 : 0,
          pointerEvents: "none",
          transition: "opacity 0.25s ease, transform 0.25s ease",
          zIndex: 200,
        }}
      >
        <span style={{ color: "var(--green)", display: "inline-flex" }}>
          <SvgIcon name="check" size={16} />
        </span>
        Preferences saved
      </div>
    </>
  );
}
